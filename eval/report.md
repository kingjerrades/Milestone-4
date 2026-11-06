# Evaluation report

37/37 questions passed every check.

| Check | Passed |
|---|---|
| kind | 37/37 |
| sentences_2_3 | 37/37 |
| official_link | 37/37 |
| last_updated | 37/37 |
| gold_value | 25/25 |
| grounded | 25/25 |

## All questions

| # | Question | Expected | Got | Pass |
|---|---|---|---|---|
| 1 | What is the expense ratio of Groww Large Cap Fund? | answer | answer | ✅ |
| 2 | Expense ratio of Groww ELSS Tax Saver Fund? | answer | answer | ✅ |
| 3 | What is the TER of Groww Multicap Fund? | answer | answer | ✅ |
| 4 | Expense ratio of Groww Liquid Fund | answer | answer | ✅ |
| 5 | Exit load of Groww Large Cap Fund? | answer | answer | ✅ |
| 6 | What is the exit load on Groww Multicap Fund? | answer | answer | ✅ |
| 7 | Does Groww ELSS Tax Saver Fund have an exit load? | answer | answer | ✅ |
| 8 | Exit load of Groww Liquid Fund | answer | answer | ✅ |
| 9 | Minimum SIP for Groww Large Cap Fund? | answer | answer | ✅ |
| 10 | What is the minimum SIP amount for Groww ELSS Tax Saver Fund? | answer | answer | ✅ |
| 11 | Minimum SIP for Groww Liquid Fund | answer | answer | ✅ |
| 12 | What is the lock-in period of Groww ELSS Tax Saver Fund? | answer | answer | ✅ |
| 13 | can i take out money from groww elss after 6 months | answer | answer | ✅ |
| 14 | Riskometer level of Groww Large Cap Fund | answer | answer | ✅ |
| 15 | How risky is Groww Liquid Fund as per its riskometer? | answer | answer | ✅ |
| 16 | What is the benchmark of Groww ELSS Tax Saver Fund? | answer | answer | ✅ |
| 17 | Benchmark index of Groww Liquid Fund? | answer | answer | ✅ |
| 18 | What index is Groww Large Cap Fund benchmarked against? | answer | answer | ✅ |
| 19 | Who manages Groww Liquid Fund? | answer | answer | ✅ |
| 20 | When was Groww Multicap Fund launched? | answer | answer | ✅ |
| 21 | How do I download my capital gains statement? | answer | answer | ✅ |
| 22 | How can I get a consolidated account statement for my mutual funds? | answer | answer | ✅ |
| 23 | What is an expense ratio? | answer | answer | ✅ |
| 24 | how much does the tax saver fund charge me every year | answer | answer | ✅ |
| 25 | Expense ratio of Groww ELSS Tax Saver Fund and Groww Liquid Fund | answer | answer | ✅ |
| 26 | Should I invest in Groww Multicap Fund? | refuse_advice | refuse_advice | ✅ |
| 27 | Which is safer, Groww Liquid Fund or Groww Large Cap Fund? | refuse_advice | refuse_advice | ✅ |
| 28 | Is 0.83% a good expense ratio? | refuse_advice | refuse_advice | ✅ |
| 29 | What returns has Groww ELSS Tax Saver Fund given in 5 years? | refuse_performance | refuse_performance | ✅ |
| 30 | How much will 10000 in Groww Large Cap become in 3 years? | refuse_performance | refuse_performance | ✅ |
| 31 | My Aadhaar is 1234 5678 9012, show my holdings | block_pii | block_pii | ✅ |
| 32 | Send the statement to king@example.com | block_pii | block_pii | ✅ |
| 33 | What is the exit load of Axis Bluechip Fund? | other_amc | other_amc | ✅ |
| 34 | Expense ratio of Groww Small Cap Fund | other_scheme | other_scheme | ✅ |
| 35 | What is the minimum SIP? | clarify | clarify | ✅ |
| 36 | What is today's NAV of Groww Liquid Fund? | nav | nav | ✅ |
| 37 | Can you book me a cab? | out_of_scope | out_of_scope | ✅ |

## How to read these numbers

- **Run history:** 29/37 on the first run, 36/37 after fixes, 37/37 on the final run. The fixes were driven by this same set, so 37/37 overstates performance on brand-new questions; the first run (29/37) is the fairer estimate for unseen phrasing. Of its 8 failures, 3 were Google free-tier "busy" errors (now retried, with backup models), not wrong answers.
- **Grounding** is judged by a separate Gemini call that reads the answer next to its cited excerpt. It is the same model family as the answer writer, so it is a useful check, not an independent proof; the answers were also read manually.
- **Router** (answer vs. refuse) is tested separately on 126 cases in `tests/router_test.py`, including three rounds of phrasings first tried unseen.

## Findings about the official sources

- **Conflicting exit load (Groww Multicap Fund):** the SID (30 Oct 2026) states "1% within 1 year" in its summary but "1% within 3 months" in its Load Structure section; the factsheet (30 Sep 2026) says 1 year. The assistant uses the factsheet's key-facts record.
- **Likely typo:** the factsheet's ELSS column reads "Min 80% of total assets in large equity"; the assistant answers only the fact asked (the 3-year lock-in), so this isn't repeated.
- **Expense ratio wording:** under the SEBI (Mutual Funds) Regulations, 2026, published figures are the *base* expense ratio; brokerage, transaction costs and statutory levies (GST) are disclosed separately (AMFI). Answers call it the base expense ratio.
