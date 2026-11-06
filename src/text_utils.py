"""Small text helpers shared by the router, the answer step and the tests."""

from __future__ import annotations

import re

# Dots that do NOT end a sentence: abbreviations and decimals like 0.0070%.
_ABBREV = r"(?:Rs|Re|No|Nos|e\.g|i\.e|etc|approx|p\.a|vs|Ltd|Pvt|Mr|Ms|Dr|St|Sr|Jr|viz|cf|Fig)"

MIN_SENTENCES = 2
MAX_SENTENCES = 3


def split_sentences(text: str) -> list[str]:
    """Split text into sentences, ignoring dots in decimals and abbreviations."""
    text = re.sub(r"\s+", " ", text.strip())
    if not text:
        return []
    protected = re.sub(r"(\d)\.(\d)", r"\1<DOT>\2", text)
    protected = re.sub(rf"\b({_ABBREV})\.", r"\1<DOT>", protected, flags=re.I)
    parts = re.split(r'(?<=[.!?])["\')\]]?\s+(?=["\'(\[]?[A-Z0-9₹])', protected)
    return [p.replace("<DOT>", ".").strip() for p in parts if p.strip()]


def count_sentences(text: str) -> int:
    return len(split_sentences(text))


def numbers_in(text: str) -> set[str]:
    """Numbers in a text, normalised so '1,000' == '1000' and '₹500' == '500'."""
    found = re.findall(r"\d+(?:[.,]\d+)*", text)
    return {n.replace(",", "").rstrip(".") for n in found}
