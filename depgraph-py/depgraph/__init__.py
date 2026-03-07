"""
depgraph — Interactive dependency graph & blast-radius analyzer for Python projects.

Usage:
    depgraph scan ./my_project
    depgraph impact my_module.MyClass
    depgraph cycles ./my_project
    depgraph visualize ./my_project
"""

from depgraph.crawler import crawl_project
from depgraph.graph import build_graph
from depgraph.analyzer import Analyzer

__version__ = "0.1.0"
__all__ = ["crawl_project", "build_graph", "Analyzer"]