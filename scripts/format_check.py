#!/usr/bin/env python3
"""Check that changed files are formatted, without forcing a reformat of old code.

    python scripts/format_check.py --base origin/main          # CI: PR head vs its base
    python scripts/format_check.py --staged                     # pre-commit: index vs HEAD

Python is checked with Ruff (ruff.toml) and the frontend with Prettier
(frontend/.prettierrc.json). Most of the repository predates the standard, so a
changed file fails only if it was formatted before the change, or is new, and is
not formatted now. A file that was already unformatted on the base is reported as a
notice and left alone, so touching it never forces a whole-file reformat on top of
open branches. The one-time full reformat removes the exemption by itself.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUFF_VERSION = "0.17.6"  # keep in sync with .pre-commit-config.yaml and CI
PRETTIER_BIN = ROOT / "frontend" / "node_modules" / ".bin" / "prettier"
PRETTIER_SUFFIXES = {".js", ".mjs", ".vue", ".css", ".json", ".html"}
PRETTIER_SKIP = {"frontend/package-lock.json"}


def git(*args: str, text: bool = True):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=text, check=False)


def tool_for(path: str) -> str | None:
    if path.endswith(".py"):
        return "ruff"
    if (
        path.startswith("frontend/")
        and Path(path).suffix in PRETTIER_SUFFIXES
        and path not in PRETTIER_SKIP
        and "/dist/" not in path
    ):
        return "prettier"
    return None


def formatted(path: str, content: str, tool: str) -> bool:
    """Whether `content`, as the file `path`, is already what the formatter would write."""
    if tool == "ruff":
        runner = ["uvx", f"ruff@{RUFF_VERSION}"] if shutil.which("uvx") else ["ruff"]
        cmd = [*runner, "format", "--stdin-filename", path, "-"]
        cwd = ROOT
    else:
        if not PRETTIER_BIN.exists():
            sys.exit("Prettier is not installed: run `npm --prefix frontend ci` first.")
        cmd = [str(PRETTIER_BIN), "--stdin-filepath", str(ROOT / path)]
        cwd = ROOT / "frontend"
    done = subprocess.run(cmd, cwd=cwd, input=content, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        sys.exit(f"{tool} could not format {path} (is the file valid?):\n{done.stderr.strip()}")
    return done.stdout == content


def changed(base: str | None, head: str, staged: bool) -> list[tuple[str, str | None]]:
    """(path now, path on the base or None if the file is new) for added, copied, modified, renamed."""
    args = ["diff", "--name-status", "-M", "--diff-filter=ACMR"]
    args += ["--cached"] if staged else [f"{base}...{head}"]
    out = git(*args)
    if out.returncode != 0:
        sys.exit(out.stderr.strip())
    files = []
    for line in out.stdout.splitlines():
        status, *paths = line.split("\t")
        files.append(
            (paths[-1], paths[0] if status[0] == "R" else None if status[0] in "AC" else paths[0])
        )
    return files


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--base", help="revision the change is measured from (e.g. origin/main)")
    parser.add_argument("--head", default="HEAD", help="revision to check (default HEAD)")
    parser.add_argument("--staged", action="store_true", help="check the index against HEAD")
    args = parser.parse_args()
    if not args.staged and not args.base:
        parser.error("give --base REV, or --staged")

    base = "HEAD" if args.staged else args.base
    head_ref = "" if args.staged else args.head  # "" makes `git show :path` read the index
    failed, legacy, checked = [], [], 0
    for path, before in changed(args.base, args.head, args.staged):
        tool = tool_for(path)
        if tool is None:
            continue
        checked += 1
        now = git("show", f"{head_ref}:{path}")
        if now.returncode != 0 or formatted(path, now.stdout, tool):
            continue
        was = git("show", f"{base}:{before}") if before else None
        if was is not None and was.returncode == 0 and not formatted(before, was.stdout, tool):
            legacy.append(path)
        else:
            failed.append((path, tool))

    print(f"Checked {checked} changed file(s) with the repository formatters.")
    if legacy:
        print("\nNotice: already unformatted before this change, left as they are:")
        print("\n".join(f"  {p}" for p in legacy))
    if failed:
        print("\nNot formatted:")
        for path, tool in failed:
            fix = (
                f"ruff format {path}"
                if tool == "ruff"
                else f"frontend/node_modules/.bin/prettier --write {path}"
            )
            print(f"  {path}\n      fix: {fix}")
        return 1
    print("Formatting OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
