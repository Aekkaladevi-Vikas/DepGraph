"""
analyzer.py — Core analysis engine.

Provides:
  - Blast radius  : what breaks if X is removed?
  - Circular imports: detect all dependency cycles
  - Orphan modules  : modules nothing depends on
  - Dependency list : what does X depend on?
"""

import networkx as nx
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field


# ─────────────────────────────────────────────
#  Data classes for clean return types
# ─────────────────────────────────────────────

@dataclass
class BlastRadius:
    target: str
    direct_dependents: List[str]        # nodes that directly import target
    transitive_dependents: List[str]    # nodes that indirectly depend on target
    total_impact: int
    impact_percentage: float            # % of project affected


@dataclass
class Cycle:
    nodes: List[str]                    # the cycle path
    length: int
    severity: str                       # CRITICAL / HIGH / MEDIUM / LOW
    suggestion: str                     # how to fix it


@dataclass
class AnalysisReport:
    blast_radii: Dict[str, BlastRadius] = field(default_factory=dict)
    cycles: List[Cycle] = field(default_factory=list)
    orphans: List[str] = field(default_factory=list)
    most_depended_on: List[Tuple[str, int]] = field(default_factory=list)
    most_dependencies: List[Tuple[str, int]] = field(default_factory=list)


# ─────────────────────────────────────────────
#  Main Analyzer class
# ─────────────────────────────────────────────

class Analyzer:

    def __init__(self, graph: nx.DiGraph):
        self.G = graph
        self._total_nodes = graph.number_of_nodes()

    # ── Blast Radius ──────────────────────────

    def blast_radius(self, target: str) -> BlastRadius:
        """
        Find everything that would break if `target` is removed.

        Args:
            target: A node name (module, class, or function).

        Returns:
            BlastRadius object with direct and transitive dependents.
        """
        if target not in self.G:
            raise ValueError(
                f"'{target}' not found in graph. "
                f"Run `depgraph scan` first and check the exact node name."
            )

        # Direct: nodes that have a direct edge to target
        direct = list(self.G.predecessors(target))

        # Transitive: all ancestors (nodes that can reach target by any path)
        all_ancestors = nx.ancestors(self.G, target)
        transitive = list(all_ancestors - set(direct))

        total = len(direct) + len(transitive)
        percentage = (total / self._total_nodes * 100) if self._total_nodes else 0.0

        return BlastRadius(
            target=target,
            direct_dependents=sorted(direct),
            transitive_dependents=sorted(transitive),
            total_impact=total,
            impact_percentage=round(percentage, 1),
        )

    def blast_radius_all(self) -> Dict[str, BlastRadius]:
        """Compute blast radius for every node. Useful for ranking."""
        return {node: self.blast_radius(node) for node in self.G.nodes}

    # ── Circular Imports ──────────────────────

    def find_cycles(self) -> List[Cycle]:
        """
        Detect all circular import chains in the project.

        Returns:
            List of Cycle objects, sorted by severity (worst first).
        """
        raw_cycles = list(nx.simple_cycles(self.G))
        cycles = []

        for raw in raw_cycles:
            length = len(raw)
            severity = self._cycle_severity(length)
            suggestion = self._cycle_suggestion(raw, length)

            cycles.append(Cycle(
                nodes=raw,
                length=length,
                severity=severity,
                suggestion=suggestion,
            ))

        # Sort: shortest (most critical) first
        cycles.sort(key=lambda c: c.length)
        return cycles

    def _cycle_severity(self, length: int) -> str:
        if length <= 2:
            return "CRITICAL"
        elif length <= 4:
            return "HIGH"
        elif length <= 7:
            return "MEDIUM"
        else:
            return "LOW"

    def _cycle_suggestion(self, cycle: List[str], length: int) -> str:
        if length == 2:
            a, b = cycle[0], cycle[1]
            a_short = a.split(".")[-1]
            b_short = b.split(".")[-1]
            return (
                f"Extract shared logic from '{a_short}' and '{b_short}' "
                f"into a new 'common.py' or 'shared.py' module."
            )
        elif length <= 4:
            return (
                f"Use dependency injection or move shared interfaces "
                f"to a separate 'interfaces.py' or 'base.py' module."
            )
        else:
            return (
                f"This is a long transitive cycle across {length} modules. "
                f"Consider introducing lazy imports or restructuring the package hierarchy."
            )

    # ── Orphan Detection ──────────────────────

    def find_orphans(self) -> List[str]:
        """
        Find modules/classes/functions that nothing depends on.
        These may be dead code or entry points.
        """
        return sorted([
            node for node in self.G.nodes
            if self.G.in_degree(node) == 0
        ])

    # ── Dependency List ───────────────────────

    def dependencies_of(self, target: str) -> Dict:
        """
        What does `target` depend on?

        Returns:
            Dict with direct and transitive dependencies.
        """
        if target not in self.G:
            raise ValueError(f"'{target}' not found in graph.")

        direct = list(self.G.successors(target))
        transitive = list(nx.descendants(self.G, target) - set(direct))

        return {
            "target": target,
            "direct": sorted(direct),
            "transitive": sorted(transitive),
            "total": len(direct) + len(transitive),
        }

    # ── Hot Spots ─────────────────────────────

    def most_depended_on(self, top_n: int = 10) -> List[Tuple[str, int]]:
        """Nodes with the highest in-degree — most used across the project."""
        return sorted(
            [(node, self.G.in_degree(node)) for node in self.G.nodes],
            key=lambda x: x[1],
            reverse=True,
        )[:top_n]

    def most_dependencies(self, top_n: int = 10) -> List[Tuple[str, int]]:
        """Nodes with the highest out-degree — depend on the most others."""
        return sorted(
            [(node, self.G.out_degree(node)) for node in self.G.nodes],
            key=lambda x: x[1],
            reverse=True,
        )[:top_n]

    # ── Full Report ───────────────────────────

    def full_report(self) -> AnalysisReport:
        """Run all analyses and return a combined report."""
        return AnalysisReport(
            cycles=self.find_cycles(),
            orphans=self.find_orphans(),
            most_depended_on=self.most_depended_on(),
            most_dependencies=self.most_dependencies(),
        )