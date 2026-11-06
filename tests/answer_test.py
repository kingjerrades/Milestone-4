"""End-to-end check of full answers (needs GEMINI_API_KEY; makes real API calls).

Run from the project root:  python tests/answer_test.py
For every reply, including refusals, it checks the brief's rules:
  * 2 to 3 sentences      * exactly one link, and it is in sources.csv
  * a "Last updated from sources" date
and, for factual questions, that the answer contains the correct value.
"""

import csv
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from answer import answer  # noqa: E402
from text_utils import count_sentences  # noqa: E402

PAUSE = 9  # two API calls per question; stays under the free tier's per-minute limit

CASES = [
    # (question, expected kind, text the answer must contain)
    ("What is the expense ratio of Groww Large Cap Fund?", "answer", "1.18%"),
    ("ELSS lock-in?", "answer", "3 years"),
    ("Minimum SIP for Groww Multicap Fund?", "answer", "500"),
    ("Exit load of Groww Liquid Fund", "answer", "0.0070%"),
    ("Riskometer of Groww ELSS Tax Saver Fund", "answer", "very high"),
    ("Benchmark of Groww Multicap Fund", "answer", "50:25:25"),
    ("How do I download my capital gains statement?", "answer", "kfintech"),
    ("How can I download my consolidated account statement?", "answer", "statement"),
    ("Expense ratio of Groww Large Cap and Groww Multicap", "answer", "0.34%"),
    ("Should I buy Groww ELSS Tax Saver Fund?", "refuse_advice", None),
    ("What are the 3 year returns of Groww Multicap Fund?", "refuse_performance", None),
    ("My PAN is ABCDE1234F", "block_pii", None),
    ("Exit load?", "clarify", None),
]


def main() -> None:
    with open(ROOT / "sources.csv", newline="", encoding="utf-8") as f:
        official = {row["url"] for row in csv.DictReader(f)}
    # Scheme documents and refusal links are also official (KIMs, factsheet, SEBI, AMFI, Groww MF).
    failed = 0
    for q, kind, must in CASES:
        a = answer(q)
        issues = []
        n = count_sentences(a.text)
        if not 2 <= n <= 3:
            issues.append(f"{n} sentences")
        if a.kind != kind:
            issues.append(f"kind={a.kind}")
        if a.link not in official:
            issues.append("link not in sources.csv")
        if re.search(r"https?://", a.text):
            issues.append("link inside the text")
        if not re.match(r"Last updated from sources: \d{2} \w{3} \d{4}$", a.last_updated):
            issues.append("bad last-updated line")
        if must and must.lower() not in a.text.lower():
            issues.append(f"missing {must!r}")
        failed += bool(issues)
        print(f"{'PASS' if not issues else 'FAIL'}  ({n} sent.) {q}" + (f"  -> {', '.join(issues)}" if issues else ""))
        print(f"      {a.text}")
        time.sleep(PAUSE if a.kind == "answer" else 1)
    print(f"\n{len(CASES) - failed}/{len(CASES)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
