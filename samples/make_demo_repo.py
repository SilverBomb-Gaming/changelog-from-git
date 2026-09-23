#!/usr/bin/env python3
"""Create samples/demo-repo, a tiny local git history for the README demo.

No remote is used. Re-running this script replaces samples/demo-repo.
"""

from pathlib import Path

from git_changelog.demo import build_demo_repo


def main() -> None:
    dest = Path(__file__).resolve().parent / "demo-repo"
    build_demo_repo(dest)
    print(dest)


if __name__ == "__main__":
    main()
