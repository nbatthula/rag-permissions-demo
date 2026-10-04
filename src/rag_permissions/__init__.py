"""Permission-aware retrieval: the rag-permissions-demo package."""
from .acl import Document, User, can_access, permission_filter
from .scoring import Scorer, keyword_overlap_score
from .store import Embedder, InMemoryStore, PgVectorStore, insecure_demo_embed

__all__ = [
    "Document",
    "Embedder",
    "InMemoryStore",
    "PgVectorStore",
    "Scorer",
    "User",
    "can_access",
    "insecure_demo_embed",
    "keyword_overlap_score",
    "permission_filter",
]
