# repoprompt

> Pack a whole code repository into **one LLM-ready prompt** — gitignore-aware,
> token-budgeted, with a file tree and every text file in a fenced block.
> Stdlib only, no dependencies. The code sibling of
> [docdense](https://github.com/Amarel-Taylor-Scott/docdense) (which does the
> same for documentation websites).

```bash
repoprompt                              # current repo → stdout
repoprompt . -o context.md             # → a file
repoprompt . --include '*.py'          # only Python
repoprompt . --max-tokens 60000        # fit a budget (skipped files reported)
repoprompt . --map                     # signatures-only map of a big repo
repoprompt . --format xml              # <file path="…"> blocks (some models prefer this)
```

Output starts with a tree, then each file:

````
# Repository: llmjson

8 files

## File tree

```
├── llmjson/
│   ├── __init__.py
│   ├── coerce.py
│   └── parse.py
└── tests/
    └── test_core.py
```

## Files

### `llmjson/coerce.py`

```python
…file contents…
```
````

## Why

Pasting a repo into a model by hand is tedious and you always forget a file —
or you dump `node_modules`/`.venv`/build output and blow the context window.
`repoprompt` walks the repo the way git sees it, skips the junk, and produces a
single deterministic, copy-pasteable prompt with a tree for orientation. No
service, no upload, no dependencies.

## What it does

- **Respects `.gitignore`** (and `.git/info/exclude`) — comments, negation
  (`!keep.log`), dir-only (`build/`), anchored (`/dist`), basename-anywhere
  (`*.log`), and `*`/`?`/`[…]`/`**` globs.
- **Hard-skips junk dirs** regardless of gitignore: `.git`, `node_modules`,
  `__pycache__`, `.venv`, `dist`, `build`, `target`, caches, … (full list in
  `walk.py`).
- **Skips binary files** (NUL-byte sniff) — no base64 noise in your prompt.
- **Token budget** (`--max-tokens`): files that would overflow are skipped and
  **reported on stderr** — never silently dropped.
- **`--map`**: for Python files, emit just the `def`/`class` signatures (with
  `*`/`/`/`**args`) instead of full bodies — a compact map of a large codebase
  that fits where the full dump wouldn't.
- **`--include` / `--exclude`** globs to scope the pack.
- **`--format md|xml`** — fenced Markdown (default) or `<file>` tags.

The packed text goes to **stdout** (pipe it: `repoprompt | pbcopy`) or to `-o`.
A one-line summary and any skips go to **stderr**, so they never pollute the
prompt.

## Library

```python
from repoprompt import load, walk, pack

ig = load(".")                          # parse .gitignore
files = list(walk(".", ig, includes=["*.py"]))
text, stats = pack(".", files, max_tokens=60000, map_mode=False)
# stats = {"included": N, "total": M, "est_tokens": T, "skipped": [(path, reason), …]}
```

## Layout

```
repoprompt/
  gitignore.py  practical .gitignore matcher (glob → regex, last-match-wins)
  walk.py       os.walk + gitignore + hard junk-dir skip-list
  pack.py       tree + fenced blocks, binary skip, token budget, python map mode
  cli.py        the `repoprompt` command
```

Token counts are a fast `len // 4` estimate (good enough for budgeting; no
tokenizer dependency).

MIT. Stdlib only — no dependencies, no network, no API keys.
