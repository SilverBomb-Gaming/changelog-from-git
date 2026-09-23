"""Build the tiny local git history used by the README demo and the tests.

The repository is fictional (a notes command called fieldnotes). Dates and
subjects are fixed. Commit hashes are whatever git assigns; tests assert on
subjects and tags, not on hash values.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

SUBJECTS = {
    "skeleton": "chore: initial project skeleton",
    "notes": "feat: add a local notes command",
    "missing_file": "fix: fail clearly when the notes file is missing",
    "group": "feat: group related notes into one entry",
    "source_id": "fix: keep each entry tied to its source id",
    "docs": "docs: document the default local store",
    "docs_env": "docs: document environment variables",
    "httpx": "chore(deps): bump httpx from 0.27.0 to 0.28.1",
    "typer": "chore(deps): bump typer from 0.12.0 to 0.15.1",
    "export": "feat: export notes to markdown",
    "merge": "Merge branch 'feature/export' into main",
    "security": "security: redact tokens before notes are printed",
    "refactor": "refactor: split rendering from storage",
    "range": "feat: select notes with --since and --until",
    "test": "test: cover dry-run without a model",
    "version": "chore: bump package version to 0.3.0",
}


def build_demo_repo(dest: Path) -> Path:
    """Create `dest` as a git repo with tags v0.1.0 and v0.2.0. Replaces `dest`."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    _run(["git", "init", "-b", "main", str(dest)])
    _git(dest, "config", "user.email", "demo@example.com")
    _git(dest, "config", "user.name", "Demo Author")
    _git(dest, "config", "commit.gpgsign", "false")
    _git(dest, "config", "tag.gpgsign", "false")

    _commit(dest, "README.md", "# fieldnotes\n\nDemo history for git-changelog.\n", SUBJECTS["skeleton"], "2026-01-10")
    _commit(
        dest,
        "notes.py",
        "def add_note(text: str) -> None:\n    print(text)\n",
        SUBJECTS["notes"],
        "2026-01-12",
    )
    _commit(
        dest,
        "notes.py",
        "def add_note(path: str, text: str) -> None:\n"
        "    if not path:\n"
        "        raise SystemExit('notes file is missing')\n"
        "    print(text)\n",
        SUBJECTS["missing_file"],
        "2026-01-13",
    )
    _git(dest, "tag", "v0.1.0")

    _commit(
        dest,
        "group.py",
        "def group(items: list[str]) -> list[str]:\n    return items\n",
        SUBJECTS["group"],
        "2026-02-02",
    )
    _commit(
        dest,
        "group.py",
        "def group(items: list[tuple[str, str]]) -> list[str]:\n"
        "    return [text for _id, text in items]\n",
        SUBJECTS["source_id"],
        "2026-02-03",
    )
    _commit(
        dest,
        "README.md",
        "# fieldnotes\n\nNotes stay in a local file. There is no remote store.\n",
        SUBJECTS["docs"],
        "2026-02-04",
    )
    _commit(
        dest,
        "README.md",
        "# fieldnotes\n\nNotes stay in a local file. Set FIELDNOTES_PATH to override it.\n",
        SUBJECTS["docs_env"],
        "2026-02-04",
    )
    _commit(dest, "requirements.txt", "httpx==0.28.1\n", SUBJECTS["httpx"], "2026-02-05")
    _commit(dest, "requirements.txt", "httpx==0.28.1\ntyper==0.15.1\n", SUBJECTS["typer"], "2026-02-06")

    _git(dest, "checkout", "-b", "feature/export")
    _commit(
        dest,
        "export.py",
        "def to_markdown(lines: list[str]) -> str:\n    return '\\n'.join(f'- {line}' for line in lines)\n",
        SUBJECTS["export"],
        "2026-02-07",
    )
    _git(dest, "checkout", "main")
    _git(dest, "merge", "--no-ff", "feature/export", "-m", SUBJECTS["merge"], date="2026-02-08")
    _commit(
        dest,
        "export.py",
        "import re\n\n"
        "def to_markdown(lines: list[str]) -> str:\n"
        "    cleaned = [re.sub(r'ghp_[A-Za-z0-9]+', '[redacted]', line) for line in lines]\n"
        "    return '\\n'.join(f'- {line}' for line in cleaned)\n",
        SUBJECTS["security"],
        "2026-02-09",
    )
    _commit(
        dest,
        "render.py",
        "def render(lines: list[str]) -> str:\n    return '\\n'.join(lines)\n",
        SUBJECTS["refactor"],
        "2026-02-10",
    )
    _git(dest, "tag", "v0.2.0")

    _commit(
        dest,
        "range.py",
        "def select(since: str, until: str) -> tuple[str, str]:\n    return since, until\n",
        SUBJECTS["range"],
        "2026-03-01",
    )
    _commit(
        dest,
        "test_dry_run.py",
        "def test_dry_run() -> None:\n    assert True\n",
        SUBJECTS["test"],
        "2026-03-02",
    )
    _commit(
        dest,
        "pyproject.toml",
        '[project]\nname = "fieldnotes"\nversion = "0.3.0"\n',
        SUBJECTS["version"],
        "2026-03-03",
    )
    return dest


def _commit(dest: Path, name: str, content: str, message: str, date: str) -> None:
    path = dest / name
    path.write_text(content, encoding="utf-8")
    _git(dest, "add", name)
    _git(dest, "commit", "-m", message, date=date)


def _git(dest: Path, *args: str, date: str | None = None) -> str:
    return _run(["git", "-C", str(dest), *args], date=date).stdout


def _run(args: list[str], date: str | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "Demo Author"
    env["GIT_AUTHOR_EMAIL"] = "demo@example.com"
    env["GIT_COMMITTER_NAME"] = "Demo Author"
    env["GIT_COMMITTER_EMAIL"] = "demo@example.com"
    if date:
        stamp = f"{date}T12:00:00"
        env["GIT_AUTHOR_DATE"] = stamp
        env["GIT_COMMITTER_DATE"] = stamp
    result = subprocess.run(args, check=False, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"{' '.join(args)} failed: {detail}")
    return result
