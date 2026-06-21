"""
codedrill.concepts — the language-concept catalogue (the "higher level" topic layer).

Deterministic idiom detectors. Each returns a list of canonical concept/topic names
that a code node *exemplifies*; the compiler lifts these into `topic` nodes and draws
`exemplifies` edges, then concept-lift turns shared topics into `related` edges.

The 12-idiom catalogue is adapted from Understand-Anything's language-concept list
(Egonex-AI, MIT). Concept names are kept language-neutral where they overlap (e.g.
"async", "generics") so a Python `async def` and a TypeScript `async` function land on
the *same* topic node and get related.
"""
from __future__ import annotations

import ast
import re
from typing import Iterable

# --- Python -------------------------------------------------------------------
def detect_python_concepts(node: ast.AST) -> list[str]:
    """Detect idioms in a single def/class node (12-idiom catalogue)."""
    found: set[str] = set()

    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if node.decorator_list:
            found.add("decorator")
            for dec in node.decorator_list:
                dname = getattr(dec, "id", None) or getattr(dec, "attr", None)
                if dname == "staticmethod":
                    found.add("staticmethod")
                elif dname == "classmethod":
                    found.add("classmethod")
                elif dname == "property":
                    found.add("property")
        if isinstance(node, ast.AsyncFunctionDef):
            found.add("async")
        # type hints
        if node.returns or any(a.annotation for a in node.args.args):
            found.add("type-hints")

    if isinstance(node, ast.ClassDef):
        if node.decorator_list:
            found.add("decorator")
            if any((getattr(d, "id", None) or getattr(d, "attr", None)) == "dataclass"
                   for d in node.decorator_list):
                found.add("dataclass")

    for sub in ast.walk(node):
        if isinstance(sub, (ast.Yield, ast.YieldFrom)):
            found.add("generator")
        elif isinstance(sub, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            found.add("comprehension")
        elif isinstance(sub, (ast.With, ast.AsyncWith)):
            found.add("context-manager")
        elif isinstance(sub, ast.Try):
            found.add("exception-handling")
        elif isinstance(sub, ast.Lambda):
            found.add("lambda")
        elif isinstance(sub, (ast.Await,)):
            found.add("async")

    # naive self-recursion: a function that calls its own name
    name = getattr(node, "name", None)
    if name:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                callee = getattr(sub.func, "id", None) or getattr(sub.func, "attr", None)
                if callee == name:
                    found.add("recursion")
                    break

    return sorted(found)


# --- TypeScript ---------------------------------------------------------------
_TS_PATTERNS: list[tuple[str, "re.Pattern[str]"]] = [
    ("generics",            re.compile(r"<\s*[A-Z]\w*(\s+extends\b)?")),
    ("async",               re.compile(r"\basync\b|\bawait\b")),
    ("promise",             re.compile(r"\bPromise\s*<")),
    ("interface",           re.compile(r"\binterface\s+\w+")),
    ("arrow-function",      re.compile(r"=>")),
    ("exception-handling",  re.compile(r"\btry\s*\{|\bcatch\s*\(")),
    ("decorator",           re.compile(r"(^|\s)@\w+")),
    ("type-hints",          re.compile(r":\s*[A-Za-z_]\w*(\[\])?\s*[;,=)]")),
    ("optional-chaining",   re.compile(r"\?\.")),
    ("destructuring",       re.compile(r"(const|let|var)\s*[\[{]")),
    ("spread",              re.compile(r"\.\.\.")),
    ("template-literal",    re.compile(r"`[^`]*\$\{")),
]


def detect_typescript_concepts(code: str) -> list[str]:
    found = {name for name, rx in _TS_PATTERNS if rx.search(code or "")}
    return sorted(found)
