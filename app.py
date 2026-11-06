"""Phase 5: the tiny UI.  Run:  streamlit run app.py

Welcome line, three example questions, the disclaimer, and a chat. Each answer
shows one official source link and the date that source is as of.

Privacy: questions are not logged or saved anywhere. If a message contains
personal details, it is replaced by a placeholder before it is kept on screen.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))

st.set_page_config(page_title="Groww MF Facts", page_icon="📄", layout="centered")

# On Streamlit Cloud the key comes from the app's Secrets settings.
try:
    if "GEMINI_API_KEY" in st.secrets and not os.environ.get("GEMINI_API_KEY"):
        os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
except Exception:  # noqa: BLE001  (no secrets file locally: .env is used instead)
    pass

import answer as engine  # noqa: E402
from disclaimer import FULL, SHORT  # noqa: E402
from router import find_pii  # noqa: E402
from schemes import SCHEMES  # noqa: E402

def _source_titles() -> dict[str, str]:
    """Official link -> page title, from sources.csv, so every link is named."""
    import csv
    with open(Path(__file__).parent / "sources.csv", newline="", encoding="utf-8") as f:
        return {row["url"]: row["title"] for row in csv.DictReader(f)}


SOURCE_TITLES = _source_titles()

EXAMPLES = [
    "What is the expense ratio of Groww Large Cap Fund?",
    "What is the lock-in period of Groww ELSS Tax Saver Fund?",
    "How do I download my capital gains statement?",
]

st.markdown(
    """
    <style>
      .block-container { padding-top: 2.2rem; max-width: 760px; }
      .disclaimer { background: rgba(0,179,134,.10); border-left: 4px solid #00b386;
                    padding: .6rem .9rem; border-radius: 6px; margin: .4rem 0 1rem;
                    font-size: .95rem; }
      .meta { font-size: .82rem; opacity: .75; margin-top: .35rem; line-height: 1.5; }
      .meta a { text-decoration: none; }
      div[data-testid="stButton"] button { text-align: left; width: 100%;
                    white-space: normal; height: auto; padding: .55rem .8rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner="Loading official documents…")
def load_index():
    return engine.get_index()


load_index()

# ---------------------------------------------------------------- header
st.title("Groww MF Facts")
st.write("Hi! Ask me factual questions about four Groww Mutual Fund schemes — "
         "expense ratio, exit load, minimum SIP, lock-in, riskometer, benchmark, or how to "
         "download your statements.")
st.markdown(f'<div class="disclaimer"><b>{SHORT}</b> Every answer links its official source.</div>',
            unsafe_allow_html=True)

with st.expander("What this assistant covers"):
    st.markdown("**Schemes:** " + ", ".join(s["name"] for s in SCHEMES.values()))
    st.markdown("**Sources:** official Groww Mutual Fund documents (scheme summaries, "
                "scheme rulebooks, monthly factsheet, riskometer disclosures), AMFI and SEBI pages.")
    st.caption(FULL)

# ---------------------------------------------------------------- chat state
if "history" not in st.session_state:
    st.session_state.history = []  # [{"role", "text", "link", "title", "updated"}]


def render(msg: dict) -> None:
    with st.chat_message(msg["role"], avatar="🧑" if msg["role"] == "user" else "📄"):
        st.markdown(msg["text"])
        if msg.get("link"):
            title = msg.get("title") or SOURCE_TITLES.get(msg["link"], "Official source")
            st.markdown(
                f'<div class="meta">Source: <a href="{msg["link"]}" target="_blank">{title}</a>'
                f'<br>{msg["updated"]}</div>',
                unsafe_allow_html=True,
            )


def ask(question: str) -> None:
    # Never keep personal details, even on screen.
    shown = "🔒 *Message hidden because it contained personal details.*" if find_pii(question) else question
    st.session_state.history.append({"role": "user", "text": shown})
    with st.spinner("Checking official sources…"):
        a = engine.answer(question)
    st.session_state.history.append({
        "role": "assistant", "text": a.text, "link": a.link,
        "title": a.source_title, "updated": a.last_updated,
    })


# ---------------------------------------------------------------- examples
if not st.session_state.history:
    st.caption("Try an example:")
    for i, q in enumerate(EXAMPLES):
        if st.button(q, key=f"ex{i}"):
            ask(q)
            st.rerun()

for msg in st.session_state.history:
    render(msg)

if question := st.chat_input("Ask a factual question about a Groww MF scheme"):
    ask(question)
    st.rerun()

if st.session_state.history:
    if st.button("Clear chat", key="clear"):
        st.session_state.history = []
        st.rerun()
