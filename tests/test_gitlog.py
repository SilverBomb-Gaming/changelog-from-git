"""Git collection: parse real history, and fail clearly when git or the repo is unusable."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from git_changelog.demo import SUBJECTS
from git_changelog.errors import GitError, GitMissingError, NotAGitRepoError, UsageError
from git_changelog.gitlog import collect_history, parse_git_log


def test_parse_git_log_keeps_multiline_bodies() -> None:
    raw = (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\x1f"
        "aaaaaaa\x1f2026-02-02\x1ffeat: add export\x1f"
        "Line one\nLine two\x1e"
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\x1f"
        "bbbbbbb\x1f2026-02-03\x1ffix: crash\x1f\x1e"
    )
    commits = parse_git_log(raw)
    assert len(commits) == 2
    assert commits[0].subject == "feat: add export"
    assert commits[0].body == "Line one\nLine two"
    assert commits[1].body == ""
    assert commits[1].short_hash == "bbbbbbb"


def test_parse_git_log_rejects_a_short_record() -> None:
    with pytest.raises(GitError, match="Could not parse"):
        parse_git_log("only-one-field\x1e")


def test_demo_range_since_tag_is_exclusive(demo_repo: Path) -> None:
    history = collect_history(demo_repo, since="v0.1.0", until="v0.2.0")
    subjects = [commit.subject for commit in history.commits]
    assert SUBJECTS["notes"] not in subjects
    assert SUBJECTS["export"] in subjects
    assert SUBJECTS["merge"] in subjects
    assert SUBJECTS["range"] not in subjects
    assert history.release == "0.2.0"
    assert history.date == "2026-02-10"
    assert history.range_label == "v0.1.0..v0.2.0"


def test_until_tag_walks_back_to_the_previous_tag(demo_repo: Path) -> None:
    history = collect_history(demo_repo, until="v0.2.0")
    assert history.since_display == "v0.1.0"
    assert history.release == "0.2.0"
    assert any(commit.subject == SUBJECTS["security"] for commit in history.commits)


def test_first_tag_falls_back_to_recent_commits(demo_repo: Path) -> None:
    history = collect_history(demo_repo, until="v0.1.0", limit=50)
    subjects = [commit.subject for commit in history.commits]
    assert subjects[0] == SUBJECTS["skeleton"]
    assert SUBJECTS["notes"] in subjects
    assert SUBJECTS["missing_file"] in subjects
    assert SUBJECTS["export"] not in subjects
    assert history.release == "0.1.0"
    assert history.date == "2026-01-13"
    assert history.since_display == "last 50 commits"


def test_default_range_is_after_the_latest_tag(demo_repo: Path) -> None:
    history = collect_history(demo_repo)
    subjects = [commit.subject for commit in history.commits]
    assert subjects == [SUBJECTS["range"], SUBJECTS["test"], SUBJECTS["version"]]
    assert history.release == "Unreleased"
    assert history.date == "2026-03-03"
    assert history.since_display == "v0.2.0"


def test_release_override_is_kept_verbatim(demo_repo: Path) -> None:
    history = collect_history(demo_repo, until="v0.2.0", release="v0.2.0")
    assert history.release == "v0.2.0"


def test_unknown_revision(demo_repo: Path) -> None:
    with pytest.raises(GitError, match="Unknown revision 'no-such-tag'"):
        collect_history(demo_repo, since="no-such-tag")


def test_empty_range(demo_repo: Path) -> None:
    with pytest.raises(UsageError, match="No commits in range"):
        collect_history(demo_repo, since="HEAD", until="HEAD")


def test_path_is_not_a_git_repo(tmp_path: Path) -> None:
    with pytest.raises(NotAGitRepoError, match="not a git repository"):
        collect_history(tmp_path)


def test_path_does_not_exist(tmp_path: Path) -> None:
    with pytest.raises(UsageError, match="does not exist"):
        collect_history(tmp_path / "missing")


def test_git_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("git_changelog.gitlog.shutil.which", lambda _name: None)
    with pytest.raises(GitMissingError, match="not on PATH"):
        collect_history(tmp_path)


def test_limit_keeps_the_newest_commits_when_there_are_no_tags(tmp_path: Path) -> None:
    repo = tmp_path / "plain"
    _git_repo_with_commits(repo, ["one", "two", "three"])
    history = collect_history(repo, limit=2)
    assert [commit.subject for commit in history.commits] == ["two", "three"]
    assert history.release == "Unreleased"
    assert history.since_display == "last 2 commits"


def test_repo_with_no_commits(tmp_path: Path) -> None:
    repo = tmp_path / "empty"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
    with pytest.raises(UsageError, match="no commits"):
        collect_history(repo)


def _git_repo_with_commits(repo: Path, subjects: list[str]) -> None:
    repo.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "Demo Author",
            "GIT_AUTHOR_EMAIL": "demo@example.com",
            "GIT_COMMITTER_NAME": "Demo Author",
            "GIT_COMMITTER_EMAIL": "demo@example.com",
        }
    )
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "demo@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Demo Author"], check=True)
    for index, subject in enumerate(subjects, start=1):
        (repo / "NOTES.md").write_text(f"line {index}\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "NOTES.md"], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", subject],
            check=True,
            capture_output=True,
            env=env,
        )
