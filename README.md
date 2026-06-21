# codedrill

A **semantic compiler for code tiddlers**. It reads a TiddlyWiki JSON array of
`paragraph` and code (`python` / `typescript`) tiddlers and emits a graph-like
knowledge base — new tiddlers (one per concept node, plus an index tiddler) and a
portable `knowledge-graph.json` — where higher-level concepts (modules, classes,
functions, language idioms, topics) and their relationships are made explicit.

Part of the **pdfdrill ecosystem**. Stdlib-only core (no third-party deps to run
or test); pdfdrill and tree-sitter/LLM hooks are optional add-ons.

```
TiddlyWiki JSON array
        │
        ▼
   route by tag ───────────────┬───────────────────────────┐
        │ "paragraph"          │ "python" / "typescript"    │
        ▼                      ▼                            │
 transclusion resolver   language extractor                │
 ({{X}}, {{X||T}},       (python: stdlib `ast`;             │
  {{X!!f}}, <$transclude>) typescript: regex heuristic,     │
        │                  tree-sitter upgrade slot)        │
        │                      │                            │
        ▼                      ▼                            │
  documents edges        module/class/function nodes        │
  (paragraph ─▶ code)    + contains/imports/inherits/calls  │
        │                      │                            │
        └──────────┬───────────┘                            │
                   ▼                                         │
            CodeGraph  (Understand-Anything schema)          │
                   │                                         │
                   ▼                                         │
        concept-lift  (language idioms → topic nodes;        │
                       shared concept → `related` edges)     │
                   │                                         │
                   ▼                                         │
        recursion fixpoint  (re-add only edges that          │
                       type-check; bounded passes;           │
                       blake2b-idempotent)                   │
                   │                                         │
                   ▼                                         │
        validate  (codedrill native signature table         │
                   + optional pdfdrill projection) ◀─────────┘
                   │
                   ▼
   emit:  graph tiddlers  ($bibkey_$type_$serial)
          knowledge-graph.json  (Understand-Anything export)
```

## Why these three ideas drive the design

The brief named three tactics for large, messy problems. Each maps to a concrete
mechanism here:

- **Bootstrapping — steal, don't reinvent.** The graph contract (node/edge types,
  the LLM-output alias tables, the language-concept catalogue) is adapted from
  [Egonex-AI/Understand-Anything](https://github.com/Egonex-AI/Understand-Anything)'s
  `schema.ts`. The deterministic graph + type-checking compiler + content-hash
  identity come straight from **pdfdrill**'s `src/semantic`. codedrill is the thin
  TiddlyWiki front-end and code extractor that wires them together.
- **Recursion — self-reinforcing loops.** After the first deterministic pass,
  `compile.py` runs a bounded fixpoint: each candidate edge (from concept-lift, and
  optionally from an LLM proposer) is admitted **only if it type-checks** against the
  signature table, then the pass repeats until no new valid edge appears. blake2b
  node/edge identity makes every pass idempotent, so the loop converges instead of
  drifting.
- **Context is everything.** `context.py` reads the `paragraph` tiddlers as a
  semantic roadmap: it derives the bibkey, abstract, authors, and — crucially — which
  prose section transcludes each code tiddler, then attaches that section as a
  `documents`/section hint and a layer hint (API/Data/Service/UI/Util/Core) on the
  code nodes. A function that lives under a "Mass Formula Solver" section is graphed
  differently from the same code under "Utilities".

## Code tiddlers in, concept graph out

- **Input.** A JSON array of tiddlers. `paragraph` tiddlers hold prose +
  transclusion syntax (the only place transclusions appear). Code tiddlers carry a
  language tag (`python`/`typescript`) and optional `type` field, and contain **no**
  transclusions — they are the leaves the paragraphs point at.
- **Output.** `drills/<name>/graph-tiddlers.json` — one tiddler per graph node named
  `$bibkey_$type_$serial` (matching your ecosystem convention), each carrying `cd.*`
  fields (`cd.id` blake2b, `cd.type`, `cd.edges` as JSON, `cd.validity`) and a
  back-transclusion `{{source}}` — plus an index tiddler `$bibkey_graph_0000` holding
  the whole graph in a field. Also `knowledge-graph.json`, the Understand-Anything
  `KnowledgeGraph` export for downstream tools.

## Install / run

Core is stdlib-only:

```bash
git clone git@github.com:WulfKolbe/CODEDRILL.git && cd CODEDRILL

# run the bundled example (heim1972: python + typescript tiddlers under one paragraph)
PYTHONPATH=src python -m codedrill demo

# compile your own TiddlyWiki JSON array
PYTHONPATH=src python -m codedrill compile path/to/tiddlers.json -o drills/myrun

# list registered language extractors
PYTHONPATH=src python -m codedrill languages
```

To also cross-check the graph through **pdfdrill**'s document-layer compiler, put a
pdfdrill checkout beside this repo and add `--pdfdrill`:

```bash
PYTHONPATH="src:../pdfdrill/src" python -m codedrill compile tiddlers.json -o drills/run --pdfdrill
```

pdfdrill's signature table is document-centric, so it validates the document/knowledge
edges and **correctly rejects** code-internal containment (class-contains-method,
function-calls-function); those stay in codedrill's own validator. That layer split is
intentional, not a bug — the run reports `projected_edges` vs `code_layer_edges`.

Optional extras: `pip install -e ".[ts]"` (tree-sitter TypeScript via the documented
upgrade slot), `".[llm]"` (LLM edge proposer, **off by default**), `".[dev]"` (pytest).

## Drilling PDFs into tiddlers (pdfdrill + MathPix)

`scripts/drill_pdf.sh` runs pdfdrill's MathPix OCR on a PDF/arXiv-id/URL, then feeds
the resulting tiddlers JSON into `codedrill compile`. **You run this yourself** —
codedrill never calls paid APIs on your behalf. It needs a sibling `pdfdrill` checkout
and a git-ignored `.env` with your **rotated** keys (see security note).

```bash
PDFDRILL_DIR=../pdfdrill ./scripts/drill_pdf.sh 2401.12345 heim1972
```

Drilled PDFs land in `pdfs/` and results in `drills/` — both are deliberately **kept**
in git (that's the point of the repo: a durable store you can branch chats off).

## Security note — rotate the leaked keys

An `env.txt` with **live** MathPix, Perplexity, OpenAI, and DeepL keys was shared into
this build. Treat all four as compromised and **rotate them now** (OpenAI project key
first). codedrill loads keys only from a git-ignored `.env` via environment variables,
never hardcodes or commits them, and made no live paid calls. `.gitignore` excludes
`.env`; verify before pushing:

```bash
git ls-files | grep -c '^\.env$'   # must print 0
```

## Layout

```
src/codedrill/
  schema.py              CodeGraph + node/edge types + signature table + UA export
  tw.py                  tiddler model, JSON load/dump, $bibkey_$type_$serial serials
  transclusion.py        {{X}} / {{X||T}} / {{X!!f}} / <$transclude/> parser
  context.py             bibkey/abstract/authors/section + layer hints (the roadmap)
  compile.py             orchestrator: extract → context-link → concept-lift → fixpoint → validate → emit
  concepts.py            12-idiom language-concept catalogue (adapted from UA)
  pdfdrill_adapter.py    signature-aware projection into pdfdrill's compiler
  llm_concepts.py        optional, env-gated edge proposer (CODEDRILL_LLM=1), off by default
  extractors/
    base.py              extractor registry
    python_ast.py        stdlib `ast` extractor
    typescript_heuristic.py  regex extractor + tree-sitter upgrade slot
examples/sample_tiddlers.json
scripts/drill_pdf.sh  scripts/create_and_push.sh
tests/   (7 tests, stdlib + pytest)
```

## Reuse & licence

MIT © 2026 Wulf Kolbe. Bootstraps from pdfdrill (Wulf Kolbe) and adapts the
knowledge-graph schema, alias tables, and concept catalogue from Egonex-AI's
Understand-Anything (MIT). See `NOTICE`.
