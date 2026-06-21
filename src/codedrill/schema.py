"""
codedrill.schema — the graph contract.

Node/edge vocabulary and the LLM-alias normalization tables are ADAPTED from
Understand-Anything (Egonex-AI, MIT): understand-anything-plugin/packages/core/src/schema.ts.
We keep their canonical types so a codedrill graph round-trips through their dashboard,
merge tools, and `knowledge-graph.json` consumers unchanged. See NOTICE.

The CODE_SIGNATURE_TABLE is the deterministic gate: every edge must connect node
*types* the relation allows, mirroring pdfdrill's src/semantic/compiler.py philosophy
(type-check relations, flag danglers) — but specialized for code rather than business docs.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Iterable, Optional

# --- Canonical node types (UA) -------------------------------------------------
NODE_TYPES = {
    "file", "function", "class", "module", "concept",
    "config", "document", "service", "table", "endpoint",
    "pipeline", "schema", "resource",
    "domain", "flow", "step",
    "article", "entity", "topic", "claim", "source",
}

# --- Canonical edge types (UA, 35 across 8 categories) -------------------------
EDGE_TYPES = {
    "imports", "exports", "contains", "inherits", "implements",
    "calls", "subscribes", "publishes", "middleware",
    "reads_from", "writes_to", "transforms", "validates",
    "depends_on", "tested_by", "configures",
    "related", "similar_to",
    "deploys", "serves", "provisions", "triggers",
    "migrates", "documents", "routes", "defines_schema",
    "contains_flow", "flow_step", "cross_domain",
    "cites", "contradicts", "builds_on", "exemplifies", "categorized_under", "authored_by",
}

# --- Alias tables (vendored from UA schema.ts) — normalize LLM/heuristic output -
NODE_TYPE_ALIASES = {
    "func": "function", "fn": "function", "method": "function",
    "interface": "class", "struct": "class",
    "mod": "module", "pkg": "module", "package": "module",
    "doc": "document", "readme": "document",
    "note": "article", "page": "article", "wiki_page": "article",
    "person": "entity", "actor": "entity", "organization": "entity",
    "tag": "topic", "category": "topic", "theme": "topic",
    "assertion": "claim", "decision": "claim", "thesis": "claim",
    "reference": "source", "paper": "source",
}
EDGE_TYPE_ALIASES = {
    "extends": "inherits", "invokes": "calls", "invoke": "calls",
    "uses": "depends_on", "requires": "depends_on",
    "relates_to": "related", "related_to": "related",
    "similar": "similar_to", "import": "imports", "export": "exports",
    "describes": "documents", "documented_by": "documents",
    "references": "cites", "conflicts_with": "contradicts",
    "refines": "builds_on", "elaborates": "builds_on",
    "illustrates": "exemplifies", "instance_of": "exemplifies", "example_of": "exemplifies",
    "belongs_to": "categorized_under", "tagged_with": "categorized_under",
    "written_by": "authored_by", "created_by": "authored_by",
}
COMPLEXITY_ALIASES = {"low": "simple", "easy": "simple", "medium": "moderate",
                      "intermediate": "moderate", "high": "complex", "hard": "complex"}


def canon_node_type(t: str) -> str:
    t = (t or "").strip().lower()
    return NODE_TYPE_ALIASES.get(t, t)


def canon_edge_type(t: str) -> str:
    t = (t or "").strip().lower()
    return EDGE_TYPE_ALIASES.get(t, t)


# --- The deterministic gate: which node types each edge may connect -----------
# Values are (allowed-source-types, allowed-target-types). "*" == any.
_ANY = {"*"}
_CODE = {"module", "file", "class", "function"}
_GROUP = {"module", "file", "class"}
CODE_SIGNATURE_TABLE: dict[str, tuple[set, set]] = {
    "imports":   ({"module", "file"}, {"module", "file", "concept"}),
    "contains":  (_GROUP, _CODE | {"schema", "config"}),
    "calls":     ({"function"}, {"function"}),
    "inherits":  ({"class"}, {"class"}),
    "implements":({"class"}, {"class", "schema"}),
    "depends_on":(_CODE, _CODE | {"resource", "service"}),
    "tested_by": (_CODE, _CODE),
    # knowledge / concept-lift edges (kept permissive; these are the "higher-level" layer)
    "exemplifies":      (_CODE, {"topic", "concept"}),
    "categorized_under":(_ANY, {"topic", "domain", "concept"}),
    "related":          (_ANY, _ANY),
    "similar_to":       (_ANY, _ANY),
    "builds_on":        (_ANY, _ANY),
    "documents":        ({"article", "document"}, _ANY),  # paragraph tiddler -> code object
    "authored_by":      (_ANY, {"entity", "source"}),
    "cites":            ({"article", "document", "source"}, _ANY),
}


@dataclass
class Node:
    id: str
    type: str
    name: str
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    complexity: str = "simple"
    filePath: Optional[str] = None
    lineRange: Optional[tuple[int, int]] = None
    languageNotes: Optional[str] = None
    knowledgeMeta: Optional[dict] = None  # {wikilinks, backlinks, category, content}

    def to_dict(self) -> dict:
        d = {k: v for k, v in asdict(self).items() if v not in (None, [], {})}
        d["tags"] = self.tags  # always emit tags array (UA expects it)
        return d


@dataclass
class Edge:
    source: str
    target: str
    type: str
    direction: str = "forward"
    description: str = ""
    weight: float = 1.0

    def key(self) -> tuple:
        return (self.source, self.target, self.type)

    def to_dict(self) -> dict:
        d = {"source": self.source, "target": self.target, "type": self.type,
             "direction": self.direction, "weight": round(self.weight, 4)}
        if self.description:
            d["description"] = self.description
        return d


@dataclass
class Warning:
    code: str
    severity: str  # "critical" | "warn" | "info"
    message: str


@dataclass
class CompileResult:
    validity: str           # "valid" | "invalid"
    warnings: list[Warning] = field(default_factory=list)

    @property
    def critical(self) -> list[Warning]:
        return [w for w in self.warnings if w.severity == "critical"]


class CodeGraph:
    """In-memory graph with idempotent, content-hashed node identity (blake2b)."""

    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self.edges: dict[tuple, Edge] = {}

    # --- identity ----------------------------------------------------------
    @staticmethod
    def node_id(kind: str, qualified_name: str, lang: str = "", body: str = "") -> str:
        """blake2b content hash — re-running the compiler on the same input is stable."""
        h = hashlib.blake2b(digest_size=8)
        h.update(f"{lang}\x1f{kind}\x1f{qualified_name}\x1f{body}".encode("utf-8"))
        return f"{canon_node_type(kind)}:{h.hexdigest()}"

    # --- mutation ----------------------------------------------------------
    def add_node(self, node: Node) -> Node:
        node.type = canon_node_type(node.type)
        node.complexity = COMPLEXITY_ALIASES.get(node.complexity, node.complexity)
        existing = self.nodes.get(node.id)
        if existing:  # idempotent merge: union tags, keep richest summary
            existing.tags = sorted(set(existing.tags) | set(node.tags))
            if len(node.summary) > len(existing.summary):
                existing.summary = node.summary
            return existing
        self.nodes[node.id] = node
        return node

    def add_edge(self, edge: Edge) -> Optional[Edge]:
        edge.type = canon_edge_type(edge.type)
        if edge.key() in self.edges:
            return self.edges[edge.key()]
        self.edges[edge.key()] = edge
        return edge

    # --- validation (the deterministic gate) -------------------------------
    def compile(self) -> CompileResult:
        warns: list[Warning] = []
        for e in self.edges.values():
            if e.source not in self.nodes:
                warns.append(Warning("dangling_source", "critical",
                                     f"edge {e.type} from missing node {e.source}"))
                continue
            if e.target not in self.nodes:
                warns.append(Warning("dangling_target", "critical",
                                     f"edge {e.type} to missing node {e.target}"))
                continue
            sig = CODE_SIGNATURE_TABLE.get(e.type)
            if not sig:
                warns.append(Warning("unknown_edge_type", "warn",
                                     f"no signature for edge type '{e.type}'"))
                continue
            src_ok, tgt_ok = sig
            st, tt = self.nodes[e.source].type, self.nodes[e.target].type
            if "*" not in src_ok and st not in src_ok:
                warns.append(Warning("type_violation", "critical",
                                     f"{e.type}: source must be {sorted(src_ok)}, got {st}"))
            if "*" not in tgt_ok and tt not in tgt_ok:
                warns.append(Warning("type_violation", "critical",
                                     f"{e.type}: target must be {sorted(tgt_ok)}, got {tt}"))
        validity = "invalid" if any(w.severity == "critical" for w in warns) else "valid"
        return CompileResult(validity, warns)

    def edge_typechecks(self, edge: Edge) -> bool:
        """Used by the recursion/fixpoint loop: would adding this edge stay valid?"""
        if edge.source not in self.nodes or edge.target not in self.nodes:
            return False
        sig = CODE_SIGNATURE_TABLE.get(canon_edge_type(edge.type))
        if not sig:
            return False
        src_ok, tgt_ok = sig
        st, tt = self.nodes[edge.source].type, self.nodes[edge.target].type
        return ("*" in src_ok or st in src_ok) and ("*" in tgt_ok or tt in tgt_ok)

    # --- export (UA knowledge-graph.json) ----------------------------------
    def to_knowledge_graph(self, *, name: str, languages: Iterable[str],
                           commit: str = "", kind: str = "knowledge") -> dict:
        import datetime
        return {
            "version": "1",
            "kind": kind,
            "project": {
                "name": name, "languages": sorted(set(languages)), "frameworks": [],
                "description": "codedrill semantic graph of TiddlyWiki code/paragraph tiddlers",
                "analyzedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "gitCommitHash": commit,
            },
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges.values()],
            "layers": [], "tour": [],
        }

    def to_json(self, **kw) -> str:
        return json.dumps(self.to_knowledge_graph(**kw), indent=2, ensure_ascii=False)
