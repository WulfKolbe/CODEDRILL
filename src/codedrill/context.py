"""
codedrill.context — "context is everything".

Document structure is a semantic roadmap. Before compiling code into a graph we
read the surrounding tiddlers (TOC, abstract, section headings, author/bib) and the
paragraph tiddlers that transclude each code tiddler, so every code node inherits a
section + layer + domain hint. The layer heuristic is adapted from Understand-Anything's
layer-detector (API / Service / Data / UI / Utility).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .tw import Tiddler
from .transclusion import transclusion_targets

_LAYER_RULES = [
    ("API",     re.compile(r"\b(api|route|router|endpoint|controller|handler|view|fastapi|flask|express)\b", re.I)),
    ("Data",    re.compile(r"\b(model|schema|db|database|repository|dao|orm|sql|migration|store)\b", re.I)),
    ("Service", re.compile(r"\b(service|manager|engine|pipeline|worker|compiler|resolver|builder)\b", re.I)),
    ("UI",      re.compile(r"\b(component|widget|ui|render|dashboard|view|template)\b", re.I)),
    ("Utility", re.compile(r"\b(util|helper|common|lib|tools?|shared)\b", re.I)),
]


def layer_hint(name: str, imports: list[str]) -> str:
    blob = name + " " + " ".join(imports)
    for layer, rx in _LAYER_RULES:
        if rx.search(blob):
            return layer
    return "Core"


@dataclass
class DocumentContext:
    bibkey: str = "doc"
    title: str = ""
    abstract: str = ""
    authors: list[str] = field(default_factory=list)
    # code-tiddler-title -> the paragraph context (section heading) that transcludes it
    section_of: dict[str, str] = field(default_factory=dict)
    # paragraph-title -> its transclusion targets
    paragraph_refs: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def build(cls, tiddlers: list[Tiddler]) -> "DocumentContext":
        ctx = cls()
        # bibkey: prefer an explicit field, else infer from a "$bibkey_..." title pattern
        for t in tiddlers:
            if t.fields.get("bibkey"):
                ctx.bibkey = t.fields["bibkey"]; break
            m = re.match(r"([A-Za-z][\w-]*?)_(?:paragraph|python|typescript|code)_", t.title)
            if m:
                ctx.bibkey = m.group(1)
        # structural tiddlers
        for t in tiddlers:
            tags = set(t.tags)
            low = t.title.lower()
            if "abstract" in tags or low.endswith("abstract"):
                ctx.abstract = t.text
            if "author" in tags or t.fields.get("author"):
                ctx.authors.append(t.fields.get("author", t.text.strip()[:120]))
            if t.fields.get("title") and not ctx.title:
                ctx.title = t.fields["title"]
        # paragraph -> transclusions, and reverse map target -> section
        for t in tiddlers:
            if "paragraph" not in t.tags:
                continue
            targets = transclusion_targets(t.text)
            if targets:
                ctx.paragraph_refs[t.title] = targets
                section = t.fields.get("section") or t.fields.get("caption") or t.title
                for tgt in targets:
                    ctx.section_of.setdefault(tgt, section)
        return ctx
