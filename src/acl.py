"""The permission model: documents, users, groups, and retrieval-time enforcement.

Core rule: a document is retrievable by a user ONLY if the user's identity
or one of their groups appears in the document's ACL. Enforcement happens
before ranking, never after.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class User:
    id: str
    groups: frozenset = field(default_factory=frozenset)


@dataclass
class Document:
    id: str
    text: str
    # ACL: set of user ids and/or group ids allowed to see this document.
    # Empty ACL => nobody can see it (fail closed).
    acl: set = field(default_factory=set)
    embedding: list = field(default_factory=list)


def can_access(user: User, doc: Document) -> bool:
    """True if the user or any of their groups is in the document's ACL."""
    if not doc.acl:
        return False  # fail closed: no ACL means no access
    if user.id in doc.acl:
        return True
    return bool(user.groups & doc.acl)


def permission_filter(user: User, docs: list) -> list:
    """Enforce ACLs BEFORE ranking. Returns only documents the user may see."""
    return [d for d in docs if can_access(user, d)]
