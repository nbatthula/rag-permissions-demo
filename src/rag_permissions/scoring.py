"""Relevance scoring, deliberately separated from permission logic.

The permission layer never depends on how relevance is computed: swap the
scorer for real embedding similarity without touching acl.py or the
permission filter in store.py.
"""
from __future__ import annotations

from collections.abc import Callable

from .acl import Document

Scorer = Callable[[str, Document], float]


def keyword_overlap_score(query: str, doc: Document) -> float:
    """Toy scorer for the runnable demo. Replace with embedding similarity."""
    query_terms = set(query.lower().split())
    if not query_terms:
        return 0.0
    return len(query_terms & set(doc.text.lower().split())) / len(query_terms)
