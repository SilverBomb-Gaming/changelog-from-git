"""Turn raw commits into user-facing notes and drop noise.

Rules, applied in order:

1. Empty subjects are skipped.
2. Merge commits (`Merge branch`, `Merge pull request`, `Merge remote-tracking branch`,
   `Merge tag`) are skipped. They repeat work that already has its own commit.
3. Conventional `test` commits are skipped. They do not describe a user-facing change.
4. Conventional `chore`, `ci`, `build`, and `style` commits are skipped as maintenance,
   except dependency bumps, which are folded into one Changed note.
5. A dependency bump is a `deps` / `dependabot` scope, or a subject like
   `bump <name> from <old> to <new>`, or the word `dependabot` / `dependencies`.
   Two or more become "Update dependencies." One keeps its own subject.
6. Conventional `docs` commits are kept. Two or more become "Update documentation."
7. `feat` → Added, `fix` → Fixed, `security` / `sec` → Security, `revert` → Removed,
   `refactor` / `perf` → Changed.
8. A subject with no conventional prefix is kept. `Add` / `Fix` / `Remove` pick a
   section. Anything else lands in Changed. Those commits are not treated as noise.

`--include-noise` keeps test and maintenance commits as individual Changed notes.
Merges and empty subjects stay skipped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from git_changelog.models import Commit, Section

_CONVENTIONAL = re.compile(
    r"^(?P<type>feat|feature|fix|docs|style|refactor|perf|test|chore|ci|build|revert|security|sec)"
    r"(?:\((?P<scope>[^)]*)\))?(?P<breaking>!)?:\s*(?P<rest>.*)$",
    re.IGNORECASE,
)
_MERGE = re.compile(
    r"^Merge (branch|pull request|remote-tracking branch|tag)\b",
    re.IGNORECASE,
)
_DEP_SUBJECT = re.compile(
    r"(dependabot|\bdependencies\b|\bbump\b\s+\S+\s+from\s+\S+\s+to\s+\S+)",
    re.IGNORECASE,
)
_DEP_SCOPES = {"dep", "deps", "dependabot", "dependencies"}
_NOISE_TYPES = {"chore", "ci", "build", "style"}
_ADD = re.compile(r"^(add|adds|added|implement|implements|introduce|introduces)\b", re.IGNORECASE)
_FIX = re.compile(r"^(fix|fixes|fixed|bugfix)\b", re.IGNORECASE)
_REMOVE = re.compile(
    r"^(remove|removes|removed|drop|drops|dropped|revert|reverts|reverted)\b",
    re.IGNORECASE,
)
_SECURITY = re.compile(r"\b(cve-\d{4}-\d+|security fix)\b", re.IGNORECASE)

SKIP_EMPTY = "empty subject"
SKIP_MERGE = "merge commit"
SKIP_TEST = "test-only commit"
SKIP_MAINTENANCE = "maintenance noise"


@dataclass
class SkippedCommit:
    commit: Commit
    reason: str


@dataclass
class DraftItem:
    """One changelog row before the model rewrites the sentence."""

    section: Section
    summary: str
    commits: list[Commit]
    grouped: bool


def prepare_commits(
    commits: list[Commit],
    *,
    include_noise: bool = False,
) -> tuple[list[DraftItem], list[SkippedCommit]]:
    """Group dependency and docs commits. Skip merges and other noise."""
    drafts: list[DraftItem] = []
    skipped: list[SkippedCommit] = []
    deps: DraftItem | None = None
    docs: DraftItem | None = None

    for commit in commits:
        action, section, reason = _classify(commit, include_noise=include_noise)
        if action == "skip":
            skipped.append(SkippedCommit(commit=commit, reason=reason))
            continue
        if action == "deps":
            if deps is None:
                deps = DraftItem(section=Section.changed, summary="", commits=[commit], grouped=False)
                drafts.append(deps)
            else:
                deps.commits.append(commit)
            continue
        if action == "docs":
            if docs is None:
                docs = DraftItem(section=Section.changed, summary="", commits=[commit], grouped=False)
                drafts.append(docs)
            else:
                docs.commits.append(commit)
            continue
        drafts.append(
            DraftItem(
                section=section or Section.changed,
                summary=clean_subject(commit.subject),
                commits=[commit],
                grouped=False,
            )
        )

    if deps is not None:
        deps.grouped = len(deps.commits) > 1
        deps.summary = (
            "Update dependencies." if deps.grouped else clean_subject(deps.commits[0].subject)
        )
    if docs is not None:
        docs.grouped = len(docs.commits) > 1
        docs.summary = (
            "Update documentation." if docs.grouped else clean_subject(docs.commits[0].subject)
        )
    return drafts, skipped


def clean_subject(subject: str) -> str:
    """Drop a conventional prefix and return one sentence."""
    text = subject.strip()
    match = _CONVENTIONAL.match(text)
    if match and match.group("rest").strip():
        text = match.group("rest").strip()
    if not text:
        return ""
    text = text[0].upper() + text[1:]
    if text[-1] not in ".!?":
        text += "."
    return text


def _classify(commit: Commit, *, include_noise: bool) -> tuple[str, Section | None, str]:
    subject = commit.subject.strip()
    if not subject:
        return "skip", None, SKIP_EMPTY
    if _MERGE.match(subject):
        return "skip", None, SKIP_MERGE

    match = _CONVENTIONAL.match(subject)
    if match:
        commit_type = match.group("type").lower()
        if commit_type == "feature":
            commit_type = "feat"
        if commit_type == "sec":
            commit_type = "security"
        scope = (match.group("scope") or "").strip().lower()
        rest = (match.group("rest") or "").strip()
        if not rest:
            return "skip", None, SKIP_EMPTY
        if _is_dependency(commit_type, scope, subject):
            return "deps", Section.changed, ""
        if commit_type == "docs":
            return "docs", Section.changed, ""
        if commit_type == "test":
            if include_noise:
                return "keep", Section.changed, ""
            return "skip", None, SKIP_TEST
        if commit_type in _NOISE_TYPES:
            if include_noise:
                return "keep", Section.changed, ""
            return "skip", None, SKIP_MAINTENANCE
        return "keep", _section_for_type(commit_type), ""

    if _DEP_SUBJECT.search(subject):
        return "deps", Section.changed, ""
    if _ADD.match(subject):
        return "keep", Section.added, ""
    if _FIX.match(subject):
        return "keep", Section.fixed, ""
    if _REMOVE.match(subject):
        return "keep", Section.removed, ""
    if _SECURITY.search(subject):
        return "keep", Section.security, ""
    return "keep", Section.changed, ""


def _is_dependency(commit_type: str, scope: str, subject: str) -> bool:
    if scope in _DEP_SCOPES:
        return True
    if commit_type in _NOISE_TYPES and _DEP_SUBJECT.search(subject):
        return True
    return False


def _section_for_type(commit_type: str) -> Section:
    if commit_type == "feat":
        return Section.added
    if commit_type == "fix":
        return Section.fixed
    if commit_type == "security":
        return Section.security
    if commit_type == "revert":
        return Section.removed
    return Section.changed
