"""
codedrill.extractors.python_ast — stdlib-only Python extractor.

Uses `ast` (zero third-party deps). Emits, per code tiddler:
  module node  -contains->  class/function nodes
  function     -calls->     function   (best-effort, by name)
  class        -inherits->  class
  module       -imports->   module/concept
  code node    -exemplifies-> topic     (language-concepts: decorator, generator, ...)
Identity is blake2b over (lang, kind, qualified_name) so re-runs are idempotent.
"""
from __future__ import annotations

import ast
from typing import Optional

from ..schema import CodeGraph, Node, Edge
from ..concepts import detect_python_concepts
from .base import register


def _complexity(node: ast.AST) -> str:
    branches = sum(isinstance(n, (ast.If, ast.For, ast.While, ast.Try,
                                  ast.With, ast.BoolOp, ast.comprehension))
                   for n in ast.walk(node))
    return "simple" if branches <= 2 else "moderate" if branches <= 8 else "complex"


def _qual(module: str, name: str) -> str:
    return f"{module}.{name}"


@register("python")
class PythonExtractor:
    lang = "python"

    def extract(self, graph: CodeGraph, *, code: str, module_name: str,
                source_title: str) -> Optional[str]:
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            mid = CodeGraph.node_id("module", module_name, self.lang)
            graph.add_node(Node(mid, "module", module_name,
                                summary=f"unparseable python: {exc}",
                                tags=["python", "codedrill"],
                                knowledgeMeta={"sourceTiddler": source_title}))
            return mid

        mid = CodeGraph.node_id("module", module_name, self.lang)
        graph.add_node(Node(mid, "module", module_name,
                            summary=ast.get_docstring(tree) or f"module {module_name}",
                            tags=["python", "codedrill"], complexity=_complexity(tree),
                            knowledgeMeta={"sourceTiddler": source_title}))

        # name -> node id, to resolve calls/inheritance within this tiddler
        local: dict[str, str] = {}

        def add_def(node, kind: str, parent_id: str, parent_name: str):
            qn = _qual(parent_name, node.name)
            nid = CodeGraph.node_id(kind, qn, self.lang)
            doc = ast.get_docstring(node) or ""
            graph.add_node(Node(
                nid, kind, node.name,
                summary=doc.splitlines()[0] if doc else f"{kind} {node.name}",
                tags=["python", kind, "codedrill"],
                complexity=_complexity(node),
                lineRange=(node.lineno, getattr(node, "end_lineno", node.lineno)),
                knowledgeMeta={"sourceTiddler": source_title, "qualified": qn},
            ))
            graph.add_edge(Edge(parent_id, nid, "contains"))
            local[node.name] = nid
            # language-concepts -> topic nodes (the "higher level" layer, seeded from UA)
            for concept in detect_python_concepts(node):
                tid = CodeGraph.node_id("topic", concept, "concept")
                graph.add_node(Node(tid, "topic", concept,
                                    summary=f"language concept: {concept}",
                                    tags=["concept", "codedrill"]))
                graph.add_edge(Edge(nid, tid, "exemplifies"))
            return nid

        # top-level classes & functions
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                cid = add_def(node, "class", mid, module_name)
                for base in node.bases:
                    bname = base.id if isinstance(base, ast.Name) else \
                            getattr(base, "attr", None)
                    if bname:
                        # forward-link; resolved post-hoc if base is local
                        bid = local.get(bname) or CodeGraph.node_id("class",
                                                                    _qual(module_name, bname),
                                                                    self.lang)
                        graph.add_node(Node(bid, "class", bname,
                                            summary=f"class {bname}",
                                            tags=["python", "class", "codedrill"]))
                        graph.add_edge(Edge(cid, bid, "inherits"))
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        add_def(sub, "function", cid, f"{module_name}.{node.name}")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                add_def(node, "function", mid, module_name)

        # imports -> module/concept nodes
        for node in ast.walk(tree):
            targets: list[str] = []
            if isinstance(node, ast.Import):
                targets = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                targets = [f"{base}.{a.name}" if base else a.name for a in node.names]
            for tgt in targets:
                tid = CodeGraph.node_id("module", tgt, "")
                graph.add_node(Node(tid, "module", tgt,
                                    summary=f"imported: {tgt}",
                                    tags=["import", "codedrill"], complexity="simple"))
                graph.add_edge(Edge(mid, tid, "imports"))

        # calls between locally-defined functions (best-effort by callee name)
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            src_id = local.get(fn.name)
            if not src_id or graph.nodes[src_id].type != "function":
                continue
            for call in ast.walk(fn):
                if isinstance(call, ast.Call):
                    callee = getattr(call.func, "id", None) or getattr(call.func, "attr", None)
                    dst = local.get(callee or "")
                    if dst and dst != src_id and graph.nodes.get(dst, Node("", "", "")).type == "function":
                        graph.add_edge(Edge(src_id, dst, "calls", weight=0.7))
        return mid
