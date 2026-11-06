"""A small BM25 implementation, so retrieval works offline without extra dependencies."""

from __future__ import annotations

import math
import re
from collections import Counter

STOPWORDS = frozenset(
    """a an and are as at be by did do does for from had has have how i in is it its of on or
    our that the their there this to was we were what when where which who why with would you
    your""".split()
)

_TOKEN_RE = re.compile(r"[a-z0-9äöüß]+")

_IRREGULAR = {"lost": "los", "won": "win", "winning": "win", "losing": "los"}
_SUFFIXES = ("ing", "ed", "es", "s")


def stem(token: str) -> str:
    """A deliberately tiny stemmer: enough for lose/lost/loss or sample/sampled/sampling."""
    if token in _IRREGULAR:
        return _IRREGULAR[token]
    if token.isdigit() or len(token) <= 3:
        return token
    for suffix in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            token = token[: -len(suffix)]
            break
    if token.endswith("e") and len(token) > 3:
        token = token[:-1]
    return token


def tokenize(text: str) -> list[str]:
    tokens = _TOKEN_RE.findall(text.lower())
    return [stem(t) for t in tokens if t not in STOPWORDS and (len(t) > 1 or t.isdigit())]


class BM25Index:
    def __init__(self, texts: list[str], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._docs = [Counter(tokenize(text)) for text in texts]
        self._lengths = [sum(doc.values()) for doc in self._docs]
        self._avg_len = (sum(self._lengths) / len(self._lengths)) if self._lengths else 0.0
        self._df: Counter[str] = Counter()
        for doc in self._docs:
            self._df.update(doc.keys())

    def __len__(self) -> int:
        return len(self._docs)

    def _idf(self, term: str) -> float:
        n = len(self._docs)
        df = self._df.get(term, 0)
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def score(self, query_terms: list[str], index: int) -> float:
        doc = self._docs[index]
        length = self._lengths[index] or 1
        total = 0.0
        for term in query_terms:
            tf = doc.get(term, 0)
            if not tf:
                continue
            denom = tf + self.k1 * (1 - self.b + self.b * length / (self._avg_len or 1))
            total += self._idf(term) * (tf * (self.k1 + 1)) / denom
        return total

    def search(self, query: str, top_k: int = 4) -> list[tuple[int, float]]:
        """Return (chunk index, score) pairs with a positive score, best first."""
        terms = tokenize(query)
        if not terms:
            return []
        scored = [(i, self.score(terms, i)) for i in range(len(self._docs))]
        scored = [(i, s) for i, s in scored if s > 0]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]
