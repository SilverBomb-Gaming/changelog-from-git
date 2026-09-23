"""Shared git fixture. Built once per session; tests only read it."""

from __future__ import annotations

from pathlib import Path

import pytest

from git_changelog.demo import build_demo_repo


@pytest.fixture(scope="session")
def demo_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    dest = tmp_path_factory.mktemp("fieldnotes") / "demo-repo"
    return build_demo_repo(dest)
