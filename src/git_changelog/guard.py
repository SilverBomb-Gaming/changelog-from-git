"""Drop model bullets that do not cite a commit this run collected."""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from git_changelog.grouping import DraftItem
from git_changelog.models import (
    SECTION_ORDER,
    Bullet,
    Commit,
    LLMChangelog,
    Section,
    parse_section,
)

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_PR = re.compile(r"(?i)\b(?:pull request|PR)\s*#(\d+)\b")
_ISSUE = re.compile(r"#(\d+)\b")
_SPACE = re.compile(r"[ \t]+")
_EMPTY_PARENS = re.compile(r"\(\s*\)")


def bullets_from_model(
    raw: str,
    drafts: list[DraftItem],
) -> tuple[dict[Section, list[Bullet]] | None, list[str]]:
    """Validate model JSON against the collected commits.

    Returns `(None, warnings)` when nothing usable remains so the caller can
    fall back to the deterministic draft. A partial result keeps the bullets
    that cite real hashes and reports how many were dropped.
    """
    warnings: list[str] = []
    try:
        parsed = _parse(raw)
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        return None, [f"Model output was not usable changelog JSON ({exc})."]

    known = _index(drafts)
    order = {commit.full_hash: index for index, commit in enumerate(_all_commits(drafts))}
    sections: dict[Section, list[Bullet]] = {section: [] for section in SECTION_ORDER}
    dropped = 0
    unknown_sections = 0

    for block in parsed.sections:
        section = parse_section(block.name)
        if section is None:
            if block.name.strip() and block.items:
                unknown_sections += 1
            continue
        for item in block.items:
            resolved = _resolve_hashes(item.commits, known, order)
            if not resolved:
                dropped += 1
                continue
            text = _clean_text(item.text, resolved)
            if not text:
                dropped += 1
                continue
            sections[section].append(Bullet(text=text, commits=resolved))

    if unknown_sections:
        warnings.append(
            f"Ignored {unknown_sections} section(s) outside Added, Changed, Fixed, Removed, and Security."
        )
    if dropped:
        warnings.append(f"Dropped {dropped} model bullet(s) that did not cite a collected commit.")

    if not any(sections.values()):
        warnings.append("Model output had no bullets tied to collected commits.")
        return None, warnings
    return sections, warnings


def drafts_to_sections(drafts: list[DraftItem]) -> dict[Section, list[Bullet]]:
    """Deterministic notes from commit subjects. Used for --no-llm and as a fallback."""
    sections: dict[Section, list[Bullet]] = {section: [] for section in SECTION_ORDER}
    for draft in drafts:
        sections[draft.section].append(Bullet(text=draft.summary, commits=list(draft.commits)))
    return sections


def _parse(raw: str) -> LLMChangelog:
    text = raw.strip()
    if text.startswith("```"):
        text = _FENCE.sub("", text).strip()
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("expected a JSON object")
    return LLMChangelog.model_validate(payload)


def _all_commits(drafts: list[DraftItem]) -> list[Commit]:
    commits: list[Commit] = []
    seen: set[str] = set()
    for draft in drafts:
        for commit in draft.commits:
            if commit.full_hash in seen:
                continue
            seen.add(commit.full_hash)
            commits.append(commit)
    return commits


def _index(drafts: list[DraftItem]) -> dict[str, Commit]:
    known: dict[str, Commit] = {}
    for commit in _all_commits(drafts):
        known[commit.full_hash.lower()] = commit
        known[commit.short_hash.lower()] = commit
    return known


def _resolve_hashes(
    hashes: list[str],
    known: dict[str, Commit],
    order: dict[str, int],
) -> list[Commit]:
    resolved: list[Commit] = []
    seen: set[str] = set()
    for raw_hash in hashes:
        commit = _lookup(raw_hash, known)
        if commit is None or commit.full_hash in seen:
            continue
        seen.add(commit.full_hash)
        resolved.append(commit)
    resolved.sort(key=lambda commit: order[commit.full_hash])
    return resolved


def _lookup(raw_hash: str, known: dict[str, Commit]) -> Commit | None:
    token = raw_hash.strip().lower()
    if token in known:
        return known[token]
    if len(token) < 7:
        return None
    matches = [commit for key, commit in known.items() if len(key) == 40 and key.startswith(token)]
    unique = {commit.full_hash: commit for commit in matches}
    if len(unique) == 1:
        return next(iter(unique.values()))
    return None


def _clean_text(text: str, commits: list[Commit]) -> str:
    cleaned = text.strip()
    source = "\n".join(f"{commit.subject}\n{commit.body}" for commit in commits)

    def keep_number(match: re.Match[str]) -> str:
        number = match.group(1)
        if re.search(rf"(?<!\d){re.escape(number)}(?!\d)", source):
            return match.group(0)
        return ""

    cleaned = _PR.sub(keep_number, cleaned)
    cleaned = _ISSUE.sub(keep_number, cleaned)
    for commit in commits:
        cleaned = re.sub(rf"\b{re.escape(commit.full_hash)}\b", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(rf"\b{re.escape(commit.short_hash)}\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r" *\n *", " ", cleaned)
    cleaned = _tidy_sentence(cleaned)
    return cleaned


def _tidy_sentence(text: str) -> str:
    """Collapse whitespace left behind when a fabricated issue number is removed."""
    cleaned = _EMPTY_PARENS.sub("", text)
    cleaned = _SPACE.sub(" ", cleaned)
    cleaned = re.sub(r"\s+([.!?])", r"\1", cleaned)
    cleaned = re.sub(r"\(\s+", "(", cleaned)
    cleaned = re.sub(r"\s+\)", ")", cleaned)
    cleaned = _EMPTY_PARENS.sub("", cleaned)
    cleaned = _SPACE.sub(" ", cleaned).strip()
    cleaned = cleaned.strip(" -;,:")
    cleaned = _SPACE.sub(" ", cleaned).strip()
    if cleaned and cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned
