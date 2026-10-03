"""Vector store with retrieval-time ACL enforcement.

Two backends with identical permission semantics:
- InMemoryStore: zero-dependency demo backend.
- PgVectorStore: real backend (requires DATABASE_URL).

Both backends filter by permission BEFORE ranking. The ranking function is a
stand-in (keyword overlap); swap in real embeddings without touching the
permission logic — that separation is the point.
"""
from __future__ import annotations

import os

from acl import Document, User, permission_filter


def _score(query: str, doc: Document) -> float:
    """Toy relevance score. Replace with embedding similarity in real use."""
    q = set(query.lower().split())
    d = set(doc.text.lower().split())
    return len(q & d) / max(len(q), 1)


class InMemoryStore:
    def __init__(self):
        self.docs: list = []

    def add(self, doc: Document):
        self.docs.append(doc)

    def search(self, user: User, query: str, top_k: int = 5) -> list:
        # 1. Enforce permissions FIRST — the candidate set is born filtered.
        allowed = permission_filter(user, self.docs)
        # 2. Rank only within what the user may see.
        ranked = sorted(allowed, key=lambda d: _score(query, d), reverse=True)
        return ranked[:top_k]


class PgVectorStore:
    """Real backend. ACL enforcement is pushed into the SQL WHERE clause so
    forbidden rows never leave the database."""

    def __init__(self, dsn: str | None = None):
        import psycopg  # lazy import: only needed for this backend

        self.dsn = dsn or os.environ["DATABASE_URL"]
        self.conn = psycopg.connect(self.dsn)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rag_docs (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                acl TEXT[] NOT NULL DEFAULT '{}',
                embedding VECTOR(384)
            )
            """
        )
        self.conn.commit()

    def add(self, doc: Document):
        self.conn.execute(
            "INSERT INTO rag_docs (id, text, acl) VALUES (%s, %s, %s) "
            "ON CONFLICT (id) DO UPDATE SET text=EXCLUDED.text, acl=EXCLUDED.acl",
            (doc.id, doc.text, list(doc.acl)),
        )
        self.conn.commit()

    def search(self, user: User, query: str, top_k: int = 5) -> list:
        # Permission check lives in the WHERE clause: forbidden rows never
        # leave Postgres. Python-side filtering is a defense-in-depth second pass.
        principals = [user.id, *user.groups]
        rows = self.conn.execute(
            "SELECT id, text, acl FROM rag_docs "
            "WHERE acl && %s::text[] OR %s = ANY(acl)",
            (principals, user.id),
        ).fetchall()
        docs = [Document(id=r[0], text=r[1], acl=set(r[2])) for r in rows]
        allowed = permission_filter(user, docs)
        ranked = sorted(allowed, key=lambda d: _score(query, d), reverse=True)
        return ranked[:top_k]
