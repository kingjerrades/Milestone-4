"""Phase 4: turn a question into a short, cited, facts-only answer.

    from answer import answer
    a = answer("What is the exit load of Groww Liquid Fund?")
    print(a.text)      # 2-3 sentences, plain language
    print(a.link)      # one official source link
    print(a.as_of)     # "Last updated from sources: <date>"

Flow: router (rules + AI double-check) -> search -> Gemini writes the answer
from numbered source excerpts and says which excerpt it used -> checks:
  * 2 to 3 sentences
  * every number in the answer appears in the cited excerpt (no made-up figures)
  * no links or advice slipped into the text
If a check fails, Gemini gets one retry with the problem explained; if it still
fails, a safe "couldn't find it" reply with the scheme's official document is
returned instead. The link always comes from the excerpt's metadata, never
from the AI, so it can't be invented.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from llm import ANSWER_MODEL, LLMError, generate  # noqa: E402
from router import LINKS, Route, route_checked  # noqa: E402
from schemes import SCHEMES, scheme_name  # noqa: E402
from search import Index  # noqa: E402
from text_utils import MAX_SENTENCES, MIN_SENTENCES, count_sentences, numbers_in, split_sentences  # noqa: E402

CORPUS_DATE = "2026-11-06"  # when the web pages were captured; used for fixed replies
K = 5  # excerpts given to the model
MAX_WORDS = 70  # keeps 2-3 sentences genuinely short for beginners

# Each scheme's own key-facts document, used when an answer can't be found.
SCHEME_DOC = {
    "large_cap": "https://assets-netstorage.growwmf.in/compliance_docs/Downloads/KIM/Equity%20Funds/KIM_Groww%20Largecap%20Fund.pdf",
    "elss": "https://assets-netstorage.growwmf.in/compliance_docs/Downloads/KIM/Equity%20Funds/KIM_Groww%20ELSS%20Tax%20Saver%20Fund.pdf",
    "multicap": "https://assets-netstorage.growwmf.in/compliance_docs/Downloads/KIM/Equity%20Funds/KIM%20-%20Groww%20Multicap%20Fund.pdf",
    "liquid": "https://assets-netstorage.growwmf.in/compliance_docs/Downloads/KIM/Debt%20Funds/KIM_Groww%20Liquid%20Fund.pdf",
}

SYSTEM = f"""You are a facts-only FAQ assistant for Groww Mutual Fund schemes. Your readers
are beginners who may not know financial terms.

Answer the question using ONLY the numbered source excerpts provided.

Rules:
- Write {MIN_SENTENCES} or {MAX_SENTENCES} short sentences in total (never 1, never more than
  {MAX_SENTENCES}), and no more than {MAX_WORDS} words altogether.
- Sentence 1 states the exact fact asked, in your own plain words. Copy figures exactly
  (for expense ratios, give both Direct and Regular plan figures if both are shown).
  State only the fact that was asked: leave out other facts that share the same row or
  sentence in the excerpt (e.g. for a lock-in question, don't mention asset allocation).
- Sentence 2 (and optionally 3) does ONE of these:
  (a) explains the term in sentence 1 in simple, general words for a beginner
      (e.g. what a benchmark index or an exit load is), or
  (b) adds one closely related detail that is written in the excerpt.
  Never state anything else about the scheme or fund house (rules, rights, names, dates,
  conditions) unless it is written in the excerpt. Do not pad with filler.
- Rephrase document language: never copy table labels or legal phrases such as
  "TER, base expense ratio" or "in multiples of Re. 1/- thereafter".
- Summarise long tables instead of listing every row: give the main figure and the pattern
  (e.g. "0.0070% on day 1, falling daily to 0.0045% on day 6, and nil from day 7").
- Write amounts with the ₹ symbol (₹500), not "Rs.".
- Excerpts marked [KEY FACTS] are the fund house's current official record for that scheme.
  If excerpts disagree, use the [KEY FACTS] excerpt.
- Expense ratio figures in the factsheet are the "base expense ratio": call them that.
- If the question names no scheme (e.g. "What is an exit load?"), explain the term in general;
  do not answer with one particular scheme's figures.
- Use excerpts from only ONE document (the same title), and list the excerpt numbers you
  used in "sources". Usually that is one excerpt; a comparison may need two from the same document.
- Never give advice, opinions or judgements (no "good", "low", "worth it", "you should").
- Never mention returns or performance.
- Never include links or URLs; the app adds the source link itself.
- Never ask the user for personal details.
- If the excerpts do not contain the answer, reply with {{"answer": null, "sources": []}}.

Reply with JSON only: {{"answer": "<your 2-3 sentences>", "sources": [<excerpt numbers, e.g. 2>]}}"""


@dataclass
class Answer:
    text: str
    link: str
    source_title: str
    as_of: str                 # ISO date of the cited source
    route: Route
    kind: str                  # "answer", "not_found", or the router's action
    excerpt_id: str | None = None

    @property
    def last_updated(self) -> str:
        return f"Last updated from sources: {date.fromisoformat(self.as_of).strftime('%d %b %Y')}"


_index: Index | None = None


def get_index() -> Index:
    global _index
    if _index is None:
        _index = Index.load()
    return _index


# ---------------------------------------------------------------- retrieval

# For fund-specific facts, the scheme's structured key-facts record goes first.
# Long documents can disagree with each other (e.g. one SID section gives an
# older exit load); the factsheet's key facts are the fund house's current snapshot.
PIN = {
    "expense_ratio": ("Factsheet",), "exit_load": ("Factsheet",), "benchmark": ("Factsheet",),
    "fund_manager": ("Factsheet",), "about": ("Factsheet",), "lock_in": ("Factsheet",),
    "riskometer": ("Riskometer",), "min_sip": ("KIM",),
}

# Extra search words per topic, so everyday phrasing finds the right passage.
HINTS = {
    "lock_in": "lock-in period years", "about": "inception date type of scheme",
    "expense_ratio": "expense ratio", "exit_load": "exit load redeemed", "min_sip": "minimum SIP amount",
    "riskometer": "riskometer risk level", "benchmark": "benchmark index",
}


def pinned(r: Route) -> list[dict]:
    if r.topic not in PIN:
        return []
    doc_types = PIN[r.topic]
    idx = get_index()
    return [c for s in r.schemes for c in idx.chunks
            if c["kind"] == "fact" and c["scheme"] == s and c["doc_type"] in doc_types]


# Topics fully answered by the key-facts record: the model sees ONLY that record,
# so nothing from longer documents can leak into the answer.
KEY_ONLY = {"expense_ratio", "exit_load", "benchmark", "fund_manager", "riskometer", "min_sip"}


def retrieve(question: str, r: Route) -> list[dict]:
    first = pinned(r)
    key_only = r.topic in KEY_ONLY or (r.topic == "lock_in" and r.schemes == ["elss"])
    if first and key_only and len(first) == len(r.schemes):
        return first
    query = f"{question} {HINTS.get(r.topic, '')}".strip()
    rest = [c for c in _search(query, r) if c["id"] not in {p["id"] for p in first}]
    return (first + rest)[:K + len(first) - 1] if first else rest


def _search(question: str, r: Route) -> list[dict]:
    idx = get_index()
    if len(r.schemes) > 1:
        # Several funds: prefer excerpts that cover them all at once (factsheet
        # snapshot tables), so one source can answer the whole question.
        seen, hits = set(), []
        for s in r.schemes:
            for h in idx.search(question, scheme=s, k=K):
                if h.chunk["id"] not in seen:
                    seen.add(h.chunk["id"])
                    hits.append(h)
        hits.sort(key=lambda h: (h.chunk["doc_type"] == "Factsheet", h.score), reverse=True)
        return [h.chunk for h in hits[:K + 1]]
    scheme = r.schemes[0] if r.schemes else None
    return [h.chunk for h in idx.search(question, scheme=scheme, k=K)]


def format_context(chunks: list[dict]) -> str:
    blocks = []
    for i, c in enumerate(chunks, start=1):
        where = f", page {c['page']}" if c.get("page") else ""
        tag = " [KEY FACTS]" if c["kind"] == "fact" else ""
        blocks.append(f"[{i}]{tag} {c['title']} (as of {c['as_of']}{where})\n{c['text']}")
    return "\n\n".join(blocks)


# ---------------------------------------------------------------- checks

# Fixed, general second sentences, used only when an otherwise valid answer has
# 1 sentence after its retry. They state no scheme-specific facts.
EXPLAIN = {
    "expense_ratio": "An expense ratio is the yearly fee a fund charges, shown as a percentage of your investment.",
    "exit_load": "An exit load is a fee charged if you withdraw your money before a set period.",
    "min_sip": "A SIP lets you invest a fixed amount at regular intervals instead of all at once.",
    "lock_in": "During a lock-in period, units cannot be redeemed or switched out.",
    "riskometer": "The riskometer is a SEBI-mandated scale showing a scheme's risk level, from Low to Very High.",
    "benchmark": "A benchmark is the market index a fund measures itself against.",
    "fund_manager": "A fund manager is the professional who decides which investments the scheme buys and sells.",
    None: "The official document linked below has the full details.",
}

ADVICE_WORDS =r"\b(?:you should|we recommend|i recommend|good choice|worth it|better|best|ideal|great option)\b"


def problems_with(text: str, chunk: dict) -> list[str]:
    """Reasons an answer can't be shown as-is (empty list = fine)."""
    issues = []
    n = count_sentences(text)
    if n < MIN_SENTENCES or n > MAX_SENTENCES:
        issues.append(f"it has {n} sentence(s); it must have {MIN_SENTENCES} or {MAX_SENTENCES}")
    missing = numbers_in(text) - numbers_in(chunk["text"]) - numbers_in(chunk["title"])
    words = len(text.split())
    if words > MAX_WORDS:
        issues.append(f"it is {words} words long; keep it under {MAX_WORDS} by summarising")
    if missing:
        issues.append(f"these numbers are not in the excerpt: {', '.join(sorted(missing))}")
    if re.search(r"https?://|www\.", text):
        issues.append("it contains a link")
    if re.search(ADVICE_WORDS, text, re.I):
        issues.append("it contains advice or a judgement")
    return issues


def _first_cited(raw: str, chunks: list[dict]) -> dict | None:
    """The first excerpt an answer cited (used to steer a retry to one document)."""
    try:
        nums = [int(n) for n in re.findall(r"\d+", json.dumps(json.loads(raw).get("sources")))]
        return chunks[nums[0] - 1] if nums and 1 <= nums[0] <= len(chunks) else None
    except (ValueError, AttributeError):
        return None


def _parse(raw: str, chunks: list[dict]) -> tuple[str | None, dict | None]:
    """Returns the answer and ONE merged 'chunk' covering the excerpts it used.

    Excerpts must all come from the same document, so the answer still has
    exactly one source link.
    """
    data = json.loads(raw)
    text = data.get("answer")
    if not text:
        return None, None
    src = data.get("sources", data.get("source"))
    nums = [int(n) for n in re.findall(r"\d+", json.dumps(src))]
    if not nums or any(not 1 <= n <= len(chunks) for n in nums):
        raise ValueError(f"bad source numbers {src!r}")
    used = [chunks[n - 1] for n in dict.fromkeys(nums)]
    if len({c["url"] for c in used}) > 1:
        raise ValueError("answer mixes documents")
    merged = dict(used[0])
    merged["text"] = " ".join(c["text"] for c in used)
    merged["id"] = "+".join(c["id"] for c in used)
    merged["as_of"] = min(c["as_of"] for c in used)
    return text.strip(), merged


# ---------------------------------------------------------------- main

def _fixed(r: Route) -> Answer:
    return Answer(text=r.reply, link=r.link, source_title="", as_of=CORPUS_DATE,
                  route=r, kind=r.action)


def not_found(r: Route) -> Answer:
    scheme = r.schemes[0] if len(r.schemes) == 1 else None
    what = scheme_name(scheme) if scheme else "Groww Mutual Fund"
    text = (f"I couldn't find that in my official sources for {what}. "
            "The official document linked below has the full details.")
    link = SCHEME_DOC.get(scheme, LINKS["factsheet"])
    return Answer(text=text, link=link, source_title="", as_of=CORPUS_DATE, route=r, kind="not_found")


def unavailable(r: Route) -> Answer:
    """The AI service couldn't be reached: say so honestly, don't claim 'not found'."""
    scheme = r.schemes[0] if len(r.schemes) == 1 else None
    text = ("I couldn't reach my answer service just now, so please try again in a moment. "
            "Meanwhile, the official document linked below has the details.")
    return Answer(text=text, link=SCHEME_DOC.get(scheme, LINKS["factsheet"]), source_title="",
                  as_of=CORPUS_DATE, route=r, kind="unavailable")


def answer(question: str, use_ai_check: bool = True) -> Answer:
    r = route_checked(question, use_ai=use_ai_check)
    if not r.is_answer:
        return _fixed(r)

    chunks = retrieve(question, r)
    if not chunks:
        return not_found(r)

    prompt = f"Source excerpts:\n\n{format_context(chunks)}\n\nQuestion: {question}"
    feedback = ""
    for _attempt in range(2):
        try:
            raw = generate(prompt + feedback, system=SYSTEM, model=ANSWER_MODEL,
                           json_mode=True, max_tokens=400, timeout=20)
        except LLMError:
            return unavailable(r)
        try:
            text, chunk = _parse(raw, chunks)
        except json.JSONDecodeError:
            return not_found(r)
        except ValueError as e:  # e.g. combined two documents: retry naming the one to use
            text, chunk, issues = raw, None, [str(e)]
            first = _first_cited(raw, chunks)
            only = f'only excerpts from "{first["title"]}"' if first else "excerpts from only ONE document"
            feedback = (f"\n\nYour previous answer was: {raw}\n"
                        f"It can't be used because it {e}. Rewrite it using {only}, "
                        "and leave out anything that document doesn't say. "
                        f"Keep it to {MIN_SENTENCES} or {MAX_SENTENCES} sentences.")
            continue
        if text is None:
            return not_found(r)
        issues = problems_with(text, chunk)
        if not issues:
            return Answer(text=text, link=chunk["url"], source_title=chunk["title"],
                          as_of=chunk["as_of"], route=r, kind="answer", excerpt_id=chunk["id"])
        feedback = (f"\n\nYour previous answer was: {text}\n"
                    f"It can't be used because {'; and '.join(issues)}. Rewrite it following the rules "
                    f"(remember: {MIN_SENTENCES} or {MAX_SENTENCES} sentences).")

    # Second attempt still broke a rule. If the ONLY problem is the sentence
    # count, fix it safely: trim a long answer to 3 sentences, or add a fixed,
    # general explanation of the term to a 1-sentence answer. Otherwise play safe.
    if chunk is not None and issues and all("sentence" in i for i in issues):
        n = count_sentences(text)
        if n > MAX_SENTENCES:
            text = " ".join(split_sentences(text)[:MAX_SENTENCES])
        elif n < MIN_SENTENCES:
            text = f"{text.rstrip()} {EXPLAIN.get(r.topic, EXPLAIN[None])}"
        return Answer(text=text, link=chunk["url"], source_title=chunk["title"],
                      as_of=chunk["as_of"], route=r, kind="answer", excerpt_id=chunk["id"])
    return not_found(r)


if __name__ == "__main__":
    for q in sys.argv[1:] or ["What is the exit load of Groww Liquid Fund?"]:
        a = answer(q)
        print(f"\nQ: {q}\n[{a.kind} | {a.route.checked_by} | {a.excerpt_id}]\n{a.text}\n"
              f"Source: {a.source_title or 'official link'} — {a.link}\n{a.last_updated}")
