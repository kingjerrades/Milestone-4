# Groww MF Facts — a facts-only mutual fund FAQ assistant

A small FAQ assistant that answers **factual** questions about mutual fund schemes
(expense ratio, exit load, minimum SIP, ELSS lock-in, riskometer, benchmark, how to
download statements) using **only official public pages**. Every answer is 2–3 sentences,
carries **one source link** and a "Last updated from sources" date. It gives **no advice**.

> **Facts-only. No investment advice.**

**Live app:** _link added after deployment_ · NextLeap PM Fellowship — Milestone 4

---

## Scope

| | |
|---|---|
| **AMC** | Groww Mutual Fund |
| **Schemes (4)** | Groww Large Cap Fund (large-cap) · Groww ELSS Tax Saver Fund (ELSS) · Groww Multicap Fund (stands in for flexi-cap; Groww MF has no flexi-cap scheme) · Groww Liquid Fund (debt, low-risk contrast) |
| **Sources** | 22 official URLs from Groww MF, AMFI and SEBI (plus KFintech, Groww MF's registrar, for the capital-gains statement page) — see [`sources.csv`](sources.csv) |
| **Questions answered** | expense ratio, exit load, minimum SIP / lumpsum, lock-in, riskometer, benchmark, fund manager, launch date, definitions, how to download CAS / capital-gains statements |
| **Questions refused** | advice ("should I buy?", "which is better?"), returns/performance, other fund houses, other Groww MF schemes, NAV, anything off-topic |

## Submission checklist

| Deliverable | Where |
|---|---|
| Working prototype | Live app link above · run locally with the steps below |
| Source list (22 URLs) | [`sources.csv`](sources.csv) |
| README (setup, scope, known limits) | this file |
| Sample Q&A (10 queries with answers + links) | [`sample_qa.md`](sample_qa.md) |
| Disclaimer used in the UI | [`disclaimer.md`](disclaimer.md) |
| Evaluation report (extra) | [`eval/report.md`](eval/report.md) |

## How it works

```
question
   │
   ▼
1. Router (rules)        personal details? → block (nothing stored)
   src/router.py         advice / returns / other fund / NAV / off-topic → polite refusal + 1 official link
                         fund-specific fact but no fund named → "Which scheme do you mean?"
   │
   ▼
2. AI double-check       Gemini Flash-Lite: "facts, advice, performance or other?"
   (only for questions   can only make the assistant MORE cautious, never less
   the rules would answer)
   │
   ▼
3. Retrieval             the scheme's official key-facts record first (factsheet / KIM / riskometer);
   src/search.py         then keyword search (BM25); optional meaning-based search (embeddings)
   src/answer.py
   │
   ▼
4. Answer                Gemini writes 2–3 plain-language sentences from the numbered excerpts
   src/answer.py         and says which excerpt it used
   │
   ▼
5. Checks                2–3 sentences · ≤70 words · every number appears in the cited excerpt ·
                         one document only · no links or advice words → else one retry, else a safe
                         "couldn't find it" reply with the official document
   │
   ▼
Answer + Source: <official link, taken from the excerpt's metadata, never written by the AI>
       + Last updated from sources: <date of that document>
```

Key design choices:
- **Citations can't be invented.** The link comes from the cited excerpt's metadata, not from the AI.
- **Structured facts first.** Tables (expense ratio, exit load, minimum SIP, riskometer) are rebuilt into one-line facts during ingestion, because plain PDF text loses which number belongs to which scheme. For core fact questions the AI sees *only* that official record.
- **Returns are filtered at the source.** 60 chunks that report returns are excluded from search, so performance figures can't be quoted even by accident.
- **Personal details never leave the router.** PAN, Aadhaar, phone, email, UPI ID, OTP, account/folio numbers and IFSC are detected by rules before any AI call; blocked messages are replaced by "Message hidden" on screen and are never logged.

## Run it locally

Requires Python 3.10+ and a free Gemini API key (Google AI Studio → *Get API key*, sign in with a Google account).

```bash
git clone https://github.com/kingjerrades/Milestone-4.git
cd Milestone-4
pip install -r requirements.txt
echo "GEMINI_API_KEY=your-key-here" > .env      # .env is git-ignored
streamlit run app.py
```

The search index (`data/processed/chunks.jsonl`) is committed, so the app runs without re-processing the documents. To rebuild it from the official files in `data/raw/`, install the extra tools first:

```bash
pip install -r requirements-dev.txt
python src/ingest.py
```

### Tests

```bash
python tests/router_test.py        # 126 answer/refuse/block decisions + reply lengths (no API calls)
python tests/search_smoke.py       # retrieval finds the right document and value (no API calls)
python tests/ai_check_test.py      # AI double-check on tricky advice questions (API calls)
python tests/evaluate.py           # full 37-question evaluation -> eval/report.md (API calls, ~8 min)
python tests/make_sample_qa.py     # rebuilds sample_qa.md from the evaluation results
```

## Deploy (Streamlit Community Cloud)

1. Sign in at [share.streamlit.io](https://share.streamlit.io) with GitHub.
2. **Create app** → repository `kingjerrades/Milestone-4`, branch `main`, main file `app.py`.
3. **Advanced settings** → Python 3.12, and under **Secrets** add:
   ```toml
   GEMINI_API_KEY = "your-key-here"
   ```
4. **Deploy.** The app uses about 120 MB of memory in its default keyword-search mode.

Optional settings (environment variables or secrets): `MF_ANSWER_MODEL`, `MF_CLASSIFIER_MODEL` (default `gemini-flash-lite-latest`), `MF_BACKUP_MODELS`, `MF_EMBEDDINGS=1` (adds meaning-based search; needs `requirements-dev.txt` and more memory than the free tier reliably gives), `MF_EMBED_TIMEOUT` (default 60 s).

## Evaluation

| Check | Final run |
|---|---|
| Right kind of reply (answer / refuse / block / clarify) | 37/37 |
| 2–3 sentences | 37/37 |
| One official link from `sources.csv` | 37/37 |
| "Last updated from sources" line | 37/37 |
| Correct value vs. the official documents | 25/25 |
| Every claim supported by the cited excerpt (AI judge) | 25/25 |

The first run scored **29/37**; fixes were made using this same set, so 29/37 is the fairer estimate for brand-new phrasing (3 of the 8 failures were Google free-tier "busy" errors, now retried with backup models). Details and per-question results: [`eval/report.md`](eval/report.md).

## Known limits

- **One AMC, four schemes.** Questions about other funds are politely declined.
- **Point-in-time data.** Facts come from the September 2026 factsheet and the KIM/SID dated 30 Oct 2026; expense ratios change monthly. Every answer shows the date its source is as of. No live NAV.
- **Conflicting official documents.** The Groww Multicap Fund SID gives two exit loads (1 year in its summary, 3 months in its Load Structure section). The assistant uses the factsheet's key-facts record (1 year).
- **Source typo.** The factsheet describes the ELSS fund as investing in "large equity"; the assistant answers only the fact asked, so this isn't repeated.
- **"Base" expense ratio.** Under the SEBI (Mutual Funds) Regulations, 2026, published figures are the base expense ratio; brokerage, transaction costs and GST are disclosed separately (AMFI). Answers say "base expense ratio".
- **Advice detection isn't perfect.** Rules alone caught about half of unusually phrased advice questions; the Gemini double-check caught 10/10 in testing. If Gemini is unreachable, the rules' decision stands.
- **Keyword search only (by default).** Meaning-based search is built but switched off: the evaluation was run in keyword mode, and turning all document chunks into vectors at startup exceeded Streamlit Cloud's free-tier memory (the first deployment was stopped for this). Unusual wording can therefore miss a passage; the topic hints and key-facts records offset most of this.
- **Free-tier limits.** Each answer uses two Gemini calls; heavy use can hit Google's per-minute limit (retries and backup models soften this). If the service is unavailable, the app says so honestly.
- **Web pages captured by hand.** Three web pages (AMFI Download CAS, AMFI TER explanation, KFintech capital-gains page) and the Groww MF FAQ were captured as text on 6–7 Nov 2026, because they render with JavaScript.
- **Capital-gains statement** comes from KFintech (Groww MF's registrar, linked from AMFI). The assistant only shows the link; it never asks for or accepts the PAN that page requires.
- **Grounding judge** uses the same model family as the answer writer; answers were also reviewed manually.

## Roadmap (v2, after submission)

- Add HDFC Mutual Fund and SBI Mutual Fund, and expand the schemes per AMC.
- Find an AMC- or AMFI-hosted capital-gains statement page.
- Refresh sources monthly (new factsheet) and show a data-freshness badge.

## Repository layout

```
app.py                 Streamlit UI
src/router.py          answer / refuse / block decisions (rules + AI double-check)
src/answer.py          retrieval, prompt, checks, citation
src/search.py          BM25 keyword search (+ optional embeddings)
src/ingest.py          PDFs / spreadsheet / web text -> tagged chunks
src/llm.py             minimal Gemini client (retries + backup models)
src/schemes.py         the 4 schemes and their aliases
src/disclaimer.py      disclaimer text (single source of truth)
src/text_utils.py      sentence counting, number extraction
data/raw/              the official documents (KIMs, SIDs, factsheet, riskometer, web text)
data/manifest.csv      file -> official URL, title, date
data/processed/        chunks.jsonl (the search index)
sources.csv            the 22 official source URLs
tests/                 router, search, AI-check and evaluation scripts
eval/                  evaluation results and report
```

---

*Facts-only. No investment advice. Mutual fund investments are subject to market risks; read all scheme-related documents carefully.*
