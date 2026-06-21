"""
codedrill test suite (stdlib unittest; runs under pytest too).

Seven tests covering the contract end to end:
  1. tag parse/stringify round-trip
  2. transclusion syntax parsing (all four forms)
  3. blake2b node identity is stable/idempotent
  4. signature table rejects a type-violating edge
  5. python ast extractor builds module/class/function/contains/inherits + concepts
  6. typescript heuristic extractor builds module/class/function + concepts
  7. full compile of the bundled sample is valid and emits $bibkey_$type_$serial tiddlers
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from codedrill.tw import parse_tags, join_tags, Tiddler, load_array  # noqa: E402
from codedrill.transclusion import transclusion_targets  # noqa: E402
from codedrill.schema import CodeGraph, Node, Edge  # noqa: E402
from codedrill.compile import compile_tiddlers  # noqa: E402
from codedrill.extractors.base import for_language  # noqa: E402
import codedrill.extractors.python_ast  # noqa: E402,F401  (registers)
import codedrill.extractors.typescript_heuristic  # noqa: E402,F401  (registers)

SAMPLE = Path(__file__).resolve().parents[1] / "examples" / "sample_tiddlers.json"


class TestTags(unittest.TestCase):
    def test_tag_roundtrip(self):
        self.assertEqual(parse_tags("a b [[two words]] c"), ["a", "b", "two words", "c"])
        s = join_tags(["a", "two words", "c"])
        self.assertIn("[[two words]]", s)
        self.assertEqual(parse_tags(s), ["a", "two words", "c"])


class TestTransclusion(unittest.TestCase):
    def test_all_forms(self):
        text = ("see {{Alpha}} and {{Beta||Tmpl}} and {{Gamma!!field}} "
                'and <$transclude tiddler="Delta"/>')
        self.assertEqual(transclusion_targets(text), ["Alpha", "Beta", "Gamma", "Delta"])


class TestIdentity(unittest.TestCase):
    def test_blake2b_stable(self):
        a = CodeGraph.node_id("function", "m.f", "python")
        b = CodeGraph.node_id("function", "m.f", "python")
        self.assertEqual(a, b)
        self.assertTrue(a.startswith("function:"))
        self.assertNotEqual(a, CodeGraph.node_id("function", "m.g", "python"))


class TestSignatureGate(unittest.TestCase):
    def test_type_violation_is_invalid(self):
        g = CodeGraph()
        f = g.add_node(Node(CodeGraph.node_id("function", "m.f"), "function", "f"))
        t = g.add_node(Node(CodeGraph.node_id("topic", "x", "concept"), "topic", "x"))
        # function -inherits-> topic is a type violation (inherits is class->class)
        g.add_edge(Edge(f.id, t.id, "inherits"))
        self.assertEqual(g.compile().validity, "invalid")
        self.assertFalse(g.edge_typechecks(Edge(f.id, t.id, "inherits")))


class TestPythonExtractor(unittest.TestCase):
    def test_python_nodes_and_edges(self):
        g = CodeGraph()
        code = ("class A:\n    def m(self):\n        return 1\n"
                "class B(A):\n    pass\n"
                "def gen():\n    yield 1\n")
        mid = for_language("python").extract(g, code=code, module_name="mod",
                                             source_title="t_py")
        types = sorted({n.type for n in g.nodes.values()})
        self.assertIn("module", types)
        self.assertIn("class", types)
        self.assertIn("function", types)
        self.assertTrue(any(e.type == "contains" for e in g.edges.values()))
        self.assertTrue(any(e.type == "inherits" for e in g.edges.values()))
        # generator concept lifted to a topic via exemplifies
        self.assertTrue(any(e.type == "exemplifies" for e in g.edges.values()))
        self.assertEqual(g.nodes[mid].type, "module")


class TestTypeScriptExtractor(unittest.TestCase):
    def test_typescript_nodes(self):
        g = CodeGraph()
        code = ("import { X } from './x';\n"
                "export interface I { a: number }\n"
                "export class C extends Base { }\n"
                "export const f = (x: number) => x;\n")
        for_language("typescript").extract(g, code=code, module_name="m", source_title="t_ts")
        self.assertTrue(any(e.type == "imports" for e in g.edges.values()))
        self.assertTrue(any(e.type == "inherits" for e in g.edges.values()))
        self.assertTrue(any(n.type == "function" for n in g.nodes.values()))


class TestFullCompile(unittest.TestCase):
    def test_sample_is_valid_and_named(self):
        out = compile_tiddlers(load_array(SAMPLE))
        self.assertEqual(out.result.validity, "valid")
        self.assertTrue(out.tiddlers)
        titles = [t.title for t in out.tiddlers]
        # $bibkey_$type_$serial naming, plus the index tiddler
        self.assertTrue(any(t.startswith("heim1972_") for t in titles))
        self.assertIn("heim1972_graph_0000", titles)
        # the graph index tiddler carries an Understand-Anything knowledge-graph
        idx = next(t for t in out.tiddlers if t.title == "heim1972_graph_0000")
        kg = json.loads(idx.fields["knowledge-graph"])
        self.assertEqual(kg["version"], "1")
        self.assertTrue(kg["nodes"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
