"""Phase 6: run the evaluation set end to end (makes real API calls).

Run from the project root:  python tests/evaluate.py
Writes eval/results.json and eval/report.md.

Checks for every reply:          and for fact answers also:
  1. right kind of reply           5. contains the gold value(s)
  2. 2-3 sentences                 6. grounded: an AI judge confirms every
  3. one official link (sources.csv)  claim is supported by the cited excerpt
  4. "Last updated from sources" line  (general definitions are allowed)
"""

from __future__ import annotations

import csv
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))
from answer import answer  # noqa: E402
from eval_set import CASES  # noqa: E402
from llm import CLASSIFIER_MODEL, LLMError, generate  # noqa: E402
from text_utils import count_sentences  # noqa: E402

PAUSE = 12  # 3 API calls per fact question; stays under the free tier's per-minute limit

JUDGE = """You check a mutual fund FAQ answer against its source excerpt.
An answer is SUPPORTED if every specific claim about the scheme or fund house
(figures, names, dates, rules, conditions) is stated in the excerpt.
General explanations of a financial term (e.g. "an exit load is a fee for redeeming early")
are allowed even if not in the excerpt, as long as they are accurate and generic.
Reply with JSON only: {"supported": true/false, "unsupported_claims": ["..."]}"""


def load_chunks() -> dict[str, dict]:
    with open(ROOT / "data/processed/chunks.jsonl", encoding="utf-8") as f:
        return {c["id"]: c for c in map(json.loads, f)}


def judge(answer_text: str, excerpt: str) -> tuple[bool | None, list[str]]:
    prompt = f"Source excerpt:\n{excerpt}\n\nAnswer to check:\n{answer_text}"
    try:
        raw = generate(prompt, system=JUDGE, model=CLASSIFIER_MODEL, json_mode=True,
                       max_tokens=200, timeout=20)
        data = json.loads(raw)
        return bool(data.get("supported")), list(data.get("unsupported_claims") or [])
    except (LLMError, ValueError):
        return None, ["judge unavailable"]


def matches(text: str, groups: list[list[str]]) -> list[str]:
    low = text.lower()
    return [" / ".join(g) for g in groups if not any(alt.lower() in low for alt in g)]


def main() -> None:
    official = {r["url"] for r in csv.DictReader(open(ROOT / "sources.csv", encoding="utf-8"))}
    chunks = load_chunks()
    results = []
    for i, (q, kind, gold) in enumerate(CASES, 1):
        a = answer(q)
        checks = {
            "kind": a.kind == kind,
            "sentences_2_3": 2 <= count_sentences(a.text) <= 3,
            "official_link": a.link in official and not re.search(r"https?://", a.text),
            "last_updated": bool(re.match(r"Last updated from sources: \d{2} \w{3} \d{4}$", a.last_updated)),
        }
        missing, supported, unsupported = [], None, []
        if kind == "answer" and a.kind == "answer":
            missing = matches(a.text, gold)
            checks["gold_value"] = not missing
            excerpt = " ".join(chunks[c]["text"] for c in a.excerpt_id.split("+"))
            supported, unsupported = judge(a.text, excerpt)
            checks["grounded"] = bool(supported)
        elif kind == "answer":
            checks["gold_value"] = False
            checks["grounded"] = False
        ok = all(checks.values())
        results.append({
            "question": q, "expected": kind, "got": a.kind, "answer": a.text,
            "source": a.source_title or a.link, "link": a.link, "last_updated": a.last_updated,
            "excerpt": a.excerpt_id, "checked_by": a.route.checked_by, "checks": checks,
            "missing_gold": missing, "unsupported_claims": unsupported, "pass": ok,
        })
        flags = ", ".join(k for k, v in checks.items() if not v)
        print(f"{i:>2} {'PASS' if ok else 'FAIL'}  {q}" + (f"   <- {flags}" if flags else ""), flush=True)
        if not ok:
            print(f"      {a.text}")
            if unsupported:
                print(f"      unsupported: {unsupported}")
        time.sleep(PAUSE if kind == "answer" else 2)

    out = ROOT / "eval"
    out.mkdir(exist_ok=True)
    (out / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    write_report(results, out / "report.md")
    passed = sum(r["pass"] for r in results)
    print(f"\n{passed}/{len(results)} passed -> eval/report.md")


def write_report(results: list[dict], path: Path) -> None:
    names = ["kind", "sentences_2_3", "official_link", "last_updated", "gold_value", "grounded"]
    lines = ["# Evaluation report", "",
             f"{sum(r['pass'] for r in results)}/{len(results)} questions passed every check.", "",
             "| Check | Passed |", "|---|---|"]
    for n in names:
        applicable = [r for r in results if n in r["checks"]]
        lines.append(f"| {n} | {sum(r['checks'][n] for r in applicable)}/{len(applicable)} |")
    lines += ["", "## All questions", "", "| # | Question | Expected | Got | Pass |", "|---|---|---|---|---|"]
    for i, r in enumerate(results, 1):
        lines.append(f"| {i} | {r['question']} | {r['expected']} | {r['got']} | {'✅' if r['pass'] else '❌'} |")
    fails = [r for r in results if not r["pass"]]
    if fails:
        lines += ["", "## Failures", ""]
        for r in fails:
            bad = [k for k, v in r["checks"].items() if not v]
            lines += [f"**{r['question']}** — failed: {', '.join(bad)}", "", f"> {r['answer']}", ""]
            if r["unsupported_claims"]:
                lines += [f"Unsupported: {'; '.join(r['unsupported_claims'])}", ""]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
