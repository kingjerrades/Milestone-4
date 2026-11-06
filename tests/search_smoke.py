"""Quick check that each question type retrieves the right source.

Run from the project root:  python tests/search_smoke.py
Each case lists the source_ids that would be a correct citation.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from search import Index  # noqa: E402

CASES = [
    ("What is the expense ratio of Groww Large Cap Fund?", "large_cap", {"S09"}, "1.18%"),
    ("Expense ratio of Groww Liquid Fund direct plan", "liquid", {"S09"}, "0.09%"),
    ("What is the lock-in period of Groww ELSS Tax Saver Fund?", "elss", {"S02", "S06", "S09"},
     "3 years"),
    ("Minimum SIP amount for Groww Multicap Fund", "multicap", {"S03"}, "Rs. 500"),
    ("Minimum SIP for Groww ELSS Tax Saver Fund", "elss", {"S02"}, "multiples of Rs. 500"),
    ("Exit load of Groww Liquid Fund", "liquid", {"S09", "S08", "S04"}, "0.0070%"),
    ("Exit load of Groww Large Cap Fund", "large_cap", {"S09", "S05", "S01"}, "7 Days"),
    ("Riskometer of Groww ELSS Tax Saver Fund", "elss", {"S10"}, "Very High"),
    ("Riskometer of Groww Liquid Fund", "liquid", {"S10"}, "Low to Moderate"),
    ("Benchmark of Groww Multicap Fund", "multicap", {"S09", "S03", "S07"}, "50:25:25"),
    ("Benchmark of Groww Large Cap Fund", "large_cap", {"S09", "S01", "S05"}, "NIFTY100"),
    ("How to download capital gains statement", None, {"S23"}),
    ("How do I download my consolidated account statement", None, {"S20"}),
    ("Difference between Groww and Groww Mutual Fund", None, {"S14"}),
]


def main() -> None:
    idx = Index.load()
    print(f"search mode: {idx.mode}, {len(idx.chunks)} chunks\n")
    passed = 0
    for question, scheme, good, *must in CASES:
        top = idx.search(question, scheme=scheme, k=3)
        ok = top and top[0].chunk["source_id"] in good
        if ok and must:  # the top chunk must also contain the actual fact
            ok = must[0].lower() in top[0].chunk["text"].lower()
        passed += bool(ok)
        c = top[0].chunk
        print(f"{'PASS' if ok else 'FAIL'}  {question}")
        print(f"      -> {c['id']} {c['doc_type']} p{c['page']}: {c['text'][:90]}")
    print(f"\n{passed}/{len(CASES)} passed")


if __name__ == "__main__":
    main()
