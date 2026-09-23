"""Markdown and the --dry-run commit listing. Neither path invents commits."""

from __future__ import annotations

from pathlib import Path

from git_changelog.grouping import DraftItem, SkippedCommit
from git_changelog.models import SECTION_ORDER, ChangelogDocument

_INTRO = (
    "# Changelog\n"
    "\n"
    "All notable changes to this project are documented in this file.\n"
    "The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).\n"
)


def render_markdown(document: ChangelogDocument) -> str:
    """Render one release. Empty sections are omitted. Hashes come from collected commits."""
    lines = [
        _INTRO.rstrip("\n"),
        "",
        f"## [{document.release}] - {document.date}",
        "",
    ]
    for section in SECTION_ORDER:
        bullets = document.sections.get(section) or []
        if not bullets:
            continue
        lines.append(f"### {section.value}")
        lines.append("")
        for bullet in bullets:
            cites = ", ".join(f"`{commit.short_hash}`" for commit in bullet.commits)
            lines.append(f"- {bullet.text} ({cites})")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_listing(
    *,
    repo: Path,
    range_label: str,
    release: str,
    date: str,
    drafts: list[DraftItem],
    skipped: list[SkippedCommit],
) -> str:
    """Plain-text dump of collected commits. This is the --dry-run / --raw output."""
    commit_count = len({commit.full_hash for draft in drafts for commit in draft.commits})
    commit_count += len(skipped)
    lines = [
        f"repo: {repo}",
        f"range: {range_label}",
        f"release: {release}",
        f"date: {date}",
        f"commits: {commit_count}",
        f"notes: {len(drafts)}",
        f"skipped: {len(skipped)}",
        "",
    ]
    for draft in drafts:
        disposition = "group" if draft.grouped else "keep"
        hashes = ",".join(commit.short_hash for commit in draft.commits)
        when = draft.commits[0].date
        subject = draft.summary.replace("\t", " ")
        lines.append(f"{disposition}\t{hashes}\t{when}\t{draft.section.value}\t{subject}")
    for item in skipped:
        subject = item.commit.subject.replace("\t", " ") or "(empty)"
        lines.append(
            f"skip\t{item.commit.short_hash}\t{item.commit.date}\t{item.reason}\t{subject}"
        )
    return "\n".join(lines).rstrip() + "\n"


def section_body(markdown: str) -> str:
    """Return the release section, without the file preamble, for --append."""
    marker = "\n## "
    index = markdown.find(marker)
    if index == -1:
        return markdown
    return markdown[index + 1 :]
