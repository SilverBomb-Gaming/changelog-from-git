"""Prompts for the changelog rewrite. The program, not the model, owns hashes and the date."""

from __future__ import annotations

from git_changelog.grouping import DraftItem

SYSTEM_PROMPT = """You write Keep a Changelog notes from git commits the user supplies.

Rules:
- Do not fabricate features, pull requests, issue numbers, authors, or dates that are not in the commit input.
- Every bullet must name one or more commit hashes copied from the input. Never invent a hash.
- Do not add a commit, a pull request, a version, or a release date. The program adds the heading.
- If a feature, fix, or removal is not described by a commit below, leave it out.
- Use only these section names: Added, Changed, Fixed, Removed, Security.
- If the input does not support a section, omit it.
- Return a single JSON object and nothing else.
"""

_SCHEMA = """{
  "sections": [
    {
      "name": "Added",
      "items": [
        {
          "text": "One user-facing sentence. No hash. No pull request number unless that number is in the commit text.",
          "commits": ["<short or full hash copied from the input>"]
        }
      ]
    }
  ]
}"""


def build_user_prompt(drafts: list[DraftItem], *, release: str, date: str) -> str:
    """Ask the model to rewrite draft notes. Hashes in this prompt are the only legal citations."""
    listing = _format_drafts(drafts)
    return f"""TASK: changelog

Rewrite the notes below into Keep a Changelog bullets for release {release} dated {date}.
That release and date are already chosen from git. Do not invent another version or date.

Return a JSON object with this shape:
{_SCHEMA}

Rules for this task:
- Use only hashes that appear below. If you cannot cite one, omit the bullet.
- You may merge several rows from the same section into one bullet. The commits array must list every hash you merged.
- You may drop a row that is not user-facing. You may not add a feature, fix, pull request, or hash.
- text is one sentence. Do not put a hash in the text. The program prints the hashes.
- Section name must be exactly one of: Added, Changed, Fixed, Removed, Security.
- Do not fabricate features, pull requests, issue numbers, authors, or dates that are not in the commit input.

COMMITS
{listing}
"""


def _format_drafts(drafts: list[DraftItem]) -> str:
    blocks: list[str] = []
    for index, draft in enumerate(drafts, start=1):
        hashes = ", ".join(commit.short_hash for commit in draft.commits)
        full = ", ".join(commit.full_hash for commit in draft.commits)
        lines = [
            f"[{index}] hashes: {hashes}",
            f"    full: {full}",
            f"    section: {draft.section.value}",
            f"    suggested_summary: {draft.summary}",
            "    commits:",
        ]
        for commit in draft.commits:
            lines.append(f"    - {commit.short_hash} {commit.date} {commit.subject}")
            body = commit.body.strip()
            if body:
                trimmed = body if len(body) <= 400 else body[:400].rstrip() + "…"
                for body_line in trimmed.splitlines():
                    lines.append(f"      {body_line}")
        blocks.append("\n".join(lines))
    return "\n".join(blocks)
