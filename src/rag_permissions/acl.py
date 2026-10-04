"""Permission model for retrieval-time ACL enforcement.

The single invariant this module protects: a document is retrievable by a
user if and only if the user (or one of their groups) appears in the
document's ACL. Enforcement happens *before* ranking, never after.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class User:
    """A search user: an identity plus the groups they belong to."""

    id: str
    groups: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        # Accept any iterable; the frozen dataclass keeps a frozenset.
        object.__setattr__(self, "groups", frozenset(self.groups))


@dataclass
class Document:
    """An indexed document. The ACL travels with the document: no ACL means
    no access (fail closed)."""

    id: str
    text: str
    acl: set[str] = field(default_factory=set)
    embedding: list[float] | None = None


def can_access(user: User, doc: Document) -> bool:
    """True when the user or any of their groups is in the document's ACL."""
    if not doc.acl:
        return False
    return user.id in doc.acl or bool(user.groups & doc.acl)


def permission_filter(user: User, docs: list[Document]) -> list[Document]:
    """Return only the documents the user may see.

    Apply this to the candidate set BEFORE ranking. Ranking must never see
    documents the user may not access.
    """
    return [doc for doc in docs if can_access(user, doc)]
