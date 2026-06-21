"""
codedrill.pdfdrill_adapter — reuse pdfdrill's deterministic compiler.

Projects the (code-centric) CodeGraph into pdfdrill's business/document SemanticGraph
so the *same* validator that guards pdfdrill's tiddlers also runs over our graph, and
the result can flow into HeimTheory-style knowledge bases. pdfdrill has no native
EntityType for code, so we map onto the closest existing types (no fork of pdfdrill core):

    module/file -> DOCUMENT(subtype=module)
    class       -> CONCEPT(subtype=class)
    function    -> CONCEPT(subtype=function)
    topic       -> CONCEPT(subtype=topic)
    article     -> DOCUMENT(subtype=paragraph)

    contains    -> RelationType.CONTAINS
    imports     -> RelationType.REFERENCES
    documents   -> RelationType.REFERENCES
    inherits    -> RelationType.DERIVED_FROM
    exemplifies -> RelationType.IMPLEMENTS    (code IMPLEMENTS a concept; CONCEPT in SCI)
    calls/related/builds_on -> RelationType.REFERENCES (carrier; precise type kept in version=)

Requires pdfdrill importable (sibling repo on PYTHONPATH, or `pip install -e ../pdfdrill`).
"""
from __future__ import annotations

from typing import Any

from .schema import CodeGraph


def project_and_validate(cg: CodeGraph) -> dict[str, Any]:
    # imported lazily so codedrill core stays dependency-free
    from semantic.graph import SemanticGraph
    from semantic.entity import Entity, EntityType
    from semantic.relation import RelationType
    from semantic import compiler

    NODE_MAP = {
        "module": (EntityType.DOCUMENT, "module"),
        "file":   (EntityType.DOCUMENT, "module"),
        "article":(EntityType.DOCUMENT, "paragraph"),
        "document":(EntityType.DOCUMENT, "document"),
        "class":  (EntityType.CONCEPT, "class"),
        "function":(EntityType.CONCEPT, "function"),
        "topic":  (EntityType.CONCEPT, "topic"),
        "concept":(EntityType.CONCEPT, "concept"),
    }
    EDGE_MAP = {
        "contains":    RelationType.CONTAINS,
        "imports":     RelationType.REFERENCES,
        "documents":   RelationType.REFERENCES,
        "inherits":    RelationType.DERIVED_FROM,
        "exemplifies": RelationType.IMPLEMENTS,
        "calls":       RelationType.REFERENCES,
        "related":     RelationType.REFERENCES,
        "builds_on":   RelationType.REFERENCES,
        "similar_to":  RelationType.REFERENCES,
        "categorized_under": RelationType.REFERENCES,
        "depends_on":  RelationType.REFERENCES,
    }

    g = SemanticGraph()
    keep: dict[str, str] = {}
    etype_of: dict[str, Any] = {}
    for nid, n in cg.nodes.items():
        mapped = NODE_MAP.get(n.type)
        if not mapped:
            continue
        etype, subtype = mapped
        g.add_entity(Entity(nid, etype, subtype=subtype))
        keep[nid] = nid
        etype_of[nid] = etype

    # Only project edges that pdfdrill's own SIGNATURE_TABLE accepts. Code-internal
    # structural edges (e.g. class-contains-method, function-calls-function) have no
    # document-centric analogue in pdfdrill and stay in the codedrill layer, which
    # already validated them. This keeps the pdfdrill pass meaningful, not abusive.
    sig = compiler.SIGNATURE_TABLE
    projected = code_layer = 0
    for e in cg.edges.values():
        pred = EDGE_MAP.get(e.type)
        if not pred or e.source not in keep or e.target not in keep:
            code_layer += 1
            continue
        src_ok, tgt_ok = sig.get(pred, (set(), set()))
        if etype_of[e.source] in src_ok and etype_of[e.target] in tgt_ok:
            g.relate(e.source, pred, e.target, produced_by="codedrill", version=e.type)
            projected += 1
        else:
            code_layer += 1   # left to codedrill's validator

    res = compiler.compile(g)
    return {
        "validity": res.validity,
        "entities": g.entity_count(),
        "projected_edges": projected,
        "code_layer_edges": code_layer,
        "critical": [w.message for w in res.warnings if w.severity == "critical"],
    }
