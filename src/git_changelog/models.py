"""Commits collected from git and the changelog produced from them."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Section(str, Enum):
    """Keep a Changelog sections this tool emits.

    Order is Added, Changed, Fixed, Removed, Security. Deprecated is omitted.
    """

    added = "Added"
    changed = "Changed"
    fixed = "Fixed"
    removed = "Removed"
    security = "Security"


SECTION_ORDER: tuple[Section, ...] = (
    Section.added,
    Section.changed,
    Section.fixed,
    Section.removed,
    Section.security,
)

_SECTION_ALIASES = {
    "added": Section.added,
    "add": Section.added,
    "changed": Section.changed,
    "change": Section.changed,
    "fixed": Section.fixed,
    "fix": Section.fixed,
    "removed": Section.removed,
    "remove": Section.removed,
    "security": Section.security,
    "sec": Section.security,
}


def parse_section(value: object) -> Section | None:
    """Return a known section name, or None when the model invented one."""
    if isinstance(value, Section):
        return value
    key = str(value or "").strip().lower()
    return _SECTION_ALIASES.get(key)


class Commit(BaseModel):
    """One commit as `git log` reported it. Hashes are never synthesized."""

    model_config = ConfigDict(extra="forbid")

    full_hash: str = Field(min_length=7)
    short_hash: str = Field(min_length=7)
    date: str = Field(min_length=4)
    subject: str = ""
    body: str = ""

    @field_validator("full_hash", "short_hash", "date", "subject", "body", mode="before")
    @classmethod
    def _strip(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()


class Bullet(BaseModel):
    """A user-facing note tied to one or more collected commits."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    commits: list[Commit] = Field(min_length=1)


class ChangelogDocument(BaseModel):
    """The release heading and the bullets under it. Rendered by this program."""

    model_config = ConfigDict(extra="forbid")

    release: str
    date: str
    sections: dict[Section, list[Bullet]]


class LLMBullet(BaseModel):
    """One bullet the model claims is grounded in the commit list."""

    model_config = ConfigDict(extra="ignore")

    text: str = ""
    commits: list[str] = Field(default_factory=list)

    @field_validator("text", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("commits", mode="before")
    @classmethod
    def _coerce_commits(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            raise ValueError("commits must be a list of hashes.")
        return [str(item).strip() for item in value if str(item).strip()]


class LLMSection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = ""
    items: list[LLMBullet] = Field(default_factory=list)

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("items", mode="before")
    @classmethod
    def _items(cls, value: object) -> list[object]:
        if value is None:
            return []
        if isinstance(value, dict):
            return [value]
        if not isinstance(value, list):
            raise ValueError("items must be a list.")
        return value


class LLMChangelog(BaseModel):
    """JSON object requested from the model. Extra keys are ignored."""

    model_config = ConfigDict(extra="ignore")

    sections: list[LLMSection] = Field(default_factory=list)

    @field_validator("sections", mode="before")
    @classmethod
    def _sections(cls, value: object) -> list[object]:
        if value is None:
            return []
        if isinstance(value, dict):
            return [{"name": name, "items": items} for name, items in value.items()]
        if not isinstance(value, list):
            raise ValueError("sections must be a list.")
        return value
