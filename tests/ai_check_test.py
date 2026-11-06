"""Checks the AI double-check (needs GEMINI_API_KEY; makes real API calls).

Run from the project root:  python tests/ai_check_test.py
Part 1: advice/returns questions written so the rules MISS them.
Part 2: every factual question in router_test.py must still be answered
        (the AI must not refuse genuine fact questions).
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from router import route, route_checked  # noqa: E402
from router_test import CASES  # noqa: E402

PAUSE = 4.5  # seconds between calls: stays under the free tier's per-minute limit

SLIP_PAST_RULES = [
    ("my uncle says groww elss is a waste of money, is he right", "refuse_advice"),
    ("i'm 25, put everything in multicap?", "refuse_advice"),
    ("liquid fund vs savings account, thoughts", "refuse_advice"),
    ("go with groww large cap, yes or no", "refuse_advice"),
    ("would a smart investor pick the multicap", "refuse_advice"),
    ("is groww elss a smart move this year", "refuse_advice"),
    ("is groww large cap fund overpriced at 2% expense", "refuse_advice"),
    ("can groww multicap make me rich", "refuse_performance"),
    ("what did 5000 a month in groww elss turn into", "refuse_performance"),
    ("is groww liquid fund giving more than 7% now", "refuse_performance"),
]


def main() -> None:
    misses = 0

    print("Part 1: advice/returns the rules miss")
    for q, expected in SLIP_PAST_RULES:
        rules_only = route(q).action
        r = route_checked(q)
        # Either refusal is safe ("can it make me rich?" is fairly read as advice or returns).
        ok = r.action in ("refuse_advice", "refuse_performance")
        misses += not ok
        print(f"  {'PASS' if ok else 'FAIL'}  rules={rules_only:<18} +ai={r.action:<18} [{r.checked_by}]  {q}")
        time.sleep(PAUSE)

    print("\nPart 2: fact questions must still be answered")
    facts = [] if "--quick" in sys.argv else [q for q, action, *_ in CASES if action == "answer"]
    over = 0
    for q in facts:
        r = route_checked(q)
        if r.action != "answer":
            over += 1
            print(f"  FAIL  refused a fact question ({r.action}, {r.checked_by}): {q}")
        elif r.checked_by != "rules+ai":
            print(f"  NOTE  AI not used ({r.checked_by}): {q}")
        time.sleep(PAUSE)
    misses += over

    caught = len(SLIP_PAST_RULES) - (misses - over)
    print(f"\nPart 1: {caught}/{len(SLIP_PAST_RULES)} caught   "
          f"Part 2: {len(facts) - over}/{len(facts)} facts still answered")
    sys.exit(1 if misses else 0)


if __name__ == "__main__":
    main()
