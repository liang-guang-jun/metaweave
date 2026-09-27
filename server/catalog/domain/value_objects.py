from __future__ import annotations

# ruff: noqa

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from ...kernel.domain.entity import EntityId


class _UuidId(EntityId[UUID]):
    def __init__(self, value: UUID | str) -> None:
        self._value = UUID(value) if isinstance(value, str) else value

    @property
    def value(self) -> UUID:
        return self._value

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._value!s})"


class WorkspaceId(_UuidId):
    pass


class WorkspaceMembershipId(_UuidId):
    pass


class NodeId(_UuidId):
    pass


class WorkspaceRole(StrEnum):
    VIEWER = "VIEWER"
    CONTRIBUTOR = "CONTRIBUTOR"
    ADMIN = "ADMIN"


class NodeType(StrEnum):
    FOLDER = "FOLDER"
    TABLE = "TABLE"
    GLOSSARY_BOOK = "GLOSSARY_BOOK"
    TERM = "TERM"
    MODEL = "MODEL"
    MAPPING = "MAPPING"


class CatalogAction(StrEnum):
    """Deprecated catalog aliases; use IAM resource Action directly."""

    READ = "read"
    WRITE = "update"
    DELETE = "delete"


@dataclass(frozen=True, slots=True)
class NodeProperty:
    key: str
    value: object

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("property key is required")


@dataclass(frozen=True, slots=True)
class NodePath:
    node_ids: tuple[NodeId, ...]
