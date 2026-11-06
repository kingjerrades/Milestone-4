"""Phase 5 UI (dark "Night" design).  Run:  streamlit run app.py

Welcome line, three example questions, the disclaimer, and a chat. Each answer
shows one official source link and "Last updated from sources: <date>".

Privacy: questions are not logged or saved anywhere. If a message contains
personal details, it is replaced by a placeholder before it is kept on screen.
Everything shown inside the chat is HTML-escaped first.
"""

from __future__ import annotations

import csv
import html
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

EXAMPLES = [
    "What is the expense ratio of Groww Large Cap Fund?",
    "What is the lock-in period of Groww ELSS Tax Saver Fund?",
    "How do I download my capital gains statement?",
]
COVERS = ["Large Cap", "ELSS Tax Saver", "Multicap", "Liquid"]

# Small badge above replies that aren't plain answers.
BADGES = {"refuse_advice": "Facts only", "refuse_performance": "Facts only", "block_pii": "Privacy"}

ICON_DOC = ('<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#3DDC97" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 3h7l5 5v13H7z"/>'
            '<path d="M14 3v5h5"/></svg>')
ICON_SHIELD = ('<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
               'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
               '<path d="M12 3l8 3v6c0 4.5-3.4 8-8 9-4.6-1-8-4.5-8-9V6z"/></svg>')
ICON_LOCK = ('<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
             'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="11" width="14" '
             'height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>')

st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
      .stApp, .stApp p, .stApp button, .stApp input, .stApp textarea { font-family: Inter, system-ui, sans-serif; }
      [data-testid="stIconMaterial"] { font-family: "Material Symbols Rounded" !important; }
      .mf-top, .mf-covers, .mf-row, .mf-row *, .mf-welcome, .mf-try { font-family: Inter, system-ui, sans-serif !important; }
      .stApp { background: #0E1013; }
      header[data-testid="stHeader"] { background: transparent; }
      .block-container { max-width: 760px; padding-top: 3.5rem; padding-bottom: 7rem; }

      .mf-top { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
      .mf-brand { display: flex; align-items: center; gap: 10px; font-size: 17px; font-weight: 600; color: #E7E9EC; }
      .mf-dot { width: 10px; height: 10px; border-radius: 999px; background: #3DDC97; display: inline-block; }
      .mf-note { font-size: 13px; color: #A3AAB4; }
      .mf-covers { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; font-size: 12px;
                   color: #A3AAB4; margin: 14px 0 6px; }
      .mf-chip { background: #181B20; border: 1px solid #262A31; border-radius: 999px; padding: 4px 10px; color: #CDD2D8; }
      .mf-welcome { font-size: 15px !important; line-height: 1.6 !important; color: #CDD2D8; margin: 22px 0 6px !important; }
      .mf-try { font-size: 12px !important; color: #8B929C; margin: 16px 0 2px !important; }

      .mf-row { display: flex; margin: 16px 0; }
      .mf-row.user { justify-content: flex-end; }
      .mf-user { max-width: 78%; background: #17352A; color: #E6F4EE; border-radius: 18px 18px 4px 18px;
                 padding: 11px 16px; font-size: 15px; line-height: 1.5; overflow-wrap: anywhere; }
      .mf-user.hidden { display: flex; gap: 8px; align-items: center; font-style: italic; color: #B9D8CB; }
      .mf-bot { max-width: 86%; background: #171A1F; border: 1px solid #23272E; border-radius: 18px 18px 18px 4px;
                padding: 16px 18px; display: flex; flex-direction: column; gap: 12px; }
      .mf-bot p { margin: 0; font-size: 15px; line-height: 1.65; color: #E7E9EC; overflow-wrap: anywhere; }
      .mf-badge { display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 500; color: #3DDC97; }
      .mf-src { align-self: flex-start; display: inline-flex; align-items: center; gap: 8px; background: #20242B;
                border-radius: 999px; padding: 6px 12px; font-size: 12px; color: #CDD2D8 !important;
                text-decoration: none !important; }
      .mf-src:hover { background: #262B33; }
      .mf-updated { font-size: 12px; color: #8B929C; margin-top: -4px; }

      div[data-testid="stButton"] button { width: 100%; justify-content: flex-start; text-align: left;
          background: #13161A; color: #E7E9EC; border: 1px solid #262A31; border-radius: 14px;
          padding: 12px 16px; min-height: 48px; white-space: normal; height: auto; }
      div[data-testid="stButton"] button:hover { border-color: #3DDC97; color: #FFFFFF; }
      div[data-testid="stButton"] button p { font-size: 14px; }
      .st-key-clear div[data-testid="stButton"] button { width: auto; background: transparent; border: 0;
          color: #A3AAB4; min-height: 44px; padding: 8px 4px; }
      .st-key-clear div[data-testid="stButton"] button:hover { color: #E7E9EC; }

      [data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] { background: #0E1013; }
      [data-testid="stChatInput"] { background: #171A1F; border: 1px solid #2A2F37; border-radius: 28px; }
      [data-testid="stChatInput"] textarea { color: #E7E9EC; font-size: 15px; }
      [data-testid="stChatInputSubmitButton"] { background: #3DDC97 !important; color: #0E1013 !important;
          border-radius: 999px !important; }
      [data-testid="stExpander"] details { background: transparent; border: 1px solid #23272E; border-radius: 12px; }
      [data-testid="stExpander"] summary p { font-size: 13px; color: #A3AAB4; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner="Loading official documents…")
def load_index():
    return engine.get_index()


@st.cache_resource
def source_titles() -> dict[str, str]:
    """Official link -> page title, from sources.csv, so every link is named."""
    with open(Path(__file__).parent / "sources.csv", newline="", encoding="utf-8") as f:
        return {row["url"]: row["title"] for row in csv.DictReader(f)}


load_index()
esc = html.escape

# ---------------------------------------------------------------- header
chips = "".join(f'<span class="mf-chip">{c}</span>' for c in COVERS)
st.markdown(
    f'<div class="mf-top"><div class="mf-brand"><span class="mf-dot"></span>Groww MF Facts</div>'
    f'<div class="mf-note">{SHORT[:-1].replace(". ", " · ")}</div></div>'
    f'<div class="mf-covers"><span>Covers</span>{chips}</div>',
    unsafe_allow_html=True,
)

if "history" not in st.session_state:
    st.session_state.history = []  # [{"role", "text", "hidden", "link", "title", "updated", "kind"}]


def render(msg: dict) -> None:
    if msg["role"] == "user":
        if msg.get("hidden"):
            body = f'<div class="mf-user hidden">{ICON_LOCK}Message hidden because it contained personal details.</div>'
        else:
            body = f'<div class="mf-user">{esc(msg["text"])}</div>'
        st.markdown(f'<div class="mf-row user">{body}</div>', unsafe_allow_html=True)
        return
    badge = BADGES.get(msg.get("kind", ""))
    badge_html = f'<div class="mf-badge">{ICON_SHIELD}{badge}</div>' if badge else ""
    title = msg.get("title") or source_titles().get(msg["link"], "Official source")
    st.markdown(
        f'<div class="mf-row"><div class="mf-bot">{badge_html}<p>{esc(msg["text"])}</p>'
        f'<a class="mf-src" href="{esc(msg["link"], quote=True)}" target="_blank" rel="noopener">'
        f'{ICON_DOC}<span>{esc(title)}</span></a>'
        f'<div class="mf-updated">{esc(msg["updated"])}</div></div></div>',
        unsafe_allow_html=True,
    )


def ask(question: str) -> None:
    # Never keep personal details, even on screen.
    hidden = bool(find_pii(question))
    st.session_state.history.append({"role": "user", "text": "" if hidden else question, "hidden": hidden})
    with st.spinner("Checking official sources…"):
        a = engine.answer(question)
    st.session_state.history.append({
        "role": "assistant", "text": a.text, "link": a.link, "title": a.source_title,
        "updated": a.last_updated, "kind": a.kind,
    })


# ---------------------------------------------------------------- welcome / chat
if not st.session_state.history:
    st.markdown('<p class="mf-welcome">Hi! Ask me factual questions about these four Groww Mutual Fund '
                'schemes: expense ratio, exit load, minimum SIP, lock-in, riskometer, benchmark, or how '
                'to download your statements. Every answer links its official source.</p>'
                '<p class="mf-try">Try an example</p>', unsafe_allow_html=True)
    for i, q in enumerate(EXAMPLES):
        if st.button(q, key=f"ex{i}"):
            ask(q)
            st.rerun()

for msg in st.session_state.history:
    render(msg)

if st.session_state.history and st.button("Clear chat", key="clear"):
    st.session_state.history = []
    st.rerun()

with st.expander("About this assistant"):
    st.caption(FULL)
    mode = "keyword + meaning-based (hybrid)" if load_index().mode == "hybrid" else "keyword"
    st.caption(f"Search mode: {mode}")

if question := st.chat_input("Ask about a Groww MF scheme…"):
    ask(question)
    st.rerun()
