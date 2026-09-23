"""End-to-end generation with a fake model. No network and no Ollama."""

from __future__ import annotations

import json
from pathlib import Path

from git_changelog.demo import SUBJECTS
from git_changelog.generate import generate
from git_changelog.prompts import SYSTEM_PROMPT


class FakeClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[tuple[str, str]] = []
        self.closed = False

    def complete(self, *, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.content

    def close(self) -> None:
        self.closed = True


def test_no_llm_markdown_cites_only_collected_commits(demo_repo: Path) -> None:
    result = generate(demo_repo, since="v0.1.0", until="v0.2.0", use_llm=False)
    assert result.used_llm is False
    assert "## [0.2.0] - 2026-02-10" in result.markdown
    assert "Update documentation." in result.markdown
    assert "Update dependencies." in result.markdown
    assert "Redact tokens before notes are printed." in result.markdown
    assert "Export notes to markdown." in result.markdown
    assert "Merge branch" not in result.markdown
    assert "bump httpx" not in result.markdown
    assert SUBJECTS["notes"] not in result.markdown
    assert SUBJECTS["range"] not in result.markdown
    _assert_every_bullet_cites_a_collected_hash(result.markdown, result.listing)


def test_model_rewrite_is_kept_when_hashes_are_real(demo_repo: Path) -> None:
    preview = generate(demo_repo, since="v0.1.0", until="v0.2.0", use_llm=False)
    export_hash = _hash_for(preview.listing, "Export notes to markdown.")
    security_hash = _hash_for(preview.listing, "Redact tokens before notes are printed.")
    client = FakeClient(
        json.dumps(
            {
                "sections": [
                    {
                        "name": "Added",
                        "items": [
                            {
                                "text": "Export notes as markdown.",
                                "commits": [export_hash],
                            }
                        ],
                    },
                    {
                        "name": "Security",
                        "items": [
                            {
                                "text": "Redact tokens before printing notes.",
                                "commits": [security_hash],
                            }
                        ],
                    },
                ]
            }
        )
    )
    result = generate(demo_repo, since="v0.1.0", until="v0.2.0", use_llm=True, client=client)
    assert result.used_llm is True
    assert client.calls[0][0] == SYSTEM_PROMPT
    assert "Do not fabricate features, pull requests" in client.calls[0][0]
    assert "Merge branch" not in client.calls[0][1]
    assert export_hash in client.calls[0][1]
    assert "Export notes as markdown." in result.markdown
    assert f"`{export_hash}`" in result.markdown
    assert f"`{security_hash}`" in result.markdown
    assert "Add a billing portal" not in result.markdown
    _assert_every_bullet_cites_a_collected_hash(result.markdown, result.listing)


def test_invented_hash_falls_back_to_commit_subjects(demo_repo: Path) -> None:
    client = FakeClient(
        json.dumps(
            {
                "sections": [
                    {
                        "name": "Added",
                        "items": [
                            {
                                "text": "Launch a hosted billing portal on 2019-01-01 via PR #500.",
                                "commits": ["deadbeef"],
                            }
                        ],
                    }
                ]
            }
        )
    )
    result = generate(demo_repo, since="v0.2.0", until="HEAD", use_llm=True, client=client)
    assert "billing portal" not in result.markdown
    assert "PR #500" not in result.markdown
    assert "2019-01-01" not in result.markdown
    assert "Select notes with --since and --until." in result.markdown
    assert any("no bullets tied to collected commits" in warning for warning in result.warnings)
    assert any("Used commit subjects instead." in warning for warning in result.warnings)
    _assert_every_bullet_cites_a_collected_hash(result.markdown, result.listing)


def test_garbage_model_output_falls_back(demo_repo: Path) -> None:
    client = FakeClient("sure, here is a changelog:\n- invented feature")
    result = generate(demo_repo, until="v0.1.0", use_llm=True, client=client)
    assert "invented feature" not in result.markdown.lower()
    assert "Add a local notes command." in result.markdown
    assert any("not usable" in warning for warning in result.warnings)


def _hash_for(listing: str, summary: str) -> str:
    for line in listing.splitlines():
        if line.endswith("\t" + summary):
            return line.split("\t")[1].split(",")[0]
    raise AssertionError(f"summary not in listing: {summary}")


def _assert_every_bullet_cites_a_collected_hash(markdown: str, listing: str) -> None:
    allowed = set()
    for line in listing.splitlines():
        parts = line.split("\t")
        if parts and parts[0] in {"keep", "group", "skip"}:
            allowed.update(parts[1].split(","))
    bullets = [line for line in markdown.splitlines() if line.startswith("- ")]
    assert bullets
    for bullet in bullets:
        cited = [token.strip("`") for token in bullet.split("`")[1::2]]
        assert cited, bullet
        assert all(token in allowed for token in cited), bullet
