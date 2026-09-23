"""Collect commits with the system git binary. This module never invents commits."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from git_changelog.errors import GitError, GitMissingError, NotAGitRepoError, UsageError
from git_changelog.models import Commit

_RECORD = "\x1e"
_FIELD = "\x1f"
_PRETTY = f"%H{_FIELD}%h{_FIELD}%ad{_FIELD}%s{_FIELD}%b{_RECORD}"


@dataclass(frozen=True)
class History:
    """Commits in an exclusive..inclusive range, oldest first, plus heading facts."""

    commits: list[Commit]
    since_display: str
    until_display: str
    release: str
    date: str
    range_label: str


def find_git(git_bin: str | None = None) -> str:
    """Return a git executable or raise a message that says git is missing."""
    binary = git_bin or shutil.which("git")
    if not binary:
        raise GitMissingError(
            "git is not installed or not on PATH. Install git and run this command again."
        )
    return binary


def ensure_repo(repo: Path, git_bin: str | None = None) -> str:
    """Return the git binary after checking that `repo` is a git work tree."""
    git = find_git(git_bin)
    if not repo.exists():
        raise UsageError(f"Repository path does not exist: {repo}")
    if not repo.is_dir():
        raise UsageError(f"Repository path is not a directory: {repo}")
    result = _run([git, "-C", str(repo), "rev-parse", "--is-inside-work-tree"])
    if result.returncode != 0 or result.stdout.strip() != "true":
        raise NotAGitRepoError(
            f"{repo} is not a git repository. Pass a directory that contains a .git folder."
        )
    return git


def collect_history(
    repo: Path,
    *,
    since: str | None = None,
    until: str = "HEAD",
    limit: int = 50,
    release: str | None = None,
    git_bin: str | None = None,
) -> History:
    """Read commits with `git log`. `--since` is exclusive. `--until` is inclusive.

    With no `--since`, the start is the latest tag reachable from `--until`.
    When `--until` itself is that tag, the previous tag is the start so the
    range covers that release. With no tags, the last `limit` commits are used.
    """
    if limit < 1:
        raise UsageError("--limit must be at least 1.")
    git = ensure_repo(repo, git_bin)
    until_sha = _rev_parse(git, repo, until)
    until_date = _commit_date(git, repo, until_sha)
    tags_here = _tags_at(git, repo, until_sha)
    chosen_release = release.strip() if release and release.strip() else _release_name(tags_here)

    if since:
        since_sha = _rev_parse(git, repo, since)
        since_display = since
        log_args = [f"{since_sha}..{until_sha}"]
        range_label = f"{since_display}..{until}"
    else:
        latest = _describe_tag(git, repo, until_sha)
        if latest is None:
            since_display = f"last {limit} commits"
            log_args = ["-n", str(limit), until_sha]
            range_label = f"{since_display}..{until}"
        else:
            latest_sha = _rev_parse(git, repo, latest)
            if latest_sha == until_sha:
                previous = _describe_tag(git, repo, f"{until_sha}^")
                if previous is None:
                    since_display = f"last {limit} commits"
                    log_args = ["-n", str(limit), until_sha]
                    range_label = f"{since_display}..{until}"
                else:
                    previous_sha = _rev_parse(git, repo, previous)
                    since_display = previous
                    log_args = [f"{previous_sha}..{until_sha}"]
                    range_label = f"{previous}..{until}"
            else:
                since_display = latest
                log_args = [f"{latest_sha}..{until_sha}"]
                range_label = f"{latest}..{until}"

    commits = _git_log(git, repo, log_args)
    if not commits:
        raise UsageError(
            f"No commits in range {range_label}. "
            "The start revision is exclusive. If it points at the same commit as --until, "
            "choose an earlier --since."
        )
    return History(
        commits=commits,
        since_display=since_display,
        until_display=until,
        release=chosen_release,
        date=until_date,
        range_label=range_label,
    )


def parse_git_log(raw: str) -> list[Commit]:
    """Parse `git log --pretty=format:` output produced by this module."""
    commits: list[Commit] = []
    for record in raw.split(_RECORD):
        if not record.strip("\n"):
            continue
        parts = record.split(_FIELD)
        if len(parts) < 5:
            raise GitError(
                "Could not parse git log output. Expected hash, short hash, date, subject, and body."
            )
        full_hash, short_hash, date, subject = (part.strip() for part in parts[:4])
        body = _FIELD.join(parts[4:]).strip()
        if not full_hash or not short_hash or not date:
            raise GitError("git log returned a commit without a hash or date.")
        commits.append(
            Commit(
                full_hash=full_hash,
                short_hash=short_hash,
                date=date,
                subject=subject,
                body=body,
            )
        )
    return commits


def load_commit_fixture(path: Path) -> list[Commit]:
    """Load a recorded commit list (tests and offline demos). These are data, not live git."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UsageError(f"Could not read commit fixture {path}: {exc}") from exc
    if not isinstance(payload, list):
        raise UsageError(f"Commit fixture {path} must be a JSON list.")
    try:
        return [Commit.model_validate(item) for item in payload]
    except ValueError as exc:
        raise UsageError(f"Commit fixture {path} has an invalid commit: {exc}") from exc


def _git_log(git: str, repo: Path, log_args: list[str]) -> list[Commit]:
    result = _run(
        [
            git,
            "-C",
            str(repo),
            "log",
            "--reverse",
            "--date=short",
            f"--pretty=format:{_PRETTY}",
            *log_args,
        ]
    )
    if result.returncode != 0:
        raise GitError(_clean_git_error(result.stderr, "git log failed."))
    return parse_git_log(result.stdout)


def _rev_parse(git: str, repo: Path, rev: str) -> str:
    result = _run(
        [git, "-C", str(repo), "rev-parse", "--verify", "--end-of-options", f"{rev}^{{commit}}"]
    )
    if result.returncode != 0:
        message = _clean_git_error(result.stderr, "unknown revision")
        if rev in {"HEAD", "head"} and "unknown revision" in message:
            raise UsageError(f"{repo} has no commits yet.")
        raise GitError(f"Unknown revision {rev!r}. {message}")
    sha = result.stdout.strip()
    if not sha:
        raise GitError(f"Unknown revision {rev!r}.")
    return sha


def _commit_date(git: str, repo: Path, sha: str) -> str:
    result = _run([git, "-C", str(repo), "log", "-1", "--format=%ad", "--date=short", sha])
    if result.returncode != 0:
        raise GitError(_clean_git_error(result.stderr, "Could not read the commit date."))
    date = result.stdout.strip()
    if not date:
        raise GitError(f"Commit {sha} has no date.")
    return date


def _describe_tag(git: str, repo: Path, rev: str) -> str | None:
    result = _run([git, "-C", str(repo), "describe", "--tags", "--abbrev=0", rev])
    if result.returncode != 0:
        return None
    tag = result.stdout.strip()
    return tag or None


def _tags_at(git: str, repo: Path, sha: str) -> list[str]:
    result = _run([git, "-C", str(repo), "tag", "--points-at", sha])
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _release_name(tags: list[str]) -> str:
    if not tags:
        return "Unreleased"
    picked = sorted(tags, key=_version_sort_key)[-1]
    if picked.startswith("v") and len(picked) > 1 and picked[1].isdigit():
        return picked[1:]
    return picked


def _version_sort_key(tag: str) -> tuple[list[int], str]:
    stripped = tag[1:] if tag.startswith("v") else tag
    numbers = [int(piece) for piece in _split_numbers(stripped)]
    return (numbers, tag)


def _split_numbers(value: str) -> list[str]:
    numbers: list[str] = []
    current = ""
    for char in value:
        if char.isdigit():
            current += char
        elif current:
            numbers.append(current)
            current = ""
    if current:
        numbers.append(current)
    return numbers


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, check=False, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise GitMissingError(
            "git is not installed or not on PATH. Install git and run this command again."
        ) from exc


def _clean_git_error(stderr: str, fallback: str) -> str:
    text = stderr.strip()
    if not text:
        return fallback
    line = text.splitlines()[-1].strip()
    if line.lower().startswith("fatal:"):
        line = line.split(":", 1)[1].strip()
    return line or fallback
