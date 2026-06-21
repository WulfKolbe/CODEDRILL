"""
codedrill — a semantic compiler for code tiddlers.

Reads a TiddlyWiki JSON array of `paragraph` + code (`python`/`typescript`) tiddlers
and emits a knowledge graph: graph tiddlers (`$bibkey_$type_$serial`) plus a portable
Understand-Anything `knowledge-graph.json`. Stdlib-only core.
"""
from __future__ import annotations

__version__ = "0.1.0"

from .compile import compile_tiddlers, compile_file, CompileOutput  # noqa: F401
from .schema import CodeGraph, Node, Edge  # noqa: F401
from .tw import Tiddler, load_array, dump_array  # noqa: F401

__all__ = [
    "compile_tiddlers", "compile_file", "CompileOutput",
    "CodeGraph", "Node", "Edge",
    "Tiddler", "load_array", "dump_array",
    "__version__",
]
