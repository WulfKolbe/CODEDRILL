"""
codedrill.compile — the semantic compiler.

Pipeline (see README diagram):
  1. route tiddlers by tag           (paragraph | python | typescript | ...)
  2. extract each code tiddler        -> CodeGraph (reusing per-language extractors)
  3. context-link                     paragraph transclusions -> `documents` edges + layer/section
  4. concept-lift                     shared language-concepts -> `related` edges (deterministic)
  5. recursion fixpoint               re-add only edges that type-check; bounded; idempotent
  6. validate                         CodeGraph.compile()  (+ optional pdfdrill compiler)
  7. emit                             graph tiddlers ($Bibkey_$type_$serial) + knowledge-graph.json
"""
from __future__ import annotations

import itertools
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .tw import Tiddler, SerialAllocator, dump_array, join_tags
from .schema import CodeGraph, Node, Edge, CompileResult
from .context import DocumentContext, layer_hint
from .extractors.base import for_language, languages
# importing the extractor modules registers them:
from .extractors import python_ast as _py   # noqa: F401
from .extractors import typescript_heuristic as _ts  # noqa: F401

CODE_TAGS = set(languages())  # {"python","typescript",...} from the registry


@dataclass
class CompileOutput:
    graph: CodeGraph
    result: CompileResult
    tiddlers: list[Tiddler] = field(default_factory=list)
    context: Optional[DocumentContext] = None
    pdfdrill: Optional[dict] = None


def _module_imports(graph: CodeGraph, module_id: str) -> list[str]:
    return [graph.nodes[e.target].name for e in graph.edges.values()
            if e.source == module_id and e.type == "imports" and e.target in graph.nodes]


def compile_tiddlers(tiddlers: list[Tiddler], *, max_passes: int = 3) -> CompileOutput:
    ctx = DocumentContext.build(tiddlers)
    graph = CodeGraph()
    code_langs: set[str] = set()
    title_to_module: dict[str, str] = {}

    # --- 2. extract code tiddlers ----------------------------------------
    for t in tiddlers:
        lang = next((tag for tag in t.tags if tag in CODE_TAGS), None)
        if not lang:
            continue
        ex = for_language(lang)
        if not ex:
            continue
        module_name = t.fields.get("module") or t.title
        mid = ex.extract(graph, code=t.text, module_name=module_name, source_title=t.title)
        if mid:
            code_langs.add(lang)
            title_to_module[t.title] = mid
            # context: assign layer + section to the module node
            node = graph.nodes[mid]
            node.knowledgeMeta = {**(node.knowledgeMeta or {}),
                                  "layer": layer_hint(module_name, _module_imports(graph, mid)),
                                  "section": ctx.section_of.get(t.title, "")}

    # --- 3. context-link: paragraph -> documents -> code -----------------
    for para_title, targets in ctx.paragraph_refs.items():
        for tgt in targets:
            mid = title_to_module.get(tgt)
            if not mid:
                continue
            aid = CodeGraph.node_id("article", para_title, "tw")
            graph.add_node(Node(aid, "article", para_title,
                                summary=f"paragraph {para_title}",
                                tags=["paragraph", "codedrill"],
                                knowledgeMeta={"sourceTiddler": para_title}))
            graph.add_edge(Edge(aid, mid, "documents", description="transclusion"))

    # --- 4. concept-lift: code nodes sharing a topic become `related` ----
    topic_members: dict[str, list[str]] = {}
    for e in list(graph.edges.values()):
        if e.type == "exemplifies":
            topic_members.setdefault(e.target, []).append(e.source)
    proposed: list[Edge] = []
    for members in topic_members.values():
        for a, b in itertools.combinations(sorted(set(members)), 2):
            proposed.append(Edge(a, b, "related", direction="bidirectional", weight=0.4,
                                 description="shares language-concept"))

    # --- 5. recursion fixpoint: add only edges that keep the graph valid -
    for _ in range(max_passes):
        added = 0
        for e in proposed:
            if e.key() in graph.edges:
                continue
            if graph.edge_typechecks(e):
                graph.add_edge(e); added += 1
        if not added:
            break

    # --- 6. validate -----------------------------------------------------
    result = graph.compile()

    # --- 7. emit graph tiddlers -----------------------------------------
    out = CompileOutput(graph=graph, result=result, context=ctx)
    out.tiddlers = emit_tiddlers(graph, ctx, validity=result.validity)
    return out


def emit_tiddlers(graph: CodeGraph, ctx: DocumentContext, *, validity: str) -> list[Tiddler]:
    """One tiddler per graph node (outgoing edges carried as a JSON field) + one index
    tiddler holding the full UA knowledge-graph.json."""
    alloc = SerialAllocator()
    id_to_title: dict[str, str] = {}
    tiddlers: list[Tiddler] = []

    # stable title order: by node type then name
    ordered = sorted(graph.nodes.values(), key=lambda n: (n.type, n.name, n.id))
    for n in ordered:
        title = alloc.title(ctx.bibkey, n.type)
        id_to_title[n.id] = title

    for n in ordered:
        out_edges = [e for e in graph.edges.values() if e.source == n.id]
        edge_repr = [{"to": id_to_title.get(e.target, e.target), "type": e.type,
                      "weight": round(e.weight, 3)} for e in out_edges]
        src = (n.knowledgeMeta or {}).get("sourceTiddler", "")
        body = [f"//{n.type}// **{n.name}** — {n.summary}".strip()]
        if (n.knowledgeMeta or {}).get("layer"):
            body.append(f"\nlayer: {n.knowledgeMeta['layer']}  section: {n.knowledgeMeta.get('section','')}")
        if src:
            body.append(f"\nSource: {{{{{src}}}}}")  # transclude original code tiddler back in
        fields = {
            "tags": join_tags(sorted(set(n.tags) | {"codedrill", "graph-node"})),
            "cd.id": n.id,
            "cd.type": n.type,
            "cd.complexity": n.complexity,
            "cd.edges": json.dumps(edge_repr, ensure_ascii=False),
            "cd.validity": validity,
        }
        if src:
            fields["cd.source"] = src
        tiddlers.append(Tiddler(title=id_to_title[n.id], text="\n".join(body), fields=fields))

    # index tiddler: the whole graph as UA knowledge-graph.json (dashboard-ready)
    kg = graph.to_knowledge_graph(name=ctx.bibkey or "codedrill",
                                  languages=[t for t in CODE_TAGS])
    tiddlers.append(Tiddler(
        title=f"{ctx.bibkey}_graph_0000",
        text="Knowledge graph index (Understand-Anything compatible). "
             "Load `knowledge-graph` field into the UA dashboard.",
        fields={"tags": join_tags(["codedrill", "graph-index"]),
                "cd.nodes": str(len(graph.nodes)),
                "cd.edges": str(len(graph.edges)),
                "cd.validity": validity,
                "knowledge-graph": json.dumps(kg, ensure_ascii=False)},
    ))
    return tiddlers


def compile_file(in_path: str | Path, out_dir: str | Path,
                 *, with_pdfdrill: bool = False) -> CompileOutput:
    from .tw import load_array
    tiddlers = load_array(in_path)
    out = compile_tiddlers(tiddlers)
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    dump_array(out.tiddlers, out_dir / "graph-tiddlers.json")
    (out_dir / "knowledge-graph.json").write_text(
        out.graph.to_json(name=out.context.bibkey or "codedrill",
                          languages=list(CODE_TAGS)), encoding="utf-8")
    if with_pdfdrill:
        try:
            from .pdfdrill_adapter import project_and_validate
            out.pdfdrill = project_and_validate(out.graph)
        except Exception as exc:  # pdfdrill not importable in this env
            out.pdfdrill = {"error": str(exc)}
    return out
