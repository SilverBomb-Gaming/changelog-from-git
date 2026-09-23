"""CLI parsing and the paths that must not call a model."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from git_changelog.cli import app
from git_changelog.demo import SUBJECTS

runner = CliRunner()


def _text(result: object) -> str:
    output = getattr(result, "output", "") or ""
    stdout = getattr(result, "stdout", "") or ""
    stderr = getattr(result, "stderr", "") or ""
    return "\n".join(part for part in (output, stdout, stderr) if part)


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "git-changelog 0.1.0" in result.stdout


def test_help_lists_generate() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "generate" in result.stdout


def test_generate_help_documents_range_and_dry_run() -> None:
    result = runner.invoke(app, ["generate", "--help"])
    assert result.exit_code == 0
    text = result.stdout
    assert "--since" in text
    assert "--until" in text
    assert "--dry-run" in text
    assert "--raw" in text
    assert "--no-llm" in text
    assert "--append" in text
    assert "--out" in text


def test_dry_run_lists_commits_and_does_not_build_a_client(
    demo_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("dry-run must not build a model client")

    monkeypatch.setattr("git_changelog.cli.build_client", explode)
    result = runner.invoke(
        app,
        ["generate", "--repo", str(demo_repo), "--since", "v0.1.0", "--until", "v0.2.0", "--dry-run"],
    )
    assert result.exit_code == 0, _text(result)
    assert "range: v0.1.0..v0.2.0" in result.stdout
    assert "release: 0.2.0" in result.stdout
    assert SUBJECTS["merge"] in result.stdout
    assert "skip\t" in result.stdout
    assert "Update dependencies." in result.stdout
    assert "# Changelog" not in result.stdout


def test_raw_is_an_alias_of_dry_run(demo_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "git_changelog.cli.build_client",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("raw must not build a client")),
    )
    result = runner.invoke(app, ["generate", "--repo", str(demo_repo), "--raw"])
    assert result.exit_code == 0, _text(result)
    assert "range: v0.2.0..HEAD" in result.stdout
    assert SUBJECTS["range"] in result.stdout


def test_no_llm_writes_markdown_without_a_client(demo_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "git_changelog.cli.build_client",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no-llm must not build a client")),
    )
    result = runner.invoke(
        app,
        ["generate", "--repo", str(demo_repo), "--until", "v0.2.0", "--no-llm"],
    )
    assert result.exit_code == 0, _text(result)
    assert result.stdout.startswith("# Changelog\n")
    assert "## [0.2.0] - 2026-02-10" in result.stdout
    assert "### Security\n" in result.stdout
    assert "Skipped " in (result.stderr or "")


def test_out_replaces_and_append_adds_a_section(demo_repo: Path, tmp_path: Path) -> None:
    destination = tmp_path / "CHANGELOG.md"
    first = runner.invoke(
        app,
        [
            "generate",
            "--repo",
            str(demo_repo),
            "--until",
            "v0.2.0",
            "--no-llm",
            "--out",
            str(destination),
        ],
    )
    assert first.exit_code == 0, _text(first)
    assert destination.read_text(encoding="utf-8") == first.stdout
    assert "replaced" in (first.stderr or "")

    second = runner.invoke(
        app,
        [
            "generate",
            "--repo",
            str(demo_repo),
            "--since",
            "v0.2.0",
            "--no-llm",
            "--out",
            str(destination),
            "--append",
        ],
    )
    assert second.exit_code == 0, _text(second)
    combined = destination.read_text(encoding="utf-8")
    assert combined.count("# Changelog\n") == 1
    assert "## [0.2.0] - 2026-02-10" in combined
    assert "## [Unreleased] - 2026-03-03" in combined
    assert "Select notes with --since and --until." in combined
    assert second.stdout.startswith("# Changelog\n")
    assert "appended" in (second.stderr or "")


def test_append_requires_out(demo_repo: Path) -> None:
    result = runner.invoke(app, ["generate", "--repo", str(demo_repo), "--no-llm", "--append"])
    assert result.exit_code == 1
    assert "--append needs --out" in _text(result)


def test_not_a_git_repo(tmp_path: Path) -> None:
    result = runner.invoke(app, ["generate", "--repo", str(tmp_path), "--no-llm"])
    assert result.exit_code == 2
    assert "not a git repository" in _text(result)


def test_git_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("git_changelog.gitlog.shutil.which", lambda _name: None)
    result = runner.invoke(app, ["generate", "--repo", str(tmp_path), "--dry-run"])
    assert result.exit_code == 2
    assert "not on PATH" in _text(result)


def test_unknown_revision_exits_2(demo_repo: Path) -> None:
    result = runner.invoke(
        app,
        ["generate", "--repo", str(demo_repo), "--since", "no-such-tag", "--no-llm"],
    )
    assert result.exit_code == 2
    assert "Unknown revision" in _text(result)


def test_limit_must_be_positive(demo_repo: Path) -> None:
    result = runner.invoke(app, ["generate", "--repo", str(demo_repo), "--limit", "0", "--no-llm"])
    assert result.exit_code == 1
    assert "--limit must be at least 1" in _text(result)


def test_include_noise_keeps_the_unreleased_chore(demo_repo: Path) -> None:
    result = runner.invoke(
        app,
        ["generate", "--repo", str(demo_repo), "--no-llm", "--include-noise"],
    )
    assert result.exit_code == 0, _text(result)
    assert "Cover dry-run without a model." in result.stdout
    assert "Bump package version to 0.3.0." in result.stdout
    assert "Merge branch" not in result.stdout
