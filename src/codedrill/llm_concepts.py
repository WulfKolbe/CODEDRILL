"""
codedrill.llm_concepts — OPTIONAL, env-gated LLM edge proposer (OFF by default).

This is the "recursion / self-reinforcing loop" hook: an LLM may *propose* extra edges
(e.g. `related`, `builds_on`, `categorized_under`) between existing nodes, but every
proposal is fed back through the SAME deterministic gate as the heuristic edges
(`CodeGraph.edge_typechecks`) — only type-checking edges survive. Bad proposals are
silently dropped, so the loop reinforces structure instead of drifting.

Activation is explicit and safe-by-default:
  - disabled unless the env var CODEDRILL_LLM=1
  - the API key is read from the environment only (never hardcoded, never committed);
    load it from a git-ignored .env (see .env.example)
  - if the provider SDK or key is missing, this returns [] (no-op) instead of raising

No network call happens at import time, and none happens at all unless you opt in.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid import cycle at runtime
    from .schema import CodeGraph, Edge


def llm_enabled() -> bool:
    return os.environ.get("CODEDRILL_LLM", "") == "1"


def propose_edges(graph: "CodeGraph") -> list["Edge"]:
    """Return candidate edges from an LLM. Empty unless explicitly enabled + configured.

    Returned edges are *candidates only* — the compiler's fixpoint loop admits each one
    solely if `graph.edge_typechecks(edge)` passes. This function performs no validation
    itself and must never mutate `graph`.
    """
    if not llm_enabled():
        return []
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        # opted in but unconfigured: stay a no-op rather than raising mid-compile
        return []
    try:
        # Lazy import so the core never depends on a provider SDK.
        # NOTE: intentionally not implemented to call paid APIs here — wire your
        # provider of choice in and return Edge(...) candidates. Defaults to no-op.
        return _proposer_impl(graph, api_key)
    except Exception:
        return []


def _proposer_impl(graph: "CodeGraph", api_key: str) -> list["Edge"]:  # pragma: no cover
    # Deliberately a no-op stub: codedrill ships without burning anyone's API quota.
    # Replace with a real call that returns Edge candidates; they will be type-gated.
    return []
