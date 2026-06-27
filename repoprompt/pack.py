"""Render walked files into one prompt: tree header + fenced file blocks.

Binary files are skipped, a token budget can cap the output, and ``map_mode``
emits Python signatures instead of full bodies for a compact whole-repo map.
"""

from __future__ import annotations

import ast
import os

_LANG = {
    ".py": "python", ".pyi": "python", ".js": "javascript", ".mjs": "javascript",
    ".cjs": "javascript", ".ts": "typescript", ".tsx": "tsx", ".jsx": "jsx",
    ".json": "json", ".md": "markdown", ".rst": "rst", ".sh": "bash",
    ".bash": "bash", ".zsh": "bash", ".go": "go", ".rs": "rust", ".rb": "ruby",
    ".php": "php", ".java": "java", ".kt": "kotlin", ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".hpp": "cpp", ".cs": "csharp", ".swift": "swift",
    ".scala": "scala", ".sql": "sql", ".html": "html", ".css": "css",
    ".scss": "scss", ".yml": "yaml", ".yaml": "yaml", ".toml": "toml",
    ".ini": "ini", ".cfg": "ini", ".xml": "xml", ".r": "r", ".lua": "lua",
    ".pl": "perl", ".proto": "protobuf", ".tf": "hcl", ".vue": "vue",
}


def lang_for(path: str) -> str:
    base = os.path.basename(path).lower()
    if base == "dockerfile" or base.startswith("dockerfile."):
        return "dockerfile"
    if base in ("makefile", "gnumakefile"):
        return "makefile"
    return _LANG.get(os.path.splitext(path)[1].lower(), "")


def estimate_tokens(s: str) -> int:
    return max(1, len(s) // 4)


def is_binary(data: bytes) -> bool:
    return b"\x00" in data[:8000]


def build_tree(paths) -> str:
    root = {}
    for p in paths:
        cur = root
        parts = p.split("/")
        for d in parts[:-1]:
            cur = cur.setdefault(d + "/", {})
        cur[parts[-1]] = None
    lines = []

    def rec(node, prefix):
        # directories (value is a dict) first, then files, each alphabetic
        items = sorted(node.items(), key=lambda kv: (kv[1] is None, kv[0].lower()))
        for i, (name, child) in enumerate(items):
            last = i == len(items) - 1
            lines.append(prefix + ("└── " if last else "├── ") + name)
            if child is not None:
                rec(child, prefix + ("    " if last else "│   "))

    rec(root, "")
    return "\n".join(lines)


def _args(node) -> str:
    a = node.args
    posonly = [ar.arg for ar in getattr(a, "posonlyargs", [])]
    names = list(posonly)
    if posonly:
        names.append("/")
    names += [ar.arg for ar in a.args]
    if a.vararg:
        names.append("*" + a.vararg.arg)
    elif a.kwonlyargs:
        names.append("*")
    names += [ar.arg for ar in a.kwonlyargs]
    if a.kwarg:
        names.append("**" + a.kwarg.arg)
    return "(" + ", ".join(names) + ")"


def map_python(text: str):
    """Top-level defs/classes (+ their methods) as signatures, or None."""
    try:
        tree = ast.parse(text)
    except Exception:
        return None
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append("def " + node.name + _args(node) + ": ...")
        elif isinstance(node, ast.ClassDef):
            out.append("class " + node.name + ":")
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.append("    def " + sub.name + _args(sub) + ": ...")
    return "\n".join(out)


def format_block(path: str, text: str, fmt: str) -> str:
    if fmt == "xml":
        return '<file path="%s">\n%s\n</file>\n' % (path, text)
    return "### `%s`\n\n```%s\n%s\n```\n" % (path, lang_for(path), text)


def pack(root, files, *, fmt="md", max_tokens=None, map_mode=False):
    root = os.path.abspath(root)
    name = os.path.basename(root) or root
    tree = build_tree(files)
    head = ("# Repository: %s\n\n%d files\n\n## File tree\n\n```\n%s\n```\n\n"
            "## Files\n" % (name, len(files), tree))
    parts = [head]
    used = estimate_tokens(head)
    included = 0
    skipped = []
    for rf in files:
        full = os.path.join(root, rf.replace("/", os.sep))
        try:
            with open(full, "rb") as fh:
                data = fh.read()
        except OSError:
            skipped.append((rf, "unreadable"))
            continue
        if is_binary(data):
            skipped.append((rf, "binary"))
            continue
        text = data.decode("utf-8", "replace").rstrip("\n")
        if map_mode and rf.endswith(".py"):
            m = map_python(text)
            if m:
                text = m
        block = format_block(rf, text, fmt)
        t = estimate_tokens(block)
        if max_tokens and used + t > max_tokens:
            skipped.append((rf, "budget"))
            continue
        used += t
        included += 1
        parts.append(block)
    body = "\n".join(parts)
    stats = {"included": included, "total": len(files),
             "est_tokens": used, "skipped": skipped}
    return body, stats
