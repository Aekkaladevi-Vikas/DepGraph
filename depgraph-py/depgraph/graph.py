"""
graph.py — Builds a directed NetworkX graph from parsed module data.

Nodes = modules, classes, functions
Edges = dependencies (A → B means A imports/uses B)
"""

import networkx as nx
from typing import List, Dict, Set, Optional
from depgraph.parser import ParsedModule


def build_graph(modules: List[ParsedModule]) -> nx.DiGraph:
    """
    Build a directed dependency graph from all parsed modules.

    Each node has attributes:
      - type: "module" | "class" | "function"
      - filepath: source file path

    Each edge has attributes:
      - kind: "import" | "from_import"

    Args:
        modules: List of ParsedModule objects from parser.

    Returns:
        A directed NetworkX graph.
    """
    G = nx.DiGraph()

    # --- Index all known symbols for fast lookup ---
    known_modules:   Set[str] = set()
    known_classes:   Set[str] = set()
    known_functions: Set[str] = set()

    for mod in modules:
        known_modules.add(mod.module_name)
        known_classes.update(mod.classes)
        known_functions.update(mod.functions)

    all_known = known_modules | known_classes | known_functions

    # --- Build suffix index for fast tail matching ---
    # e.g. "myapp.utils" → also indexed under "utils"
    # This lets us resolve "from myapp.utils import X" even when
    # the known module is just "utils" (project scanned from inside)
    suffix_index: Dict[str, str] = {}
    for name in all_known:
        parts = name.split(".")
        for i in range(len(parts)):
            suffix = ".".join(parts[i:])
            # Only store if no conflict (first one wins)
            if suffix not in suffix_index:
                suffix_index[suffix] = name

    # --- Add all nodes first ---
    for mod in modules:
        G.add_node(
            mod.module_name,
            type="module",
            filepath=str(mod.filepath),
            label=mod.module_name.split(".")[-1],
        )
        for cls in mod.classes:
            G.add_node(cls, type="class", filepath=str(mod.filepath),
                       label=cls.split(".")[-1])
        for fn in mod.functions:
            if fn not in known_classes:
                G.add_node(fn, type="function", filepath=str(mod.filepath),
                           label=fn.split(".")[-1])

    # --- Add edges based on imports ---
    for mod in modules:
        src = mod.module_name

        for imp in mod.imports:
            target = _resolve(imp, all_known, known_modules, suffix_index)
            if target and target != src:
                G.add_edge(src, target, kind="import")
                # Also connect to parent module if target is a class/function
                _add_parent_edge(G, src, target, known_modules)

        for from_imp in mod.from_imports:
            target = _resolve(from_imp, all_known, known_modules, suffix_index)
            if target and target != src:
                G.add_edge(src, target, kind="from_import")
                # Also connect to parent module if target is a class/function
                _add_parent_edge(G, src, target, known_modules)

    return G


def _add_parent_edge(
    G: nx.DiGraph,
    src: str,
    target: str,
    known_modules: Set[str],
) -> None:
    """
    If target is a class/function (e.g. myapp.models.User),
    also add an edge to its parent module (myapp.models).
    This ensures the module itself is not falsely marked as an orphan
    just because imports reference its classes directly.
    """
    parts = target.split(".")
    for i in range(len(parts) - 1, 0, -1):
        parent = ".".join(parts[:i])
        if parent in known_modules and parent != src and parent != target:
            if not G.has_edge(src, parent):
                G.add_edge(src, parent, kind="from_import")
            break


def _resolve(
    symbol:       str,
    all_known:    Set[str],
    known_modules: Set[str],
    suffix_index: Dict[str, str],
) -> str | None:
    """
    Try to match an import string to a known internal project symbol.
    Returns the matched node name or None if it's an external library.

    Resolution strategies (tried in order):
      1. Exact match
      2. Longest prefix match       — "a.b.c" → try "a.b.c", "a.b", "a"
      3. Suffix/tail match          — "myapp.utils.MyClass" → try "utils.MyClass", "MyClass"
      4. Suffix prefix match        — strip package prefix, then try prefix match
    """
    if not symbol:
        return None

    # ── Strategy 1: Exact match ────────────────────────────
    if symbol in all_known:
        return symbol

    # ── Strategy 2: Longest prefix match ──────────────────
    # "myapp.utils.MyClass" → try "myapp.utils", "myapp"
    parts = symbol.split(".")
    for i in range(len(parts) - 1, 0, -1):
        candidate = ".".join(parts[:i])
        if candidate in all_known:
            return candidate

    # ── Strategy 3: Suffix index match ────────────────────
    # "myapp.utils.MyClass" → try suffix_index["utils.MyClass"],
    #                         suffix_index["MyClass"]
    if symbol in suffix_index:
        return suffix_index[symbol]

    for i in range(1, len(parts)):
        suffix = ".".join(parts[i:])
        if suffix in suffix_index:
            return suffix_index[suffix]

    # ── Strategy 4: Suffix prefix match ───────────────────
    # Strip leading parts and try prefix matching on the remainder
    # Handles: "myapp.utils.helper" where known is "utils"
    for i in range(1, len(parts)):
        remainder = ".".join(parts[i:])
        rem_parts = remainder.split(".")
        for j in range(len(rem_parts) - 1, 0, -1):
            candidate = ".".join(rem_parts[:j])
            if candidate in all_known:
                return candidate

    return None  # external library — ignore


def get_summary(G: nx.DiGraph, modules: List[ParsedModule]) -> Dict:
    """Return a summary dict of the graph statistics."""
    module_nodes  = [n for n, d in G.nodes(data=True) if d.get("type") == "module"]
    class_nodes   = [n for n, d in G.nodes(data=True) if d.get("type") == "class"]
    func_nodes    = [n for n, d in G.nodes(data=True) if d.get("type") == "function"]

    orphans = [n for n in G.nodes if G.in_degree(n) == 0 and G.out_degree(n) == 0]

    parse_errors = [
        {"module": m.module_name, "errors": m.errors}
        for m in modules if m.errors
    ]

    return {
        "total_files":     len(modules),
        "total_modules":   len(module_nodes),
        "total_classes":   len(class_nodes),
        "total_functions": len(func_nodes),
        "total_nodes":     G.number_of_nodes(),
        "total_edges":     G.number_of_edges(),
        "orphan_modules":  orphans,
        "parse_errors":    parse_errors,
    }