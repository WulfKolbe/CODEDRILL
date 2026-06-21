"""
codedrill.extractors.typescript_heuristic — heuristic TS extractor.

A regex/heuristic tier that handles the common shapes (imports, exported
classes/functions/interfaces, `extends`/`implements`) with zero native deps.

>>> UPGRADE SLOT <<<
For precise extraction, drop in tree-sitter. Understand-Anything already ships a
TypeScript tree-sitter extractor (understand-anything-plugin/packages/core/src/
plugins/extractors/typescript-extractor.ts). Port its node-walk, or call
`tree_sitter_languages.get_parser("typescript")` here and emit the same
Node/Edge objects. The downstream graph/validator/tiddler code is language-agnostic.
"""
from __future__ import annotations

import re
from typing import Optional

from ..schema import CodeGraph, Node, Edge
from ..concepts import detect_typescript_concepts
from .base import register

_IMPORT = re.compile(r"""import\s+(?:[\w*{}\s,]+\s+from\s+)?['"]([^'"]+)['"]""")
_CLASS = re.compile(r"\b(?:export\s+)?(?:abstract\s+)?class\s+(\w+)"
                    r"(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w,\s]+))?")
_IFACE = re.compile(r"\b(?:export\s+)?interface\s+(\w+)")
_FUNC = re.compile(r"\b(?:export\s+)?(?:async\s+)?function\s+(\w+)")
_ARROW = re.compile(r"\b(?:export\s+)?const\s+(\w+)\s*[:=][^=]*=>", re.MULTILINE)


@register("typescript")
class TypeScriptExtractor:
    lang = "typescript"

    def extract(self, graph: CodeGraph, *, code: str, module_name: str,
                source_title: str) -> Optional[str]:
        mid = CodeGraph.node_id("module", module_name, self.lang)
        graph.add_node(Node(mid, "module", module_name, summary=f"module {module_name}",
                            tags=["typescript", "codedrill"],
                            knowledgeMeta={"sourceTiddler": source_title}))
        local: dict[str, str] = {}

        def emit(kind: str, name: str) -> str:
            nid = CodeGraph.node_id(kind, f"{module_name}.{name}", self.lang)
            graph.add_node(Node(nid, kind, name, summary=f"{kind} {name}",
                                tags=["typescript", kind, "codedrill"],
                                knowledgeMeta={"sourceTiddler": source_title}))
            graph.add_edge(Edge(mid, nid, "contains"))
            local[name] = nid
            return nid

        for m in _IMPORT.finditer(code):
            tid = CodeGraph.node_id("module", m.group(1), "")
            graph.add_node(Node(tid, "module", m.group(1), summary=f"imported: {m.group(1)}",
                                tags=["import", "codedrill"]))
            graph.add_edge(Edge(mid, tid, "imports"))
        for m in _IFACE.finditer(code):
            emit("class", m.group(1))  # interface -> class (UA alias)
        for m in _CLASS.finditer(code):
            cid = emit("class", m.group(1))
            for base in filter(None, [m.group(2)] + (m.group(3).split(",") if m.group(3) else [])):
                base = base.strip()
                bid = local.get(base) or CodeGraph.node_id("class", f"{module_name}.{base}", self.lang)
                graph.add_node(Node(bid, "class", base, summary=f"class {base}",
                                    tags=["typescript", "class", "codedrill"]))
                graph.add_edge(Edge(cid, bid, "inherits"))
        for rx in (_FUNC, _ARROW):
            for m in rx.finditer(code):
                emit("function", m.group(1))

        for concept in detect_typescript_concepts(code):
            tid = CodeGraph.node_id("topic", concept, "concept")
            graph.add_node(Node(tid, "topic", concept, summary=f"language concept: {concept}",
                                tags=["concept", "codedrill"]))
            graph.add_edge(Edge(mid, tid, "exemplifies"))
        return mid
