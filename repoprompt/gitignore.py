"""A practical subset of ``.gitignore`` matching — stdlib only.

Supports: comments, blank lines, negation (``!``), directory-only rules
(``foo/``), anchored rules (``/foo`` or ``a/b``), basename-anywhere rules
(``*.log``), and ``*`` / ``?`` / ``[...]`` / ``**`` globs. Last matching rule
wins, as in git.

Not a bit-for-bit reimplementation of git's matcher (no per-directory nested
``.gitignore`` precedence subtleties) — but it gets the everyday cases right.
"""

from __future__ import annotations

import os
import re


def _compile(pat: str) -> str:
    """Translate a gitignore glob into a regex body (no anchors)."""
    i, n, out = 0, len(pat), []
    while i < n:
        if pat.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
            continue
        if pat.startswith("/**", i):
            out.append("(?:/.*)?")
            i += 3
            continue
        c = pat[i]
        if c == "*":
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        elif c == "[":
            j = pat.find("]", i)
            if j != -1:
                out.append(pat[i:j + 1])
                i = j + 1
                continue
            out.append("\\[")
        else:
            out.append(re.escape(c))
        i += 1
    return "".join(out)


class GitIgnore:
    def __init__(self, patterns):
        self.rules = []  # (negate, dironly, is_path, compiled_regex)
        for line in patterns:
            self._add(line)

    def _add(self, line: str):
        s = line.rstrip("\n")
        if not s.strip() or s.lstrip().startswith("#"):
            return
        negate = s.startswith("!")
        if negate:
            s = s[1:]
        dironly = s.endswith("/")
        if dironly:
            s = s.rstrip("/")
        anchored = s.startswith("/")
        if anchored:
            s = s.lstrip("/")
        has_slash = "/" in s
        rx = _compile(s)
        if anchored or has_slash:
            cre = re.compile(rx + r"(?:/.*)?\Z", re.S)
            self.rules.append((negate, dironly, True, cre))
        else:
            cre = re.compile(rx + r"\Z", re.S)
            self.rules.append((negate, dironly, False, cre))

    def match(self, relpath: str, is_dir: bool) -> bool:
        """True if ``relpath`` (posix, repo-relative) is ignored."""
        ignored = False
        parts = relpath.split("/")
        for negate, dironly, is_path, cre in self.rules:
            if dironly and not is_dir:
                continue
            if is_path:
                ok = bool(cre.match(relpath))
            else:
                ok = any(cre.match(p) for p in parts)
            if ok:
                ignored = not negate
        return ignored


def load(root: str) -> GitIgnore:
    """Load rules from ``root/.gitignore`` and ``.git/info/exclude``."""
    pats = []
    for rel in (".gitignore", os.path.join(".git", "info", "exclude")):
        p = os.path.join(root, rel)
        if os.path.isfile(p):
            with open(p, encoding="utf-8", errors="replace") as f:
                pats.extend(f.read().splitlines())
    return GitIgnore(pats)
