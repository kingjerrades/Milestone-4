"""Search over the ingested chunks.

Keyword search (BM25) always runs. Meaning-based search (embeddings) is added
when the embedding model can be loaded, e.g. on Streamlit Cloud; the two scores
are blended. Chunks flagged as containing returns are never returned, because
the assistant must not state or compare performance.

    from search import Index
    idx = Index.load()
    hits = idx.search("exit load of Groww Liquid Fund", scheme="liquid")
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from nltk.stem import PorterStemmer
from rank_bm25 import BM25Okapi

sys.path.insert(0, str(Path(__file__).parent))
_stem = PorterStemmer().stem

CHUNKS = Path(__file__).resolve().parents[1] / "data" / "processed" / "chunks.jsonl"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"

# Structured facts and short scheme documents are better citations than the
# long SIDs, so they get a gentle boost when scores are close.
KIND_BOOST = {"fact": 1.35, "text": 1.0}
DOC_BOOST = {"KIM": 1.1, "Factsheet": 1.1, "Riskometer": 1.1, "SID": 0.9}

STOPWORDS = set("""a an the of for to in on and or is are what whats what's how do does
i my me can you your it this that with by be at from as which between""".split())

# Words that appear in nearly every chunk: dropped from queries only, so a
# short chunk can't win just by repeating the fund's name.
QUERY_NOISE = {"groww", "mutual", "fund", "funds", "scheme", "amc", "tell", "please"}


def tokenize(text: str) -> list[str]:
    """Lowercase, drop stopwords, and stem so 'difference' matches 'different'."""
    words = re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", text.lower())
    return [_stem(w) for w in words if w not in STOPWORDS]


@dataclass
class Hit:
    score: float
    chunk: dict


class Index:
    def __init__(self, chunks: list[dict]):
        self.chunks = [c for c in chunks if not c["has_returns"]]
        self.bm25 = BM25Okapi([tokenize(c["text"]) for c in self.chunks])
        self.embedder = None
        self.vectors = None

    @classmethod
    def load(cls, path: Path = CHUNKS,
             use_embeddings: bool = os.environ.get("MF_EMBEDDINGS", "1") == "1") -> "Index":
        with open(path, encoding="utf-8") as f:
            idx = cls([json.loads(line) for line in f])
        if use_embeddings:
            idx._try_load_embeddings()
        return idx

    def _try_load_embeddings(self) -> None:
        """Load the embedding model, giving up after MF_EMBED_TIMEOUT seconds.

        The download runs in a separate process that is stopped on timeout,
        so a blocked network can't hang the app or stop it from exiting.
        Once downloaded, the model loads from the local cache.
        """
        import subprocess

        timeout = float(os.environ.get("MF_EMBED_TIMEOUT", "60"))
        fetch = f"from fastembed import TextEmbedding; TextEmbedding({EMBED_MODEL!r})"
        try:
            subprocess.run([sys.executable, "-c", fetch], timeout=timeout, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            import numpy as np
            from fastembed import TextEmbedding
            self.embedder = TextEmbedding(EMBED_MODEL)
            self.vectors = np.array(list(self.embedder.embed([c["text"] for c in self.chunks])))
        except Exception:  # noqa: BLE001  (timeout, no network, bad cache): keyword only
            self.embedder, self.vectors = None, None

    @staticmethod
    def _query_terms(query: str, scheme: str | None) -> list[str]:
        """Query tokens minus generic words and, when filtering by scheme, its name."""
        from schemes import SCHEMES
        drop = {_stem(w) for w in QUERY_NOISE}
        if scheme in SCHEMES:
            s = SCHEMES[scheme]
            for phrase in [s["name"], *s["aliases"]]:
                drop.update(tokenize(phrase))
        terms = [t for t in tokenize(query) if t not in drop]
        return terms or tokenize(query)

    @property
    def mode(self) -> str:
        return "hybrid" if self.embedder is not None else "keyword"

    def search(self, query: str, scheme: str | None = None, k: int = 5) -> list[Hit]:
        """Top-k chunks. `scheme` limits results to that scheme plus AMC-wide pages."""
        kw = self.bm25.get_scores(self._query_terms(query, scheme))
        top = max(kw.max(), 1e-9)
        scores = kw / top

        if self.embedder is not None:
            import numpy as np
            q = np.array(list(self.embedder.embed([query]))[0])
            dense = self.vectors @ q / (np.linalg.norm(self.vectors, axis=1) * np.linalg.norm(q))
            scores = 0.5 * scores + 0.5 * dense

        hits = []
        for c, s in zip(self.chunks, scores):
            if scheme and c["scheme"] not in (scheme, "all"):
                continue
            s *= KIND_BOOST.get(c["kind"], 1.0) * DOC_BOOST.get(c["doc_type"], 1.0)
            if scheme is None and c["scheme"] == "all":
                s *= 1.5  # no fund named: AMC-wide pages (FAQ, statements) fit better
            hits.append(Hit(float(s), c))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]
