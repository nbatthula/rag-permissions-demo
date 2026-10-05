"""Vector stores with retrieval-time ACL enforcement.

Both backends share one contract: the candidate set is permission-filtered
BEFORE ranking. The in-memory backend exists so the demo runs with zero
dependencies; the pgvector backend shows how to push the same check into the
database, where it belongs.
"""
from __future__ import annotations

import os
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # typing.Self is 3.11+; import only for type checkers since
    # `from __future__ import annotations` keeps annotations lazy at runtime.
    from typing import Self

from .acl import Document, User, permission_filter
from .scoring import Scorer, keyword_overlap_score

Embedder = Callable[[str], list[float]]


class InMemoryStore:
    """Zero-dependency store. Permission semantics identical to PgVectorStore."""

    def __init__(self, scorer: Scorer = keyword_overlap_score) -> None:
        self._docs: list[Document] = []
        self._scorer = scorer

    def add(self, doc: Document) -> None:
        self._docs.append(doc)

    def search(self, user: User, query: str, top_k: int = 5) -> list[Document]:
        allowed = permission_filter(user, self._docs)  # 1. enforce first
        ranked = sorted(allowed, key=lambda d: self._scorer(query, d), reverse=True)
        return ranked[:top_k]


class PgVectorStore:
    """Postgres/pgvector backend. The ACL check lives in the WHERE clause, so
    forbidden rows never leave the database."""

    def __init__(self, dsn: str, embed: Embedder) -> None:
        import psycopg

        self._embed = embed
        self._conn = psycopg.connect(dsn)

    @classmethod
    def connect(
        cls, dsn: str | None = None, embed: Embedder | None = None
    ) -> PgVectorStore:
        """Connect and ensure the schema exists. Constructors do no I/O."""
        dsn = dsn or os.environ.get("DATABASE_URL")
        if not dsn:
            raise ValueError(
                "PgVectorStore needs a DSN: pass dsn=... or set DATABASE_URL"
            )
        store = cls(dsn, embed or insecure_demo_embed)
        store.init_schema()
        return store

    def init_schema(self) -> None:
        # The pgvector image ships the extension installed but not enabled;
        # the VECTOR type does not exist until this runs.
        self._conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rag_docs (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                acl TEXT[] NOT NULL DEFAULT '{}',
                embedding VECTOR(384)
            )
            """
        )
        # GIN index: the ACL overlap check in search() must not become the
        # slow path as the corpus grows.
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS rag_docs_acl_gin ON rag_docs USING GIN (acl)"
        )
        self._conn.commit()

    def add(self, doc: Document) -> None:
        embedding = doc.embedding if doc.embedding is not None else self._embed(doc.text)
        self._conn.execute(
            """
            INSERT INTO rag_docs (id, text, acl, embedding)
            VALUES (%s, %s, %s, %s::vector)
            ON CONFLICT (id) DO UPDATE SET
                text = EXCLUDED.text,
                acl = EXCLUDED.acl,
                embedding = EXCLUDED.embedding
            """,
            (doc.id, doc.text, sorted(doc.acl), _vector_literal(embedding)),
        )
        self._conn.commit()

    def search(self, user: User, query: str, top_k: int = 5) -> list[Document]:
        principals = [user.id, *sorted(user.groups)]
        rows = self._conn.execute(
            """
            SELECT id, text, acl FROM rag_docs
             WHERE acl && %s
             ORDER BY embedding <=> %s::vector
             LIMIT %s
            """,
            (principals, _vector_literal(self._embed(query)), top_k),
        ).fetchall()
        docs = [Document(id=row[0], text=row[1], acl=set(row[2])) for row in rows]
        # Defense in depth: the WHERE clause already enforced the ACL, but the
        # Python-side filter is cheap and keeps both backends honest.
        return permission_filter(user, docs)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def insecure_demo_embed(text: str, dim: int = 384) -> list[float]:
    """DEMO ONLY. Deterministic hash-based pseudo-embedding so the pgvector
    path runs without an embedding model or API key. It carries no semantic
    meaning: replace with a real embedding model before any serious use."""
    import hashlib

    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [digest[i % len(digest)] / 255.0 * 2 - 1 for i in range(dim)]


def _vector_literal(embedding: list[float]) -> str:
    """Render an embedding as a Postgres vector literal (no driver needed)."""
    return "[" + ",".join(f"{x:.6f}" for x in embedding) + "]"
