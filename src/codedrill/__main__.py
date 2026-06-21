"""
codedrill CLI.

    python -m codedrill demo                       run the bundled example
    python -m codedrill compile <tiddlers.json> [-o DIR] [--pdfdrill]
    python -m codedrill languages                  list registered extractors
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .compile import compile_file, compile_tiddlers, CompileOutput
from .extractors.base import languages
from .tw import load_array


def _print_summary(out: CompileOutput, out_dir: Path | None) -> None:
    g = out.graph
    print(f"  nodes: {len(g.nodes)}   edges: {len(g.edges)}   validity: {out.result.validity}")
    by_type: dict[str, int] = {}
    for n in g.nodes.values():
        by_type[n.type] = by_type.get(n.type, 0) + 1
    print("  node types: " + ", ".join(f"{k}={v}" for k, v in sorted(by_type.items())))
    crit = out.result.critical
    if crit:
        print(f"  critical warnings ({len(crit)}):")
        for w in crit[:10]:
            print(f"    - {w.message}")
    if out.pdfdrill is not None:
        p = out.pdfdrill
        if "error" in p:
            print(f"  pdfdrill: unavailable ({p['error']})")
        else:
            print(f"  pdfdrill projection: validity={p['validity']} "
                  f"entities={p['entities']} projected_edges={p['projected_edges']} "
                  f"code_layer_edges={p['code_layer_edges']}")
    if out_dir is not None:
        print(f"  wrote: {out_dir/'graph-tiddlers.json'}")
        print(f"         {out_dir/'knowledge-graph.json'}")


def cmd_demo(_args: argparse.Namespace) -> int:
    sample = Path(__file__).resolve().parents[2] / "examples" / "sample_tiddlers.json"
    print(f"codedrill demo — compiling {sample.name}")
    out = compile_tiddlers(load_array(sample))
    _print_summary(out, None)
    return 0 if out.result.validity == "valid" else 1


def cmd_compile(args: argparse.Namespace) -> int:
    out_dir = Path(args.output)
    print(f"codedrill compile — {args.input} -> {out_dir}")
    out = compile_file(args.input, out_dir, with_pdfdrill=args.pdfdrill)
    _print_summary(out, out_dir)
    return 0 if out.result.validity == "valid" else 1


def cmd_languages(_args: argparse.Namespace) -> int:
    # importing compile registered the bundled extractors
    print("registered extractors: " + ", ".join(languages()))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="codedrill", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("demo", help="run the bundled example").set_defaults(func=cmd_demo)

    c = sub.add_parser("compile", help="compile a TiddlyWiki JSON array")
    c.add_argument("input", help="path to a tiddlers JSON array")
    c.add_argument("-o", "--output", default="drills/out", help="output directory")
    c.add_argument("--pdfdrill", action="store_true",
                   help="also cross-check via pdfdrill's compiler (needs pdfdrill on PYTHONPATH)")
    c.set_defaults(func=cmd_compile)

    sub.add_parser("languages", help="list registered extractors").set_defaults(func=cmd_languages)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
