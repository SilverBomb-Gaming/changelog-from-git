"""Collect commits, optionally ask a model to rewrite them, and render markdown."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from git_changelog.errors import UsageError
from git_changelog.grouping import prepare_commits
from git_changelog.guard import bullets_from_model, drafts_to_sections
from git_changelog.llm import LLMClient, build_client
from git_changelog.models import ChangelogDocument
from git_changelog.prompts import SYSTEM_PROMPT, build_user_prompt
from git_changelog.gitlog import History, collect_history
from git_changelog.render import render_listing, render_markdown


@dataclass
class GenerateResult:
    """Stdout payload plus warnings the CLI prints on stderr."""

    markdown: str
    listing: str
    warnings: list[str] = field(default_factory=list)
    used_llm: bool = False
    skipped: int = 0
    notes: int = 0
    release: str = ""
    date: str = ""


def generate(
    repo: Path,
    *,
    since: str | None = None,
    until: str = "HEAD",
    limit: int = 50,
    release: str | None = None,
    include_noise: bool = False,
    client: LLMClient | None = None,
    use_llm: bool = False,
    require_notes: bool = True,
) -> GenerateResult:
    """Build a changelog for one git range.

    `use_llm` asks the model to rewrite draft notes. Bullets that do not cite a
    collected commit are dropped. If none remain, the draft from commit subjects
    is used instead. `--dry-run` passes `require_notes=False` so a noise-only
    range still prints the commit listing.
    """
    history = collect_history(
        repo,
        since=since,
        until=until,
        limit=limit,
        release=release,
        git_bin=None,
    )
    return generate_from_history(
        history,
        repo=repo,
        include_noise=include_noise,
        client=client,
        use_llm=use_llm,
        require_notes=require_notes,
    )


def generate_from_history(
    history: History,
    *,
    repo: Path,
    include_noise: bool = False,
    client: LLMClient | None = None,
    use_llm: bool = False,
    require_notes: bool = True,
) -> GenerateResult:
    drafts, skipped = prepare_commits(history.commits, include_noise=include_noise)
    listing = render_listing(
        repo=repo,
        range_label=history.range_label,
        release=history.release,
        date=history.date,
        drafts=drafts,
        skipped=skipped,
    )
    if not drafts and require_notes:
        raise UsageError(
            "Every commit in this range was skipped as noise "
            "(empty subjects, merges, test-only commits, or maintenance). "
            "Pass --include-noise to keep test and maintenance commits, or widen the range."
        )

    warnings: list[str] = []
    used_llm = False
    sections = drafts_to_sections(drafts)
    if use_llm and drafts:
        active = client if client is not None else build_client()
        owns_client = client is None
        try:
            raw = active.complete(
                system=SYSTEM_PROMPT,
                user=build_user_prompt(drafts, release=history.release, date=history.date),
            )
        finally:
            if owns_client:
                active.close()
        used_llm = True
        model_sections, warnings = bullets_from_model(raw, drafts)
        if model_sections is None:
            warnings.append("Used commit subjects instead.")
            sections = drafts_to_sections(drafts)
        else:
            sections = model_sections

    document = ChangelogDocument(release=history.release, date=history.date, sections=sections)
    return GenerateResult(
        markdown=render_markdown(document),
        listing=listing,
        warnings=warnings,
        used_llm=used_llm,
        skipped=len(skipped),
        notes=len(drafts),
        release=history.release,
        date=history.date,
    )
