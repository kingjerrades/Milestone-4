"""Build sample_qa.md from the evaluation results (real outputs, every check passed).

Run from the project root after tests/evaluate.py:  python tests/make_sample_qa.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PICKS = [
    "What is the expense ratio of Groww Large Cap Fund?",
    "Exit load of Groww Liquid Fund",
    "What is the minimum SIP amount for Groww ELSS Tax Saver Fund?",
    "What is the lock-in period of Groww ELSS Tax Saver Fund?",
    "How risky is Groww Liquid Fund as per its riskometer?",
    "What is the benchmark of Groww ELSS Tax Saver Fund?",
    "How do I download my capital gains statement?",
    "Should I invest in Groww Multicap Fund?",
    "What returns has Groww ELSS Tax Saver Fund given in 5 years?",
    "My Aadhaar is 1234 5678 9012, show my holdings",
]


def main() -> None:
    import csv
    titles = {row["url"]: row["title"] for row in csv.DictReader(open(ROOT / "sources.csv", encoding="utf-8"))}
    results = {r["question"]: r for r in json.loads((ROOT / "eval/results.json").read_text())}
    lines = ["# Sample Q&A", "",
             "Real outputs from the assistant (Groww Mutual Fund; 4 schemes), copied from the "
             "evaluation run. Every answer is 2–3 sentences with one official source link.", ""]
    n = 0
    for q in PICKS:
        r = results.get(q)
        if not r or not r["pass"]:
            print(f"skipped (missing or failed): {q}")
            continue
        n += 1
        shown_q = "My Aadhaar is [12-digit number], show my holdings" if "Aadhaar" in q else q
        label = {"answer": "Factual answer", "refuse_advice": "Refusal — advice",
                 "refuse_performance": "Refusal — returns", "block_pii": "Blocked — personal details"
                 }.get(r["got"], r["got"])
        lines += [f"### {n}. {shown_q}", f"*{label}*", "", f"> {r['answer']}", ">",
                  f"> **Source:** [{titles.get(r['link']) or r['source']}]({r['link']})  ",
                  f"> {r['last_updated']}", ""]
    (ROOT / "sample_qa.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote sample_qa.md with {n} questions")


if __name__ == "__main__":
    main()
