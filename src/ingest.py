"""Phase 2: turn the official source files into tagged, searchable chunks.

Run from the project root:
    python src/ingest.py

Reads   data/manifest.csv and the files under data/
Writes  data/processed/chunks.jsonl  (one JSON object per chunk)

Every chunk carries the metadata the assistant needs to cite it:
source_id, url, title, publisher, doc_type, scheme, as_of, page.

Two kinds of chunk are produced:
  - "text": running text split into overlapping windows of ~220 words.
  - "fact": one-line facts rebuilt from tables (expense ratio, exit load,
    benchmark, minimum SIP, riskometer), where plain text extraction would
    lose which number belongs to which scheme.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import openpyxl
import pymupdf

sys.path.insert(0, str(Path(__file__).parent))
from schemes import SCHEMES, scheme_name  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "processed" / "chunks.jsonl"

CHUNK_WORDS = 220
OVERLAP_WORDS = 40

# Matches return/performance tables ("1 Year ... 9.43"), so these chunks can be
# kept out of answers: the assistant must never state or compare returns.
RETURNS_RE = re.compile(
    r"(1 Year|3 Years|5 Years|Since Inception|Returns for last)\D{0,40}-?\d+\.\d+"
    r"|Value of (Std )?Investment|Value of ₹?\s?10,000|Disclosure on performance"
    r"|\bCAGR\b|Sharpe Ratio|Standard Deviation",
    re.I,
)

# Rows from the factsheet snapshot tables worth keeping as facts.
SNAPSHOT_ROWS = (
    "Type of Scheme",
    "Scheme Characteristics",  # ELSS: "...with a lock in period of 3 years"
    "Benchmark",
    "Base Expense Ratio",
    "Exit Load",
    "Inception Date",
    "Indicative Investment Horizon",
    "Fund Manager",
)


@dataclass
class Chunk:
    id: str
    source_id: str
    url: str
    title: str
    publisher: str
    doc_type: str
    scheme: str
    as_of: str
    page: int | None
    kind: str
    has_returns: bool
    text: str


# ---------------------------------------------------------------- helpers

def clean(text: str) -> str:
    text = text.replace("\xad", "").replace("ŧ", "")
    text = re.sub(r"`\s?(?=\d)", "₹", text)  # factsheet prints ₹ as a backtick
    return re.sub(r"\s+", " ", text).strip()


def windows(text: str, size: int = CHUNK_WORDS, overlap: int = OVERLAP_WORDS):
    words = text.split()
    if len(words) <= size:
        if words:
            yield " ".join(words)
        return
    step = size - overlap
    for start in range(0, len(words), step):
        piece = words[start:start + size]
        if len(piece) < 40 and start > 0:  # tiny tail: already covered by overlap
            break
        yield " ".join(piece)


def cell_text(words, rect) -> str:
    """Text of a table cell, built from words whose centre lies inside it."""
    if rect is None:
        return ""
    r = pymupdf.Rect(rect)
    inside = [w for w in words
              if r.contains(pymupdf.Point((w[0] + w[2]) / 2, (w[1] + w[3]) / 2))]
    inside.sort(key=lambda w: (round(w[1]), w[0]))
    return clean(" ".join(w[4] for w in inside))


def table_rows(page):
    words = page.get_text("words")
    for table in page.find_tables().tables:
        yield [[cell_text(words, c) for c in row.cells] for row in table.rows]


def graded_exit_load(cell: str) -> str:
    """Rebuild a day-wise exit load table (liquid funds) that PDF extraction scrambles.

    "Investor exit Day 7 Day 1 ... Day 6 ... 0.0070% 0.0065% ... 0.0000%"
    becomes "Day 1: 0.0070%; ...; Day 7 onwards: 0.0000% (of redemption proceeds)".
    """
    days = sorted({int(d) for d in re.findall(r"Day (\d+)", cell)})
    rates = re.findall(r"\d+\.\d+%", cell)
    if not days or len(days) != len(rates):
        return cell
    parts = [f"Day {d}{' onwards' if d == days[-1] else ''}: {r}" for d, r in zip(days, rates)]
    return "Graded by days since subscription — " + "; ".join(parts) + " (as a % of redemption proceeds)"


def match_scheme(label: str) -> str | None:
    low = label.lower().replace(" ", "")
    for key, s in SCHEMES.items():
        if any(n.lower().replace(" ", "") == low for n in s["doc_names"]):
            return key
    return None


class Builder:
    """Collects chunks and stamps each with its source's metadata."""

    def __init__(self, entry: dict):
        self.entry = entry
        self.chunks: list[Chunk] = []

    def add(self, text: str, *, scheme: str | None = None, page: int | None = None,
            kind: str = "text", returns_page: bool = False) -> None:
        text = clean(text)
        if len(text.split()) < 8:
            return
        scheme = scheme or self.entry["scheme"]
        header = f"[{scheme_name(scheme)} | {self.entry['doc_type']}]"
        e = self.entry
        self.chunks.append(Chunk(
            id=f"{e['source_id']}-{len(self.chunks) + 1:03d}",
            source_id=e["source_id"], url=e["url"], title=e["title"],
            publisher=e["publisher"], doc_type=e["doc_type"], scheme=scheme,
            as_of=e["as_of"], page=page, kind=kind,
            has_returns=returns_page or bool(RETURNS_RE.search(text)),
            text=f"{header} {text}",
        ))

    def add_windows(self, text: str, **kw) -> None:
        """Split a page into windows. If the page reports returns anywhere,
        every window from it is flagged, since tables split across windows."""
        text = clean(text)
        kw.setdefault("returns_page", bool(RETURNS_RE.search(text)))
        for piece in windows(text):
            self.add(piece, **kw)


# ---------------------------------------------------------------- extractors

def ingest_kim(b: Builder, path: Path) -> None:
    doc = pymupdf.open(path)
    for i, page in enumerate(doc):
        text = page.get_text()
        if "COMMON APPLICATION FORM" in text:
            break  # the rest is application forms, not scheme facts
        b.add_windows(text, page=i + 1)

    # Minimum SIP table (inside the SIP form): ELSS has its own row,
    # every other scheme follows the "All Scheme" row.
    own_key = b.entry["scheme"]
    for i, page in enumerate(doc):
        if "Minimum SIP Amount" not in page.get_text():
            continue
        for rows in table_rows(page):
            freqs = next((r[2:] for r in rows if "Daily" in r), None)
            if not freqs:
                continue
            current = None
            block: dict[str, list[str]] = {}
            for r in rows:
                if r[0]:
                    current = r[0]
                if current and r[1]:
                    block.setdefault(current, []).append((r[1], r[2:]))
            for label, lines in block.items():
                applies = (match_scheme(label) == own_key) or (
                    label == "All Scheme" and own_key != "elss")
                if not applies:
                    continue
                parts = []
                for field, values in lines:
                    vals = "; ".join(f"{f}: {v}" for f, v in zip(freqs, values) if v)
                    parts.append(f"{field} — {vals}.")
                b.add(f"Minimum SIP for {scheme_name(own_key)} by frequency. " + " ".join(parts),
                      page=i + 1, kind="fact")
        break


def ingest_sid(b: Builder, path: Path) -> None:
    for i, page in enumerate(pymupdf.open(path)):
        b.add_windows(page.get_text(), page=i + 1)


def ingest_factsheet(b: Builder, path: Path) -> None:
    doc = pymupdf.open(path)
    for i, page in enumerate(doc):
        text = page.get_text()
        flat = clean(text)

        # Glossary page: definitions of expense ratio, exit load, SIP, etc.
        if flat.upper().startswith("HOW TO READ FACTSHEET"):
            b.add_windows(text, scheme="all", page=i + 1)
            continue

        # Snapshot tables: one column per scheme.
        if flat.startswith("Snapshot of"):
            for rows in table_rows(page):
                header = next((r for r in rows if r and r[0] == "Scheme Name"), None)
                if not header:
                    continue
                for col, label in enumerate(header[1:], start=1):
                    key = match_scheme(label)
                    if not key:
                        continue
                    facts = []
                    for r in rows:
                        if col < len(r) and r[col] and r[0].startswith(SNAPSHOT_ROWS):
                            label, value = r[0], r[col]
                            if label.startswith("Exit Load") and "Day 1" in value:
                                value = graded_exit_load(value)
                            m = re.match(r"([\d.]+%)\s*/\s*([\d.]+%)", value)
                            if label.startswith("Base Expense Ratio") and m:
                                label = "Expense ratio (base expense ratio, BER)"
                                value = f"Regular Plan {m[1]}, Direct Plan {m[2]}"
                            facts.append(f"{label}: {value}.")
                    if facts:
                        b.add(f"{scheme_name(key)} key facts (factsheet, as on 30 September 2026). "
                              + " ".join(facts), scheme=key, page=i + 1, kind="fact")
            continue

        # Per-scheme detail pages ("<n> September 2026 Index Page ... GROWW <name> (")
        if "Index Page" in flat[:40]:
            for key, s in SCHEMES.items():
                if any(f"{n} (" in flat for n in s["doc_names"]):
                    b.add_windows(text, scheme=key, page=i + 1)


def ingest_riskometer(b: Builder, path: Path) -> None:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    months = [c for c in rows[1] if hasattr(c, "strftime")]
    for r in rows[2:]:
        key = match_scheme(str(r[2] or "").strip())
        if not key:
            continue
        levels = [v for v in r[3:3 + len(months)] if v]
        if not levels:
            continue
        latest_month = months[len(levels) - 1].strftime("%B %Y")
        history = ", ".join(f"{m.strftime('%b %Y')}: {v}" for m, v in zip(months, levels))
        b.add(f"Riskometer level of {scheme_name(key)}: {levels[-1]} "
              f"(latest available, {latest_month}). Monthly riskometer levels: {history}.",
              scheme=key, kind="fact")


def ingest_web(b: Builder, path: Path) -> None:
    body = path.read_text(encoding="utf-8").split("\n---\n", 1)[-1]
    if "\nQ: " in "\n" + body:  # FAQ page: one chunk per question
        for qa in re.split(r"\n\s*\n", body.strip()):
            b.add(qa.replace("Q: ", "Question: ").replace("\nA: ", " Answer: "))
    else:
        b.add_windows(body)


INGESTERS = {
    "KIM": ingest_kim,
    "SID": ingest_sid,
    "Factsheet": ingest_factsheet,
    "Riskometer": ingest_riskometer,
}


def main() -> None:
    with open(DATA / "manifest.csv", newline="", encoding="utf-8") as f:
        manifest = list(csv.DictReader(f))

    all_chunks: list[Chunk] = []
    for entry in manifest:
        path = DATA / entry["file"]
        b = Builder(entry)
        INGESTERS.get(entry["doc_type"], ingest_web)(b, path)
        all_chunks.extend(b.chunks)
        facts = sum(c.kind == "fact" for c in b.chunks)
        print(f"{entry['source_id']}  {entry['title'][:48]:<48} {len(b.chunks):>4} chunks ({facts} facts)")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")
    returns = sum(c.has_returns for c in all_chunks)
    print(f"\nTotal {len(all_chunks)} chunks -> {OUT.relative_to(ROOT)} "
          f"({returns} flagged as containing returns)")


if __name__ == "__main__":
    main()
