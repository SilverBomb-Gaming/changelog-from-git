"""Markdown shape: Keep a Changelog sections, hashes from the bullets, no empty sections."""

from __future__ import annotations

from git_changelog.models import Bullet, ChangelogDocument, Commit, Section
from git_changelog.render import render_listing, render_markdown, section_body
from git_changelog.grouping import DraftItem, SkippedCommit


def _commit(short: str, subject: str) -> Commit:
    return Commit(
        full_hash=short + ("b" * (40 - len(short))),
        short_hash=short,
        date="2026-02-10",
        subject=subject,
    )


def test_render_markdown_omits_empty_sections_and_cites_hashes() -> None:
    added = _commit("abc1234", "feat: add export")
    fixed = _commit("def5678", "fix: crash")
    deps_a = _commit("aaa1111", "chore(deps): bump httpx from 0.27.0 to 0.28.1")
    deps_b = _commit("bbb2222", "chore(deps): bump typer from 0.12.0 to 0.15.1")
    document = ChangelogDocument(
        release="0.2.0",
        date="2026-02-10",
        sections={
            Section.added: [Bullet(text="Add export.", commits=[added])],
            Section.changed: [Bullet(text="Update dependencies.", commits=[deps_a, deps_b])],
            Section.fixed: [Bullet(text="Handle the crash.", commits=[fixed])],
            Section.removed: [],
            Section.security: [],
        },
    )
    markdown = render_markdown(document)
    assert markdown.startswith("# Changelog\n")
    assert "## [0.2.0] - 2026-02-10\n" in markdown
    assert "### Added\n" in markdown
    assert "### Changed\n" in markdown
    assert "### Fixed\n" in markdown
    assert "### Removed" not in markdown
    assert "### Security" not in markdown
    assert "- Add export. (`abc1234`)" in markdown
    assert "- Update dependencies. (`aaa1111`, `bbb2222`)" in markdown
    assert "- Handle the crash. (`def5678`)" in markdown
    assert markdown.endswith("\n")
    # Fixed is requested after Changed, before a Removed section would appear.
    assert markdown.index("### Added") < markdown.index("### Changed") < markdown.index("### Fixed")


def test_section_body_drops_the_preamble_for_append() -> None:
    markdown = render_markdown(
        ChangelogDocument(
            release="Unreleased",
            date="2026-03-03",
            sections={
                Section.added: [
                    Bullet(text="Select a range.", commits=[_commit("abc1234", "feat: range")])
                ]
            },
        )
    )
    body = section_body(markdown)
    assert body.startswith("## [Unreleased] - 2026-03-03\n")
    assert not body.startswith("# Changelog")


def test_listing_marks_keep_group_and_skip() -> None:
    kept = _commit("abc1234", "feat: add export")
    grouped = [
        _commit("aaa1111", "chore(deps): bump httpx from 0.27.0 to 0.28.1"),
        _commit("bbb2222", "chore(deps): bump typer from 0.12.0 to 0.15.1"),
    ]
    merge = _commit("ccc3333", "Merge branch 'feature/export' into main")
    listing = render_listing(
        repo=Path_placeholder(),
        range_label="v0.1.0..v0.2.0",
        release="0.2.0",
        date="2026-02-10",
        drafts=[
            DraftItem(section=Section.added, summary="Add export.", commits=[kept], grouped=False),
            DraftItem(
                section=Section.changed,
                summary="Update dependencies.",
                commits=grouped,
                grouped=True,
            ),
        ],
        skipped=[SkippedCommit(commit=merge, reason="merge commit")],
    )
    assert "range: v0.1.0..v0.2.0" in listing
    assert "release: 0.2.0" in listing
    assert "commits: 4" in listing
    assert "notes: 2" in listing
    assert "skipped: 1" in listing
    assert "keep\tabc1234\t2026-02-10\tAdded\tAdd export." in listing
    assert "group\taaa1111,bbb2222\t2026-02-10\tChanged\tUpdate dependencies." in listing
    assert "skip\tccc3333\t2026-02-10\tmerge commit\tMerge branch 'feature/export' into main" in listing


def Path_placeholder():
    from pathlib import Path

    return Path("samples/demo-repo")
