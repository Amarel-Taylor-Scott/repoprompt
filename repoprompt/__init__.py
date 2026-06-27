"""repoprompt — pack a code repository into one LLM-ready prompt.

gitignore-aware walk → file tree + each text file in a fenced block → optional
token budget and a Python "map" (signatures only) mode. Stdlib only.
"""

from .gitignore import GitIgnore, load
from .walk import walk
from .pack import pack, estimate_tokens, lang_for

__all__ = ["GitIgnore", "load", "walk", "pack", "estimate_tokens", "lang_for"]
__version__ = "0.1.0"
