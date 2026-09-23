"""A project .env fills in missing variables and does not override the environment."""

from __future__ import annotations

import os
from pathlib import Path

from git_changelog.dotenv import load_dotenv


def test_dotenv_sets_missing_keys_and_keeps_existing_ones(
    tmp_path: Path,
    monkeypatch,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "# comment",
                "OLLAMA_MODEL=from-file",
                "CHANGELOG_PROVIDER=openai",
                "OPENAI_API_KEY=\"secret\"",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("OLLAMA_MODEL", "from-env")
    monkeypatch.delenv("CHANGELOG_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    load_dotenv(env_file)
    assert os.environ["OLLAMA_MODEL"] == "from-env"
    assert os.environ["CHANGELOG_PROVIDER"] == "openai"
    assert os.environ["OPENAI_API_KEY"] == "secret"
