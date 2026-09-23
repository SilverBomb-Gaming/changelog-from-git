"""Noise rules: merges are dropped, dependency bumps fold into one note."""

from __future__ import annotations

from pathlib import Path

from git_changelog.gitlog import load_commit_fixture
from git_changelog.grouping import (
    SKIP_EMPTY,
    SKIP_MAINTENANCE,
    SKIP_MERGE,
    SKIP_TEST,
    clean_subject,
    prepare_commits,
)
from git_changelog.models import Commit, Section

FIXTURE = Path(__file__).parent / "fixtures" / "commits.json"


def _commit(short: str, subject: str) -> Commit:
    return Commit(
        full_hash=short + ("a" * (40 - len(short))),
        short_hash=short,
        date="2026-02-01",
        subject=subject,
    )


def test_recorded_fixture_groups_docs_and_dependencies() -> None:
    drafts, skipped = prepare_commits(load_commit_fixture(FIXTURE))
    summaries = [(draft.section, draft.summary, [commit.short_hash for commit in draft.commits]) for draft in drafts]
    assert summaries == [
        (Section.added, "Add export.", ["1111111"]),
        (Section.fixed, "Handle empty input.", ["2222222"]),
        (Section.changed, "Update documentation.", ["3333333", "4444444"]),
        (Section.changed, "Update dependencies.", ["5555555", "6666666"]),
        (Section.security, "Redact tokens before print.", ["8888888"]),
        (Section.changed, "Split render from collect.", ["bbbbbbb"]),
    ]
    reasons = {item.commit.short_hash: item.reason for item in skipped}
    assert reasons == {
        "7777777": SKIP_MERGE,
        "9999999": SKIP_TEST,
        "aaaaaaa": SKIP_MAINTENANCE,
        "ccccccc": SKIP_EMPTY,
    }
    assert all(item.grouped for item in drafts if "Update " in item.summary)


def test_plain_subjects_are_kept_and_not_treated_as_noise() -> None:
    drafts, skipped = prepare_commits(
        [
            _commit("abc1234", "Add a status line"),
            _commit("def5678", "Fix the crash on empty input"),
            _commit("aaa1111", "Remove the legacy flag"),
            _commit("bbb2222", "Ship the weekend build"),
        ]
    )
    assert skipped == []
    assert [draft.section for draft in drafts] == [
        Section.added,
        Section.fixed,
        Section.removed,
        Section.changed,
    ]


def test_include_noise_keeps_tests_and_chores_but_not_merges() -> None:
    commits = [
        _commit("abc1234", "test: cover the parser"),
        _commit("def5678", "chore: tidy the makefile"),
        _commit("aaa1111", "Merge pull request #4 from demo/export"),
    ]
    drafts, skipped = prepare_commits(commits, include_noise=True)
    assert [draft.summary for draft in drafts] == ["Cover the parser.", "Tidy the makefile."]
    assert [item.reason for item in skipped] == [SKIP_MERGE]
    assert all(draft.section is Section.changed for draft in drafts)


def test_single_dependency_keeps_its_subject() -> None:
    drafts, skipped = prepare_commits(
        [_commit("abc1234", "chore(deps): bump httpx from 0.27.0 to 0.28.1")]
    )
    assert skipped == []
    assert drafts[0].grouped is False
    assert drafts[0].summary == "Bump httpx from 0.27.0 to 0.28.1."


def test_revert_lands_in_removed() -> None:
    drafts, _skipped = prepare_commits([_commit("abc1234", "revert: drop the export flag")])
    assert drafts[0].section is Section.removed
    assert drafts[0].summary == "Drop the export flag."


def test_clean_subject_capitalizes_and_adds_a_period() -> None:
    assert clean_subject("feat: add a local notes command") == "Add a local notes command."
    assert clean_subject("Already done!") == "Already done!"
