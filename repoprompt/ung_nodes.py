"""UNG node adapters for repoprompt — pure, JSON-in/JSON-out wrappers.

repoprompt's high-level flow (``load`` / ``walk`` / ``pack``) reads the
filesystem; UNG nodes must not. These adapters wrap the pure rendering and
matching core over in-memory data instead: ``pack-files`` renders a
{path: content} map with the same tree header, fenced blocks, binary skip,
token budget, and Python map mode as ``pack()``; ``filter-gitignore`` applies
the ``GitIgnore`` matcher to given paths. Multi-output nodes return a dict
keyed by output name. No I/O, no network, no filesystem access.
"""

from __future__ import annotations

from typing import Optional

from .gitignore import GitIgnore
from .pack import (
    build_tree as _build_tree,
    estimate_tokens as _estimate_tokens,
    format_block as _format_block,
    is_binary as _is_binary,
    map_python as _map_python,
)


def pack_files(files: dict, repo_name: str = "repo", fmt: str = "md",
               max_tokens: Optional[int] = None, map_mode: bool = False) -> dict:
    """Render {path: content} into one LLM-ready prompt plus pack stats."""
    paths = list(files)
    tree = _build_tree(paths)
    head = ("# Repository: %s\n\n%d files\n\n## File tree\n\n```\n%s\n```\n\n"
            "## Files\n" % (repo_name, len(paths), tree))
    parts = [head]
    used = _estimate_tokens(head)
    included = 0
    skipped = []
    for path in paths:
        text = files[path]
        if _is_binary(text.encode("utf-8", "surrogateescape")):
            skipped.append([path, "binary"])
            continue
        text = text.rstrip("\n")
        if map_mode and path.endswith(".py"):
            mapped = _map_python(text)
            if mapped:
                text = mapped
        block = _format_block(path, text, fmt)
        tokens = _estimate_tokens(block)
        if max_tokens and used + tokens > max_tokens:
            skipped.append([path, "budget"])
            continue
        used += tokens
        included += 1
        parts.append(block)
    stats = {"included": included, "total": len(paths),
             "est_tokens": used, "skipped": skipped}
    return {"prompt": "\n".join(parts), "stats": stats}


def build_tree(paths: list) -> str:
    """Render repo-relative paths as the box-drawing file tree."""
    return _build_tree(paths)


def map_python_signatures(source: str) -> Optional[str]:
    """Return top-level def/class signatures of Python source, or null."""
    return _map_python(source)


def estimate_tokens(text: str) -> int:
    """Estimate the token count of a text (~4 characters per token)."""
    return _estimate_tokens(text)


def filter_gitignore(patterns: str, paths: list) -> dict:
    """Split paths into kept/ignored using .gitignore rules (last match wins)."""
    matcher = GitIgnore(patterns.splitlines())
    kept, ignored = [], []
    for path in paths:
        (ignored if matcher.match(path, False) else kept).append(path)
    return {"kept": kept, "ignored": ignored}


_TAGS = ["license.mit", "runtime.python", "dependency-free"]


def _node(fn, action, caps, summary, inputs, outputs, parameters=None):
    return {
        "fn": fn,
        "id": "amarel.repoprompt." + action,
        "capabilities": caps,
        "summary": summary,
        "inputs": inputs,
        "outputs": outputs,
        "parameters": parameters or [],
        "effects": [],
        "determinism": "deterministic",
        "idempotency": "idempotent",
        "tags": _TAGS,
    }


NODES = [
    _node(pack_files, "pack-files", ["files.pack-prompt"],
          "Pack an in-memory {path: content} repo into one LLM-ready prompt: "
          "file tree header, fenced blocks, binary skip, token budget, and "
          "Python signatures-only map mode.",
          [{"name": "files", "type_id": "amarel.types.files",
            "description": "{repo-relative path: text content} to pack."}],
          [{"name": "prompt", "type_id": "amarel.types.text",
            "description": "The packed prompt text."},
           {"name": "stats", "type_id": "amarel.types.json-value",
            "description": "{included, total, est_tokens, skipped: [[path, reason]]}."}],
          [{"name": "repo_name", "value_type": "string", "default": "repo",
            "required": False},
           {"name": "fmt", "value_type": "string", "default": "md",
            "required": False, "choices": ["md", "xml"]},
           {"name": "max_tokens", "value_type": "integer", "default": None,
            "required": False},
           {"name": "map_mode", "value_type": "boolean", "default": False,
            "required": False, "choices": [True, False]}]),
    _node(build_tree, "build-tree", ["files.render-tree"],
          "Render repo-relative paths as the box-drawing file tree used at "
          "the top of a packed prompt.",
          [{"name": "paths", "type_id": "amarel.types.text-list",
            "description": "Repo-relative POSIX paths."}],
          [{"name": "tree", "type_id": "amarel.types.text",
            "description": "The rendered tree, directories first."}]),
    _node(map_python_signatures, "map-python", ["code.map-signatures"],
          "Reduce Python source to its top-level def/class signatures — a "
          "compact map of a module (null when the source does not parse).",
          [{"name": "source", "type_id": "amarel.types.text",
            "description": "The Python source text."}],
          [{"name": "signatures", "type_id": "amarel.types.text",
            "description": "One signature per line, or null."}]),
    _node(estimate_tokens, "estimate-tokens", ["text.count-tokens"],
          "Estimate a text's token count with the fast ~4-chars-per-token "
          "budget heuristic.",
          [{"name": "text", "type_id": "amarel.types.text",
            "description": "The text to measure."}],
          [{"name": "tokens", "type_id": "amarel.types.number",
            "description": "The estimated token count (>= 1 for non-empty)."}]),
    _node(filter_gitignore, "filter-gitignore", ["files.filter-gitignore"],
          "Split paths into kept and ignored using .gitignore semantics: "
          "negation, dir-only, anchored, basename, and ** globs.",
          [{"name": "patterns", "type_id": "amarel.types.text",
            "description": "The .gitignore file content."},
           {"name": "paths", "type_id": "amarel.types.text-list",
            "description": "Repo-relative POSIX file paths to classify."}],
          [{"name": "kept", "type_id": "amarel.types.text-list",
            "description": "Paths not ignored."},
           {"name": "ignored", "type_id": "amarel.types.text-list",
            "description": "Paths matched by the rules."}]),
]
