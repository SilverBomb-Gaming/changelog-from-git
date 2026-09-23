"""Bullets that do not cite a collected commit are dropped. Invented issue numbers are stripped."""

from __future__ import annotations

import json

from git_changelog.grouping import DraftItem
from git_changelog.guard import bullets_from_model, drafts_to_sections
from git_changelog.models import Commit, Section


def _commit(short: str, subject: str, body: str = "") -> Commit:
    return Commit(
        full_hash=(short + ("d" * 40))[:40],
        short_hash=short,
        date="2026-02-02",
        subject=subject,
        body=body,
    )


def _drafts() -> list[DraftItem]:
    return [
        DraftItem(
            section=Section.added,
            summary="Add export.",
            commits=[_commit("abc1234", "feat: add export")],
            grouped=False,
        ),
        DraftItem(
            section=Section.fixed,
            summary="Handle empty input.",
            commits=[_commit("def5678", "fix: handle empty input", body="Fixes #12 in the parser.")],
            grouped=False,
        ),
    ]


def test_unknown_hash_is_dropped_and_a_real_hash_is_kept() -> None:
    raw = json.dumps(
        {
            "sections": [
                {
                    "name": "Added",
                    "items": [
                        {"text": "Add export.", "commits": ["abc1234"]},
                        {"text": "Add a billing portal.", "commits": ["deadbee"]},
                    ],
                }
            ]
        }
    )
    sections, warnings = bullets_from_model(raw, _drafts())
    assert sections is not None
    bullets = sections[Section.added]
    assert len(bullets) == 1
    assert bullets[0].text == "Add export."
    assert bullets[0].commits[0].short_hash == "abc1234"
    assert any("Dropped 1" in warning for warning in warnings)


def test_fabricated_pull_request_number_is_removed() -> None:
    raw = json.dumps(
        {
            "sections": [
                {
                    "name": "Added",
                    "items": [{"text": "Add export (PR #99).", "commits": ["abc1234"]}],
                },
                {
                    "name": "Fixed",
                    "items": [{"text": "Handle empty input. Fixes #12.", "commits": ["def5678"]}],
                },
            ]
        }
    )
    sections, _warnings = bullets_from_model(raw, _drafts())
    assert sections is not None
    assert sections[Section.added][0].text == "Add export."
    assert "#99" not in sections[Section.added][0].text
    assert sections[Section.fixed][0].text == "Handle empty input. Fixes #12."


def test_unusable_json_returns_no_sections() -> None:
    sections, warnings = bullets_from_model("this is not json", _drafts())
    assert sections is None
    assert warnings


def test_fenced_json_and_full_hash_are_accepted() -> None:
    full = _drafts()[0].commits[0].full_hash
    raw = "```json\n" + json.dumps(
        {"sections": [{"name": "added", "items": [{"text": "Add export.", "commits": [full]}]}]}
    ) + "\n```"
    sections, _warnings = bullets_from_model(raw, _drafts())
    assert sections is not None
    assert sections[Section.added][0].commits[0].short_hash == "abc1234"


def test_draft_fallback_uses_the_commit_subjects() -> None:
    sections = drafts_to_sections(_drafts())
    assert sections[Section.added][0].text == "Add export."
    assert sections[Section.added][0].commits[0].subject == "feat: add export"
