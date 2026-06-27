"""Walk a repo, honoring .gitignore plus a hard skip-list of junk dirs."""

from __future__ import annotations

import fnmatch
import os

# Always pruned, regardless of .gitignore — caches, vendored deps, build output.
ALWAYS_SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    "env", ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build",
    ".idea", ".vscode", ".tox", ".eggs", ".next", ".svelte-kit", ".nuxt",
    ".gradle", "target", ".terraform", "coverage", ".cache", "vendor",
    ".parcel-cache", ".turbo", "__snapshots__",
}


def _any_glob(relpath: str, name: str, globs) -> bool:
    return any(fnmatch.fnmatch(relpath, g) or fnmatch.fnmatch(name, g)
               for g in globs)


def walk(root: str, ig=None, includes=None, excludes=None):
    """Yield repo-relative (posix) file paths, sorted within each directory."""
    root = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root).replace(os.sep, "/")
        rel = "" if rel == "." else rel

        kept = []
        for d in dirnames:
            if d in ALWAYS_SKIP_DIRS:
                continue
            rd = (rel + "/" + d).lstrip("/") if rel else d
            if ig and ig.match(rd, True):
                continue
            kept.append(d)
        dirnames[:] = sorted(kept)

        for f in sorted(filenames):
            rf = (rel + "/" + f).lstrip("/") if rel else f
            if ig and ig.match(rf, False):
                continue
            if excludes and _any_glob(rf, f, excludes):
                continue
            if includes and not _any_glob(rf, f, includes):
                continue
            yield rf
