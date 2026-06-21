"""
codedrill.transclusion — parse TiddlyWiki transclusion syntax in paragraph tiddlers.

Paragraph tiddlers (tag "paragraph") are text + transclusions of non-textual objects.
We extract the referenced titles so the compiler can draw `documents` edges
(paragraph -> code object) and propagate section/context onto the code node.

Recognized forms:
    {{Title}}                      block transclusion
    {{Title||Template}}            templated transclusion (non-textual objects)
    {{Title!!field}}               field transclusion
    {{Title}width:40%;}            with style (TW allows a `{...}` style block)
    <$transclude tiddler="Title"/> widget form
"""
from __future__ import annotations

import re

_BRACE = re.compile(r"\{\{\s*([^{}|!]+?)\s*(?:!!\s*[^{}|]+?)?\s*(?:\|\|\s*[^{}]+?)?\s*\}\}")
_WIDGET = re.compile(r"""<\$transclude\b[^>]*\btiddler\s*=\s*["']([^"']+)["']""")


def transclusion_targets(text: str) -> list[str]:
    """Return de-duplicated tiddler titles transcluded by this text, in order."""
    seen, out = set(), []
    for rx in (_BRACE, _WIDGET):
        for m in rx.finditer(text or ""):
            title = m.group(1).strip()
            # strip a trailing `}style;` artifact if the regex over-captured
            title = title.split("}")[0].strip()
            if title and title not in seen:
                seen.add(title)
                out.append(title)
    return out
