"""
codedrill.tw — TiddlyWiki tiddler model + JSON-array I/O + serial naming.

A *tiddler* is the unit of a TiddlyWiki: a `title`, a `text` body, a tag list, and
arbitrary extra `fields`. codedrill reads a JSON array of tiddlers (the export format
of TiddlyWiki) and emits another JSON array (the graph tiddlers).

Tag handling mirrors TiddlyWiki's own `$tw.utils.parseStringArray` / `stringifyList`:
tags are space-separated, and any tag containing whitespace is wrapped in `[[...]]`.

Graph tiddlers are named `$bibkey_$type_$serial` (e.g. `heim1972_function_0003`) — the
serial is a zero-padded, per-(bibkey,type) counter handed out by `SerialAllocator`.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

# Fields that are first-class on a tiddler; everything else lands in `.fields`.
_RESERVED = {"title", "text", "tags"}

_LISTITEM = re.compile(r"\[\[(.*?)\]\]|(\S+)")


def parse_tags(value: Any) -> list[str]:
    """Parse a TiddlyWiki tag string (or list) into a list of tag names."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    out: list[str] = []
    for m in _LISTITEM.finditer(str(value)):
        out.append(m.group(1) if m.group(1) is not None else m.group(2))
    return out


def join_tags(tags: Iterable[str]) -> str:
    """Stringify a tag list the way TiddlyWiki does ([[...]] for tags with spaces)."""
    parts = []
    for t in tags:
        t = str(t)
        parts.append(f"[[{t}]]" if (" " in t or "\t" in t) else t)
    return " ".join(parts)


@dataclass
class Tiddler:
    title: str
    text: str = ""
    tags: list[str] = field(default_factory=list)
    fields: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Tiddler":
        title = d.get("title", "")
        text = d.get("text", "")
        tags = parse_tags(d.get("tags"))
        fields = {k: v for k, v in d.items() if k not in _RESERVED}
        return cls(title=title, text=text, tags=tags, fields=fields)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"title": self.title, "text": self.text}
        # A serialized tiddler keeps a single "tags" string. If the emitter already
        # stashed a "tags" field (the common path in compile.emit_tiddlers), trust it;
        # otherwise stringify the tags list.
        out.update(self.fields)
        if "tags" not in out and self.tags:
            out["tags"] = join_tags(self.tags)
        return out


class SerialAllocator:
    """Hands out `$bibkey_$type_$serial` titles with a per-(bibkey,type) counter."""

    def __init__(self, start: int = 1, width: int = 4) -> None:
        self._counters: dict[tuple[str, str], int] = {}
        self._start = start
        self._width = width

    def title(self, bibkey: str, type_: str) -> str:
        bibkey = bibkey or "doc"
        key = (bibkey, type_)
        n = self._counters.get(key, self._start - 1) + 1
        self._counters[key] = n
        return f"{bibkey}_{type_}_{n:0{self._width}d}"


def load_array(path: str | Path) -> list[Tiddler]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a JSON array of tiddlers, got {type(data).__name__}")
    return [Tiddler.from_dict(d) for d in data]


def dump_array(tiddlers: list[Tiddler], path: str | Path) -> None:
    payload = [t.to_dict() for t in tiddlers]
    Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
