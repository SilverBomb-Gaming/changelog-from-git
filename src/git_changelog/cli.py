"""Command-line interface for git-changelog."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

from git_changelog import __version__
from git_changelog.dotenv import load_dotenv
from git_changelog.errors import ChangelogError, GitError, GitMissingError, LLMError, NotAGitRepoError, UsageError
from git_changelog.generate import generate as generate_changelog
from git_changelog.llm import build_client
from git_changelog.render import section_body

app = typer.Typer(
    name="git-changelog",
    help="Turn git history into a Keep a Changelog markdown file.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"git-changelog {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
) -> None:
    """Turn git history into a Keep a Changelog markdown file."""


@app.command("generate")
def generate_cmd(
    repo: Annotated[
        Path,
        typer.Option("--repo", help="Git repository to read. Default: the current directory."),
    ] = Path("."),
    since: Annotated[
        Optional[str],
        typer.Option("--since", help="Start revision (exclusive). Default: latest tag, else last --limit commits."),
    ] = None,
    until: Annotated[
        str,
        typer.Option("--until", help="End revision (inclusive). Default: HEAD."),
    ] = "HEAD",
    limit: Annotated[
        int,
        typer.Option("--limit", help="How many commits to read when the repo has no usable tag."),
    ] = 50,
    release: Annotated[
        Optional[str],
        typer.Option(
            "--release",
            help="Version heading. Default: tag on --until with one leading v stripped, else Unreleased.",
        ),
    ] = None,
    out: Annotated[
        Optional[Path],
        typer.Option("--out", help="Also write the stdout text to this file. Replaces the file unless --append."),
    ] = None,
    append: Annotated[
        bool,
        typer.Option(
            "--append",
            help="With --out, append this release under an existing changelog instead of replacing the file.",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            "--raw",
            help="Print the collected commits and skip reasons. Do not call a model.",
        ),
    ] = False,
    no_llm: Annotated[
        bool,
        typer.Option(
            "--no-llm",
            help="Write Keep a Changelog markdown from commit subjects only. Do not call a model.",
        ),
    ] = False,
    include_noise: Annotated[
        bool,
        typer.Option(
            "--include-noise",
            help="Keep test and maintenance commits as Changed notes. Merges and empty subjects stay skipped.",
        ),
    ] = False,
    provider: Annotated[
        Optional[str],
        typer.Option("--provider", help="ollama (default) or openai. Overrides CHANGELOG_PROVIDER."),
    ] = None,
    model: Annotated[
        Optional[str],
        typer.Option("--model", help="Model name. Overrides OLLAMA_MODEL or OPENAI_MODEL for this command."),
    ] = None,
) -> None:
    """Collect commits and write a changelog to stdout."""
    try:
        _generate(
            repo=repo,
            since=since,
            until=until,
            limit=limit,
            release=release,
            out=out,
            append=append,
            dry_run=dry_run,
            no_llm=no_llm,
            include_noise=include_noise,
            provider=provider,
            model=model,
        )
    except UsageError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc
    except (GitMissingError, NotAGitRepoError, GitError, LLMError, ChangelogError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(2) from exc


def _generate(
    *,
    repo: Path,
    since: str | None,
    until: str,
    limit: int,
    release: str | None,
    out: Path | None,
    append: bool,
    dry_run: bool,
    no_llm: bool,
    include_noise: bool,
    provider: str | None,
    model: str | None,
) -> None:
    if append and out is None:
        raise UsageError("--append needs --out PATH. Stdout is always just this run's text.")
    if limit < 1:
        raise UsageError("--limit must be at least 1.")

    load_dotenv()
    use_llm = not dry_run and not no_llm
    client = build_client(provider, model) if use_llm else None
    try:
        result = generate_changelog(
            repo,
            since=since,
            until=until,
            limit=limit,
            release=release,
            include_noise=include_noise,
            client=client,
            use_llm=use_llm,
            require_notes=not dry_run,
        )
    finally:
        if client is not None:
            client.close()

    if result.skipped and not dry_run:
        noun = "commit" if result.skipped == 1 else "commits"
        typer.echo(
            f"Skipped {result.skipped} {noun} as noise. Re-run with --dry-run to list them.",
            err=True,
        )
    for warning in result.warnings:
        typer.echo(f"warning: {warning}", err=True)

    payload = result.listing if dry_run else result.markdown
    typer.echo(payload, nl=False)
    if out is not None:
        _write_out(out, payload, append=append)
        mode = "appended" if append else "replaced"
        typer.echo(f"Wrote {out} ({mode}).", err=True)


def _write_out(path: Path, payload: str, *, append: bool) -> None:
    if not path.parent.exists():
        raise UsageError(f"Directory does not exist: {path.parent}")
    if append and path.is_file() and path.stat().st_size > 0:
        existing = path.read_text(encoding="utf-8")
        addition = section_body(payload) if existing.lstrip().startswith("# Changelog") else payload
        separator = "" if existing.endswith("\n") else "\n"
        path.write_text(existing + separator + "\n" + addition, encoding="utf-8")
        return
    path.write_text(payload, encoding="utf-8")
