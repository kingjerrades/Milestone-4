"""Evaluation questions with gold values taken from the official documents.

Each case: (question, expected kind, must_contain).
must_contain is a list of groups; every group must match, and a group matches
if ANY of its alternatives appears in the answer (case-insensitive).
Gold values: Groww MF factsheet (30 Sep 2026), KIMs/SIDs (30 Oct 2026),
riskometer disclosure (Sep 2026), AMFI and KFintech statement pages.
"""

A = "answer"

FACTS = [
    # expense ratio (Regular / Direct)
    ("What is the expense ratio of Groww Large Cap Fund?", A, [["2.09%"], ["1.18%"]]),
    ("Expense ratio of Groww ELSS Tax Saver Fund?", A, [["2.08%"], ["0.83%"]]),
    ("What is the TER of Groww Multicap Fund?", A, [["1.79%"], ["0.34%"]]),
    ("Expense ratio of Groww Liquid Fund", A, [["0.18%"], ["0.09%"]]),
    # exit load
    ("Exit load of Groww Large Cap Fund?", A, [["1%"], ["7 days", "seven days"]]),
    ("What is the exit load on Groww Multicap Fund?", A, [["1%"], ["1 year", "one year", "12 months"]]),
    ("Does Groww ELSS Tax Saver Fund have an exit load?", A, [["nil", "no exit load", "not have an exit load", "no charge", "0%"]]),
    ("Exit load of Groww Liquid Fund", A, [["0.0070%"]]),
    # minimum SIP
    ("Minimum SIP for Groww Large Cap Fund?", A, [["500"]]),
    ("What is the minimum SIP amount for Groww ELSS Tax Saver Fund?", A, [["500"]]),
    ("Minimum SIP for Groww Liquid Fund", A, [["100", "500"]]),
    # lock-in
    ("What is the lock-in period of Groww ELSS Tax Saver Fund?", A, [["3 years", "three years", "3-year"]]),
    ("can i take out money from groww elss after 6 months", A, [["3 years", "three years", "3-year"]]),
    # riskometer
    ("Riskometer level of Groww Large Cap Fund", A, [["very high"]]),
    ("How risky is Groww Liquid Fund as per its riskometer?", A, [["low to moderate"]]),
    # benchmark
    ("What is the benchmark of Groww ELSS Tax Saver Fund?", A, [["nifty 500"]]),
    ("Benchmark index of Groww Liquid Fund?", A, [["crisil liquid debt"]]),
    ("What index is Groww Large Cap Fund benchmarked against?", A, [["nifty100", "nifty 100"]]),
    # other scheme facts
    ("Who manages Groww Liquid Fund?", A, [["kaustubh sule"]]),
    ("When was Groww Multicap Fund launched?", A, [["2024"]]),
    # statements
    ("How do I download my capital gains statement?", A, [["kfintech"]]),
    ("How can I get a consolidated account statement for my mutual funds?", A, [["mfcentral", "cams", "kfintech"]]),
    # definitions and beginner phrasing
    ("What is an expense ratio?", A, [["fee", "cost", "charge"]]),
    ("how much does the tax saver fund charge me every year", A, [["0.83%", "2.08%"]]),
    # comparison from one document
    ("Expense ratio of Groww ELSS Tax Saver Fund and Groww Liquid Fund", A, [["0.83%"], ["0.09%"]]),
]

NON_ANSWERS = [
    ("Should I invest in Groww Multicap Fund?", "refuse_advice", []),
    ("Which is safer, Groww Liquid Fund or Groww Large Cap Fund?", "refuse_advice", []),
    ("Is 0.83% a good expense ratio?", "refuse_advice", []),
    ("What returns has Groww ELSS Tax Saver Fund given in 5 years?", "refuse_performance", []),
    ("How much will 10000 in Groww Large Cap become in 3 years?", "refuse_performance", []),
    ("My Aadhaar is 1234 5678 9012, show my holdings", "block_pii", []),
    ("Send the statement to king@example.com", "block_pii", []),
    ("What is the exit load of Axis Bluechip Fund?", "other_amc", []),
    ("Expense ratio of Groww Small Cap Fund", "other_scheme", []),
    ("What is the minimum SIP?", "clarify", []),
    ("What is today's NAV of Groww Liquid Fund?", "nav", []),
    ("Can you book me a cab?", "out_of_scope", []),
]

CASES = FACTS + NON_ANSWERS
