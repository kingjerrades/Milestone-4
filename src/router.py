"""Phase 3: decide what to do with a question before any search or AI step.

The router is plain rules, not an AI model, so its decisions are predictable,
testable and free. The answer prompt (Phase 4) also tells the model to refuse
advice, as a second layer of protection.

Checks run in this order; the first one that matches decides the outcome:

  1. empty / greeting          -> greet
  2. personal details (PII)    -> block (nothing is stored or logged)
  3. prompt-injection attempt  -> out_of_scope
  4. advice / opinion          -> refuse_advice   (link: SEBI investor site)
  5. returns / performance     -> refuse_performance (link: official factsheet)
  6. other fund house          -> out_of_scope    (link: AMFI expense ratio page)
  7. other Groww MF scheme     -> out_of_scope    (link: Groww MF website)
  8. NAV (daily price)         -> not_supported   (link: official factsheet)
  9. fund-specific fact, no fund named -> clarify
 10. nothing about mutual funds -> out_of_scope
 11. everything else           -> answer (handed to search + Phase 4)

    from router import route
    r = route("What is the exit load of Groww Liquid Fund?")
    r.action  # "answer"; r.schemes == ["liquid"]; r.topic == "exit_load"
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from schemes import SCHEMES  # noqa: E402

# ---------------------------------------------------------------- links
# Every reply carries one official link, refusals included (ids from sources.csv).
LINKS = {
    "factsheet": "https://assets-netstorage.growwmf.in/compliance_docs/Downloads/Fact%20Sheet/2026%20-%202027/Monthly%20Factsheet%20Sept%202026.pdf",  # S09
    "amfi_ter": "https://www.amfiindia.com/ter-of-mf-schemes",  # S12
    "growwmf_home": "https://www.growwmf.in/",  # S14
    "sebi_investor": "https://investor.sebi.gov.in/",  # S21
}

COVERED = "Groww Large Cap Fund, Groww ELSS Tax Saver Fund, Groww Multicap Fund and Groww Liquid Fund"

# ---------------------------------------------------------------- replies
# Plain language for beginners, 3 sentences or fewer.
REPLIES = {
    "greet": (
        "Hi! I answer factual questions about four Groww Mutual Fund schemes: " + COVERED + ". "
        "Ask me about expense ratio, exit load, minimum SIP, lock-in, riskometer, benchmark, "
        "or how to download your statements.",
        "growwmf_home",
    ),
    "block_pii": (
        "For your safety, please don't share personal details like PAN, Aadhaar, phone number, "
        "email, OTP or account numbers here. I haven't stored what you typed. "
        "Please ask your question again without those details.",
        "sebi_investor",
    ),
    "refuse_advice": (
        "I can only share facts, not investment advice, so I can't say whether to buy, sell, "
        "or which fund to pick. For personal guidance, consider a SEBI-registered investment "
        "adviser; SEBI's investor website explains the basics. I'm happy to share facts like a "
        "scheme's expense ratio, exit load or riskometer.",
        "sebi_investor",
    ),
    "refuse_performance": (
        "I don't share, calculate or compare returns, because performance figures need context "
        "that a short answer can't give. Each scheme's official performance figures are in Groww "
        "Mutual Fund's latest monthly factsheet.",
        "factsheet",
    ),
    "other_amc": (
        "I only cover four Groww Mutual Fund schemes: " + COVERED + ". "
        "For schemes from other fund houses, AMFI's website lists official expense ratios for "
        "every scheme.",
        "amfi_ter",
    ),
    "other_scheme": (
        "I only cover four Groww Mutual Fund schemes: " + COVERED + ". "
        "Official documents for Groww MF's other schemes are on its website.",
        "growwmf_home",
    ),
    "nav": (
        "A fund's NAV (its price per unit) changes every working day, so I don't quote it here. "
        "The latest monthly factsheet shows each scheme's NAV as on its date.",
        "factsheet",
    ),
    "clarify": (
        "Which scheme do you mean? I cover " + COVERED + ". "
        "For example: \"What is the exit load of Groww Liquid Fund?\"",
        "factsheet",
    ),
    "out_of_scope": (
        "I can only answer factual questions about four Groww Mutual Fund schemes, such as "
        "expense ratio, exit load, minimum SIP, lock-in, riskometer, benchmark, or how to "
        "download statements. For example: \"What is the lock-in period of Groww ELSS Tax Saver Fund?\"",
        "growwmf_home",
    ),
}

# ---------------------------------------------------------------- patterns

PII_PATTERNS = {
    "PAN": r"\b[a-z]{5}\d{4}[a-z]\b",
    "Aadhaar": r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)",
    "phone": r"(?<![\d.])(?:\+?91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}(?![\d.])",
    "email": r"[\w.+-]+@[\w-]+\.[a-z]{2,}",
    "UPI ID": r"\b[\w.-]{2,}@(?:ok\w+|ybl|paytm|upi|ibl|axl|apl|icici|sbi|hdfcbank)\b",
    "OTP": r"\b(?:otp|one[\s-]?time[\s-]?password|verification code|pin)\b\D{0,15}\d{4,8}\b",
    "account number": r"\b(?:account|a/c|acct|folio|demat|client id|dp id|card)\b\D{0,25}\d{6,18}\b",
    "IFSC": r"\b[a-z]{4}0[a-z0-9]{6}\b",
    "long number": r"(?<![\d.,₹])\d{9,18}(?![\d.,%])",
}

INJECTION = (
    r"ignore (?:all |any |the |your |previous |prior |above )*(?:instructions|rules|prompt)"
    r"|system prompt|you are now|pretend (?:to be|you)|jailbreak|developer mode|act as (?:a|an|my)"
)

ADVICE = [
    r"\b(?:should|shall)\b",
    r"\b(?:safest|safer|riskiest|riskier|cheapest|cheaper)\b",
    r"\bfor (?:the )?(?:long|short)[\s-]?term\b",
    r"\b(?:is )?(?:now|today) (?:a |the )?(?:good|right|best) time\b",
    r"\bdo you (?:recommend|suggest|think)\b",
    r"\b(?:recommend|suggest)\w*\b",
    r"\b(?:better|best|worst|ideal)\b",
    r"\btop (?:fund|scheme|pick|choice)s?\b",
    r"\bworth (?:it|investing|buying|the)\b",
    r"\bis (?:it|this|that) (?:a )?(?:good|bad|safe|wise|worth|right|ok|okay)\b",
    r"\bgood (?:fund|investment|option|choice|time|idea|scheme)\b",
    r"\b(?:buy|sell|exit|redeem|switch|stop|continue|hold)\b.{0,40}\b(?:now|today|or not|right now|this year)\b",
    r"\bwhich (?:fund|scheme|one|is)\b.{0,50}\b(?:invest|choose|pick|go for|buy|for me|prefer)\b",
    r"\b(?:my|your) portfolio\b",
    r"\b(?:allocate|allocation|diversif)\w*",
    r"\bhow much (?:should|to|can|do) (?:i|we) invest\b",
    r"\b(?:for me|right for|suitable|safe for)\b",
    r"\b(?:will|would) (?:it|the fund|the market|the nav|nav|my fund|prices?) (?:go up|go down|rise|fall|crash|increase|decrease)\b",
    r"\bwhere (?:to|should i|can i|do i) (?:put|park|invest|keep)\b",
    r"\brate (?:it|this|groww|the fund)\b|\bout of (?:10|ten|5|five)\b|\bopinion\b|\byour (?:view|take|thoughts)\b",
    r"\b(?:trust(?:worthy|ed)?|reliable|legit|scam|fraud)\b",
    r"\b(?:would|will|do) you (?:pick|choose|prefer|go for|buy|invest)\b",
]

# "Is 1% expense ratio high?" asks for a judgement. Risk-level questions
# ("Is the ELSS fund high risk?") are factual riskometer questions instead.
JUDGEMENT = r"\b(?:is|are)\b.{0,60}\b(?:high|low|expensive|cheap|reasonable|too much|fair|good|bad)\b"

PERFORMANCE = [
    r"(?<!tax )(?<!income tax )\breturns?\b(?! (?:form|filing))",
    r"\bperform\w*",
    r"\b(?:cagr|xirr|irr)\b",
    r"\bhow much (?:will|would|can|could|do|did|has|have)\b.{0,50}\b(?:earn|make|get|become|grow|gain|be worth)\b",
    r"\b(?:gain|gains|grew|became|gave)\b",
    r"\b(?:ytm|yield to maturity|annuali[sz]ed|absolute return)\b",
    r"\b(?:earn|earning|earnings|profit\w*|yield\w*)\b",
    r"\b(?:outperform\w*|underperform\w*|beat(?:s|en)? (?:the |its |their )?(?:benchmark|market|index|nifty|sensex))\b",
    r"\bpast performance\b",
    r"\b(?:sip )?calculator\b",
    r"\bdoubl(?:e|ing) (?:my )?money\b",
    r"\bguaranteed?\b",
]

OTHER_AMCS = (
    r"\b(?:hdfc|sbi|icici|axis|nippon|kotak|mirae|parag parikh|ppfas|quant|uti|aditya birla|"
    r"birla|tata|dsp|motilal|bandhan|franklin|templeton|edelweiss|canara|invesco|hsbc|"
    r"baroda|lic mf|union mf|sundaram|pgim|navi|zerodha|whiteoak|bajaj finserv|mahindra|"
    r"jm financial|iti mf|360 one|helios|samco|old bridge|trust mf)\b"
)

OTHER_GROWW_SCHEMES = (
    r"\b(?:small ?cap|mid ?cap|value fund|banking|financial services|index fund|etf|overnight|"
    r"money market|gilt|short term|short duration|dynamic|arbitrage|hybrid|aggressive|balanced|"
    r"gold|silver|momentum|railway|psu|defen[cs]e|fund of funds?|fof|total market|next 50|"
    r"consumption|multi asset|dividend yield|nifty 50 index|ev fund)\b"
)

# Topics in priority order: the first match is the primary topic.
TOPICS = [
    ("capital_gains", r"capital[\s-]?gains?|\bcg statement|tax (?:statement|report|proof)|statement for (?:tax|itr)"),
    ("statement", r"\bstatements?\b|\bcas\b|holding (?:report|summary)|transaction history"),
    ("lock_in", r"lock[\s-]?in|locked|\b80 ?c\b|tax[\s-]sav"),
    ("exit_load", r"exit load|\bexit\b|\bload\b|penalt|(?:withdraw|redeem)\w* (?:early|before)|redemption (?:charge|fee)"),
    ("expense_ratio", r"expense|\bter\b|\bfees?\b|\bcharges?\b|\bcosts?\b|commission"),
    ("min_sip", r"\bsip\b|minimum|\bmin\b|lump ?sum|(?:smallest|least|lowest)\b.{0,20}\bamount|start (?:with|investing)"),
    ("riskometer", r"\brisk"),
    ("benchmark", r"benchmark|index (?:it|does it) (?:track|follow)|compared? against"),
    ("nav", r"\bnav\b"),
    ("fund_manager", r"fund manager|who manages|managed by"),
    ("about", r"inception|launch|objective|\baum\b|type of (?:scheme|fund)|category|invests? in|what kind"),
]

# Topics that only make sense for a specific scheme.
SCHEME_SPECIFIC = {"expense_ratio", "exit_load", "min_sip", "riskometer", "benchmark", "fund_manager", "about"}

# "What is an expense ratio?" asks for a definition; "What is THE expense ratio?" or
# "What is the minimum SIP?" asks for a scheme's value, so it needs a scheme named.
DEFINITION = (
    r"^(?:what|whats|what's)\s+(?:is|are)\s+(?!the\b|its\b|their\b)"
    r"|^what (?:does|do)\b|\b(?:meaning|mean|define|definition|explain|difference between)\b"
)
VALUE_WORDS = r"\b(?:minimum|min|amount|level|current|latest|how much|how many)\b"

# For ELSS, "can I take my money out after 6 months?" is a lock-in question.
WITHDRAWAL = r"\b(?:take (?:my |the )?(?:money )?out|withdraw|redeem|sell|cash out|get (?:my )?money)\b"

MF_WORDS = (
    r"mutual fund|\bfunds?\b|\bschemes?\b|\bsip\b|\bnav\b|\bamc\b|groww|invest|\bunits?\b|folio|"
    r"\belss\b|expense|exit load|riskometer|benchmark|statement|\bcas\b|direct plan|regular plan|kyc|redeem|redemption"
)

GREETING = r"^(?:hi+|hello|hey|namaste|good (?:morning|afternoon|evening)|thanks?|thank you|ok(?:ay)?|cool|bye)\W*$"


# ---------------------------------------------------------------- result

@dataclass
class Route:
    action: str                 # "answer" or a REPLIES key
    schemes: list[str] = field(default_factory=list)
    topic: str | None = None    # primary topic, e.g. "exit_load"
    topics: list[str] = field(default_factory=list)
    reply: str | None = None    # canned reply for non-answer actions
    link: str | None = None     # its official link
    pii_found: list[str] = field(default_factory=list)  # kinds only, never values
    checked_by: str = "rules"   # "rules", "rules+ai", or "rules (ai unavailable)"

    @property
    def is_answer(self) -> bool:
        return self.action == "answer"


def _reply(action: str, **kw) -> Route:
    text, link_key = REPLIES[action]
    return Route(action=action, reply=text, link=LINKS[link_key], **kw)


def _any(patterns, text: str) -> bool:
    return any(re.search(p, text) for p in patterns)


# ---------------------------------------------------------------- helpers

def find_pii(text: str) -> list[str]:
    """Kinds of personal data present in the text (e.g. ["PAN", "phone"])."""
    low = text.lower()
    return [kind for kind, p in PII_PATTERNS.items() if re.search(p, low)]


def redact(text: str) -> str:
    """Replace any personal data with [REDACTED], for safe logging."""
    out = text
    for p in PII_PATTERNS.values():
        out = re.sub(p, "[REDACTED]", out, flags=re.I)
    return out


def find_schemes(low: str) -> list[str]:
    found = []
    for key, s in SCHEMES.items():
        names = [n.lower() for n in s["doc_names"]] + s["aliases"]
        if any(re.search(r"\b" + re.escape(n) + r"\b", low) for n in names):
            found.append(key)
    return found


def find_topics(low: str) -> list[str]:
    """Topics asked about. Fund names are removed first, so the word
    "Tax Saver" in "Groww ELSS Tax Saver Fund" isn't read as a lock-in question."""
    for s in SCHEMES.values():
        for n in s["doc_names"]:
            low = low.replace(n.lower(), " ")
    return [name for name, p in TOPICS if re.search(p, low)]


# ---------------------------------------------------------------- main

def route(question: str) -> Route:
    text = (question or "").strip()
    low = re.sub(r"\s+", " ", text.lower())

    # 1. empty or greeting
    if not low or re.match(GREETING, low):
        return _reply("greet")

    # 2. personal details: block before anything else looks at the text
    pii = find_pii(text)
    if pii:
        return _reply("block_pii", pii_found=pii)

    # 3. attempts to override the assistant's rules
    if re.search(INJECTION, low):
        return _reply("out_of_scope")

    topics = find_topics(low)
    is_statement = bool({"statement", "capital_gains"} & set(topics))

    # 4. advice / opinion. Also "Large cap or multicap?": two funds joined by
    #    "or" with no fact asked is a request to choose.
    schemes = find_schemes(low)
    choose = len(schemes) >= 2 and re.search(r"\bor\b|\bvs\.?\b|versus", low) and not (
        set(topics) & SCHEME_SPECIFIC)
    if _any(ADVICE, low) or choose or (re.search(JUDGEMENT, low) and "risk" not in low):
        return _reply("refuse_advice", topics=topics)

    # 5. returns / performance ("capital gains statement" is not a returns question)
    if not is_statement and _any(PERFORMANCE, low):
        return _reply("refuse_performance", topics=topics)

    # 6. another fund house, e.g. "HDFC Flexi Cap"
    if re.search(OTHER_AMCS, low):
        return _reply("other_amc", topics=topics)

    # 7. a Groww MF scheme outside our four, e.g. "Groww Small Cap Fund".
    #    Only when none of our four is named, so "Large cap benchmark Nifty 100?" still answers.
    if not schemes and re.search(OTHER_GROWW_SCHEMES, low):
        return _reply("other_scheme", topics=topics)

    if schemes == ["elss"] and not topics and re.search(WITHDRAWAL, low):
        topics = ["lock_in"]
    topic = topics[0] if topics else None

    # ELSS is the only scheme with a lock-in, so "lock-in period?" means ELSS.
    if topic == "lock_in" and not schemes:
        schemes = ["elss"]

    # 8. NAV changes daily; we don't quote it
    if topic == "nav":
        return _reply("nav", schemes=schemes, topics=topics)

    # 9. a fund-specific fact with no fund named ("Exit load?"), unless it's
    #    a definition ("What is an exit load?"), which the factsheet glossary answers
    is_definition = re.search(DEFINITION, low) and not re.search(VALUE_WORDS, low)
    if topic in SCHEME_SPECIFIC and not schemes and not is_definition:
        return _reply("clarify", topics=topics)

    # 10. nothing to do with mutual funds
    if not schemes and not topics and not re.search(MF_WORDS, low):
        return _reply("out_of_scope")

    # 11. a factual question we can try to answer
    return Route(action="answer", schemes=schemes, topic=topic, topics=topics)


# ---------------------------------------------------------------- AI double-check

AI_SYSTEM = """You classify questions sent to a facts-only mutual fund FAQ assistant.
Reply with JSON only: {"label": "<label>"} where <label> is one of:

fact        - asks what something IS or how a process works: a scheme's expense ratio,
              exit load, minimum SIP, lock-in, riskometer level, benchmark, fund manager,
              launch date, what it invests in, definitions, or how to download statements.
              Comparing the FACTS of two schemes is still fact.
advice      - asks for an opinion, judgement, recommendation or a choice: whether to buy,
              sell, hold or switch; which fund is better, safer or right for someone;
              whether a number is good, high or worth it; where to put money; rating a fund;
              whether a fund or company can be trusted.
performance - asks about returns, gains, growth of an investment, past or future
              performance, yield, or whether a fund beat its benchmark.
other       - not about mutual funds.

Examples:
"Is Groww ELSS very high risk?" -> fact (asks its riskometer level)
"Expense ratio of large cap vs multicap" -> fact
"How do I download my CAS?" -> fact
"Is 0.5% expense ratio cheap?" -> advice
"Large cap or multicap for my son?" -> advice
"Give me your honest view on the liquid fund" -> advice
"What did the multicap fund deliver last year?" -> performance
"How much would 10k have grown in ELSS?" -> performance
"Write me a poem" -> other"""

AI_ACTIONS = {"advice": "refuse_advice", "performance": "refuse_performance", "other": "out_of_scope"}


def ai_label(question: str) -> str:
    """Ask the AI model for a label. Raises llm.LLMError if it's unreachable."""
    import json

    from llm import CLASSIFIER_MODEL, LLMError, generate
    raw = generate(f"Question: {question}", system=AI_SYSTEM, model=CLASSIFIER_MODEL,
                   json_mode=True, max_tokens=20, timeout=8)
    try:
        label = json.loads(raw).get("label", "").strip().lower()
    except (ValueError, AttributeError):
        raise LLMError(f"unreadable label: {raw[:80]}") from None
    if label not in {"fact", "advice", "performance", "other"}:
        raise LLMError(f"unknown label: {label}")
    return label


def route_checked(question: str, use_ai: bool = True) -> Route:
    """Rules first; then, for questions the rules would answer, an AI double-check.

    The AI only ever sees questions that already passed the personal-details
    check, and it can only make the assistant MORE cautious (turn an answer
    into a refusal), never the other way round.
    """
    r = route(question)
    if not (use_ai and r.is_answer):
        return r
    from llm import LLMError, available
    if not available():
        r.checked_by = "rules (ai unavailable)"
        return r
    try:
        label = ai_label(question)
    except LLMError:
        r.checked_by = "rules (ai unavailable)"
        return r
    if label in AI_ACTIONS:
        out = _reply(AI_ACTIONS[label], topics=r.topics)
        out.checked_by = "rules+ai"
        return out
    r.checked_by = "rules+ai"
    return r


if __name__ == "__main__":
    for q in sys.argv[1:] or ["What is the exit load of Groww Liquid Fund?"]:
        r = route_checked(q)
        print(f"{r.action:<20} [{r.checked_by}] schemes={r.schemes} topic={r.topic}  <- {q}")
