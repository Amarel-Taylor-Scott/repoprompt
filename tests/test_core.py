"""Offline tests for gitignore matching, walking, and packing. No network."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from repoprompt import gitignore  # noqa: E402
from repoprompt.walk import walk  # noqa: E402
from repoprompt.pack import pack  # noqa: E402


def _mk(files):
    d = tempfile.mkdtemp(prefix="repoprompt-")
    for rel, content in files.items():
        full = os.path.join(d, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(full), exist_ok=True) if os.path.dirname(full) else None
        mode = "wb" if isinstance(content, bytes) else "w"
        with open(full, mode) as f:
            f.write(content)
    return d


def test_gitignore_basic():
    ig = gitignore.GitIgnore(["*.log", "node_modules/", "/dist", "!keep.log"])
    assert ig.match("a/b.log", False)
    assert not ig.match("keep.log", False)        # negation wins (last rule)
    assert ig.match("node_modules", True)
    assert ig.match("dist", True)
    assert not ig.match("src/dist", True)         # /dist is anchored to root


def test_gitignore_doublestar():
    ig = gitignore.GitIgnore(["**/tmp", "a/**/c.py"])
    assert ig.match("x/y/tmp", True)
    assert ig.match("a/b/c.py", False)
    assert ig.match("a/c.py", False)


def test_walk_respects_ignore_and_skipdirs():
    d = _mk({"a.py": "x=1\n", "sub/b.py": "y=2\n", "x.log": "noise\n",
             "node_modules/p.js": "bad\n", ".git/cfg": "g\n", ".gitignore": "*.log\n"})
    ig = gitignore.load(d)
    got = set(walk(d, ig))
    assert "a.py" in got and "sub/b.py" in got
    assert "x.log" not in got
    assert all(not p.startswith("node_modules") for p in got)
    assert all(not p.startswith(".git/") for p in got)


def test_walk_include_exclude():
    d = _mk({"a.py": "1\n", "b.md": "x\n", "c.py": "2\n"})
    py = set(walk(d, None, includes=["*.py"]))
    assert py == {"a.py", "c.py"}
    no_c = set(walk(d, None, excludes=["c.py"]))
    assert "c.py" not in no_c and "a.py" in no_c


def test_pack_tree_and_blocks():
    d = _mk({"a.py": "print(1)\n", "pkg/b.py": "Z = 2\n"})
    files = sorted(walk(d))
    body, stats = pack(d, files)
    assert "File tree" in body
    assert "`a.py`" in body and "print(1)" in body
    assert "```python" in body
    assert stats["included"] == 2


def test_pack_binary_skipped():
    d = _mk({"a.py": "x=1\n", "logo.png": b"\x89PNG\x00\x00binary"})
    files = sorted(walk(d))
    body, stats = pack(d, files)
    assert any(why == "binary" for _, why in stats["skipped"])
    assert "binary" not in body or "logo.png" not in body.split("## Files")[-1]


def test_budget_skips_and_reports():
    d = _mk({("f%d.py" % i): ("# big\n" + "x = 1\n" * 200) for i in range(5)})
    files = sorted(walk(d))
    body, stats = pack(d, files, max_tokens=200)
    assert stats["included"] < len(files)
    assert any(why == "budget" for _, why in stats["skipped"])


def test_map_mode_signatures_only():
    src = "def foo(a, b):\n    return a + b\n\nclass C:\n    def m(self):\n        return 1\n"
    d = _mk({"m.py": src})
    files = sorted(walk(d))
    body, _ = pack(d, files, map_mode=True)
    assert "def foo(a, b): ..." in body
    assert "class C:" in body
    assert "return a + b" not in body            # body elided in map mode


def test_xml_format():
    d = _mk({"a.py": "x=1\n"})
    files = sorted(walk(d))
    body, _ = pack(d, files, fmt="xml")
    assert '<file path="a.py">' in body


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print("\n%d passed" % len(fns))
