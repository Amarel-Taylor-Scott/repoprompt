"""``repoprompt`` CLI — a repo → one LLM-ready prompt.

    repoprompt                              # current dir → stdout
    repoprompt . --include '*.py' -o ctx.md
    repoprompt . --max-tokens 60000         # budget; skipped files reported
    repoprompt . --map                      # signatures-only map of a big repo
    repoprompt . --format xml               # <file path="…"> blocks
"""

from __future__ import annotations

import argparse
import os
import sys

from .gitignore import load as load_ignore
from .pack import pack
from .walk import walk


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="repoprompt",
        description="Pack a repo into one LLM-ready prompt (gitignore-aware, "
                    "token-budgeted). Stdlib only.",
    )
    p.add_argument("path", nargs="?", default=".", help="repo root (default: .)")
    p.add_argument("--include", action="append", default=[],
                   help="glob to include (repeatable); only matching files")
    p.add_argument("--exclude", action="append", default=[],
                   help="glob to exclude (repeatable)")
    p.add_argument("--max-tokens", type=int, default=None,
                   help="approx token budget; files past it are skipped + reported")
    p.add_argument("--format", choices=["md", "xml"], default="md")
    p.add_argument("--map", action="store_true",
                   help="signatures only for .py files (compact whole-repo map)")
    p.add_argument("--no-gitignore", action="store_true",
                   help="do not read .gitignore")
    p.add_argument("-o", "--output", help="write here (default: stdout)")
    a = p.parse_args(argv)

    root = a.path
    if not os.path.isdir(root):
        sys.stderr.write("repoprompt: not a directory: %s\n" % root)
        return 1

    ig = None if a.no_gitignore else load_ignore(root)
    files = list(walk(root, ig, includes=a.include or None,
                      excludes=a.exclude or None))
    if not files:
        sys.stderr.write("repoprompt: no files matched\n")
        return 1

    body, stats = pack(root, files, fmt=a.format,
                       max_tokens=a.max_tokens, map_mode=a.map)

    if a.output:
        with open(a.output, "w", encoding="utf-8") as f:
            f.write(body)
        where = a.output
    else:
        sys.stdout.write(body)
        where = None

    msg = "repoprompt: %d/%d files · ~%d tokens" % (
        stats["included"], stats["total"], stats["est_tokens"])
    if where:
        msg += " → %s" % where
    sys.stderr.write(msg + "\n")
    for rf, why in stats["skipped"]:
        sys.stderr.write("  skipped (%s): %s\n" % (why, rf))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
