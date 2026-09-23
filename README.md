# git-changelog by Alfredo Cardona (SilverBomb-Gaming)

A local-first CLI that reads a git repository and writes a [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) markdown file.

The default model path is [Ollama](https://ollama.com) on your machine (`llama3.2`). No cloud API key is required. Commit messages stay on localhost unless you opt into an OpenAI-compatible endpoint.

The installable project name is `changelog-from-git`. The command is `git-changelog`.

Built by Alfredo Cardona ([SilverBomb-Gaming](https://github.com/SilverBomb-Gaming)).

## In the owner's words

<!-- Replace this paragraph after merge. It is the one spot left for a human voice. -->

I wanted release notes I could check against `git log` without sending the repository to a hosted model. `--no-llm` still leans on conventional-commit prefixes, so a repo that never uses them will look flat until the Ollama pass rewrites the sentences. That limitation is the one I would explain first.

## What it is / isn't

**It is** a portfolio CLI for one job: take a real commit range and draft Added / Changed / Fixed / Removed / Security notes. Every bullet cites at least one hash collected from git. The release heading and the date come from git, not from the model.

**It isn't** a hosted changelog service, a GitHub Releases publisher, or a writer that may invent features, pull requests, or dates. If the model cites a hash this run did not collect, that bullet is dropped. If nothing usable comes back, the tool falls back to the commit subjects it already grouped.

## Demo

You need Python 3.11+ and git. Ollama is only required for the last command. The fixture is built locally. It does not clone a remote.

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .

python samples/make_demo_repo.py
```

That writes `samples/demo-repo`, a tiny fictional project (`fieldnotes`) with tags `v0.1.0` and `v0.2.0`. The directory is gitignored so this repository does not nest another `.git`.

See the commits the tool will use. This does not call a model. Each line is one collected commit: `keep`, `group`, or `skip`, then the hash, date, section or skip reason, and the original subject:

```bash
git-changelog generate --repo samples/demo-repo --since v0.1.0 --until v0.2.0 --dry-run
```

Write markdown from those subjects only (still no model). You should see `Update documentation.` and `Update dependencies.` as grouped notes, a Security note about redacting tokens, and no `Merge branch` line:

```bash
git-changelog generate --repo samples/demo-repo --since v0.1.0 --until v0.2.0 --no-llm
```

With Ollama, the same range is rewritten into user-facing sentences. Hashes in the file are still the ones from `--dry-run`:

```bash
ollama pull llama3.2
git-changelog generate --repo samples/demo-repo --since v0.1.0 --until v0.2.0 --out CHANGELOG.md
```

`--raw` is an alias of `--dry-run`.

Other ranges:

```bash
# Unreleased commits after the latest tag (v0.2.0 on the fixture)
git-changelog generate --repo samples/demo-repo --no-llm

# The release that v0.2.0 points at (previous tag .. that tag)
git-changelog generate --repo samples/demo-repo --until v0.2.0 --no-llm

# This repository, once it has history
git-changelog generate --repo . --no-llm
```

`--since` is exclusive. `--until` is inclusive and defaults to `HEAD`. With no `--since`, the start is the latest tag reachable from `--until`. If `--until` is itself that tag, the previous tag is the start, so the range covers that release. With no tags, the last `--limit` commits are used (default 50).

The heading is `--release` when you pass it (kept as you typed it). Otherwise it is the tag on `--until`, with one leading `v` removed when the next character is a digit (`v0.2.0` becomes `0.2.0`). If `--until` is not tagged, the heading is `Unreleased`. The date is the commit date of `--until`, so regenerating the same range on a later day does not change the heading.

## How a changelog is built

```text
git log  ──►  drop or group noise  ──►  optional model rewrite  ──►  markdown
(real hashes)   (this program)            (Ollama by default)         (this program)
```

1. **Collect.** `git log` supplies the hash, short hash, date, subject, and body. Nothing is added to that list.
2. **Group.** Merges and other noise are skipped. Dependency bumps in the same range become one Changed note. Docs commits become one Changed note when there are two or more. The rules are below.
3. **Rewrite, when you ask.** The model receives only the kept notes and must return JSON. The system prompt forbids fabricating features, pull requests, issue numbers, authors, or dates that are not in that input, and it forbids inventing a hash. Those sentences are pinned by `tests/test_prompts.py`.
4. **Check in code.** A bullet is kept only when every cited hash matches a commit collected in this run. A `#123` or `PR #123` is removed unless that number already appears in the cited commit's subject or body. The program, not the model, prints the heading, the date, and the hash citations.
5. **Fall back.** Unusable model output, or output with no grounded bullets, is replaced by the grouped commit subjects. A warning goes to stderr.

`--dry-run` / `--raw` stop after the listing. `--no-llm` writes the grouped markdown and does not open a client.

Section order is **Added, Changed, Fixed, Removed, Security**. Empty sections are omitted. There is no Deprecated section and no compare-link footer, because this tool does not invent a remote URL.

## Noise rules

Applied in order:

| Commit | What happens |
| --- | --- |
| Empty subject | Skipped |
| `Merge branch`, `Merge pull request`, `Merge remote-tracking branch`, `Merge tag` | Skipped. The merged commits are already in the log |
| Conventional `test` | Skipped |
| Conventional `chore`, `ci`, `build`, `style` | Skipped as maintenance |
| Dependency bump | One Changed note. A bump is a `deps` / `dependabot` scope, a subject like `bump <name> from <old> to <new>`, or the word `dependabot` / `dependencies`. Two or more become "Update dependencies." |
| Conventional `docs` | Kept. Two or more become "Update documentation." |
| `feat` | Added |
| `fix` | Fixed |
| `security` / `sec` | Security |
| `revert` | Removed |
| `refactor` / `perf` | Changed |
| No conventional prefix | Kept. A subject that starts with Add / Fix / Remove picks that section. Anything else is Changed. These are not treated as noise |

`--include-noise` keeps `test` and maintenance commits as their own Changed notes. Merges and empty subjects stay skipped.

`tests/fixtures/commits.json` is a recorded commit list (not a live repo) used to pin these rules without git.

## Output file

Stdout is always this run's text: the commit listing for `--dry-run`, or the generated markdown otherwise.

`--out CHANGELOG.md` **replaces** the file with that same text. Replace is the default so a generated range is one document you can read before you merge it by hand.

`--out CHANGELOG.md --append` appends instead. If the file already starts with `# Changelog`, the new `# Changelog` preamble is not repeated; the `## [version]` section is added under the existing one. The file is not deduped. Stdout is still only the new document, not the combined file. `--append` without `--out` is an error.

## Configuration

Copy `.env.example` to `.env` in the working directory (the directory you run the command from), or export the variables yourself. Existing environment variables win over `.env`.

| Variable | Default | Role |
| --- | --- | --- |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama server |
| `OLLAMA_MODEL` | `llama3.2` | Chat model |
| `OLLAMA_NUM_CTX` | `8192` | Context window sent to Ollama |
| `CHANGELOG_PROVIDER` | `ollama` | `ollama` or `openai` |
| `CHANGELOG_TIMEOUT` | `120` | Seconds for the model call |
| `OPENAI_API_KEY` | empty | Only for the OpenAI-compatible path |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Compatible base URL, usually ending in `/v1` |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model name for that path |

```bash
# Remote or local OpenAI-compatible server (LM Studio, a proxy, api.openai.com, …)
export CHANGELOG_PROVIDER=openai
export OPENAI_BASE_URL=https://api.openai.com/v1
export OPENAI_API_KEY=sk-...
export OPENAI_MODEL=gpt-4o-mini
git-changelog generate --repo samples/demo-repo --since v0.1.0 --until v0.2.0
```

`api.openai.com` refuses to run without `OPENAI_API_KEY`. A local compatible server may omit the key. `--provider` and `--model` override the environment for one command.

Narrow `--since` / `--until` if a long history does not fit in `OLLAMA_NUM_CTX`. Commit bodies sent to the model are truncated at 400 characters. The hashes are not.

## Scope / out of scope

**In scope**

- One git range, markdown only
- Ollama by default, OpenAI-compatible chat as an option
- A dry run and a no-model draft so you can see the commits before any model runs
- Bullets that each map back to a collected hash

**Out of scope**

- PDF and HTML export
- Publishing a GitHub Release, opening a pull request, or guessing a compare URL
- Inventing commits, features, pull requests, issue numbers, authors, or dates that are not in the collected input
- A guarantee that two models will phrase the same commit the same way. The hashes are the check

## Layout

```text
src/git_changelog/
  cli.py        # git-changelog generate …
  gitlog.py     # git log collection and the recorded-fixture loader
  grouping.py   # noise rules and conventional-commit sections
  prompts.py    # system prompt and the changelog task prompt
  guard.py      # drop bullets that do not cite a collected commit
  generate.py   # collect, optional rewrite, fallback
  render.py     # Keep a Changelog markdown and the dry-run listing
  llm.py        # Ollama and OpenAI-compatible clients
  demo.py       # builds the fixture repository
samples/
  make_demo_repo.py
tests/fixtures/commits.json
tests/          # pytest, no live model
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

`pytest` mocks the model client. It does not start Ollama and does not call the network. Git is required for the repository tests. Grouping, rendering, the no-fabrication prompt, and the hash guard also run from `tests/fixtures/commits.json` and in-memory commits.

Exit codes: `0` success, `1` bad input or an empty usable range, `2` git is missing, the path is not a repository, a revision does not exist, or the model provider failed.

## License

MIT © 2026 Alfredo Cardona
