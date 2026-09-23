"""The model is told, in the system prompt, not to invent history."""

from __future__ import annotations

from git_changelog.grouping import DraftItem
from git_changelog.models import Commit, Section
from git_changelog.prompts import SYSTEM_PROMPT, build_user_prompt

_FORBIDDEN = (
    "Do not fabricate features, pull requests, issue numbers, authors, or dates "
    "that are not in the commit input."
)


def test_system_prompt_forbids_fabricated_features_prs_and_dates() -> None:
    assert _FORBIDDEN in SYSTEM_PROMPT
    assert "Never invent a hash." in SYSTEM_PROMPT
    assert "Do not add a commit, a pull request, a version, or a release date." in SYSTEM_PROMPT
    for name in ("Added", "Changed", "Fixed", "Removed", "Security"):
        assert name in SYSTEM_PROMPT


def test_user_prompt_repeats_the_rule_and_only_lists_supplied_commits() -> None:
    commit = Commit(
        full_hash="abc1234abc1234abc1234abc1234abc1234abc",
        short_hash="abc1234",
        date="2026-02-02",
        subject="feat: add export",
        body="See pull request discussion in the commit: none.",
    )
    prompt = build_user_prompt(
        [DraftItem(section=Section.added, summary="Add export.", commits=[commit], grouped=False)],
        release="0.2.0",
        date="2026-02-10",
    )
    assert _FORBIDDEN in prompt
    assert "abc1234" in prompt
    assert "feat: add export" in prompt
    assert "0.2.0" in prompt
    assert "2026-02-10" in prompt
    assert "You may not add a feature" in prompt
