"""
tests/test_depgraph.py — Unit tests for depgraph core logic.

Run with: pytest tests/ -v
"""

import sys
import tempfile
from pathlib import Path

import pytest
import networkx as nx

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from depgraph.crawler import crawl_project
from depgraph.parser import parse_file, filepath_to_module, parse_project
from depgraph.graph import build_graph, get_summary
from depgraph.analyzer import Analyzer


# ─────────────────────────────────────────────
#  Fixtures: create a fake project on disk
# ─────────────────────────────────────────────

@pytest.fixture
def fake_project(tmp_path):
    """Create a small fake Python project with known dependencies."""

    # utils/logger.py
    (tmp_path / "utils").mkdir()
    (tmp_path / "utils" / "__init__.py").write_text("")
    (tmp_path / "utils" / "logger.py").write_text("""
def log(msg):
    print(msg)
""")

    # db/models.py
    (tmp_path / "db").mkdir()
    (tmp_path / "db" / "__init__.py").write_text("")
    (tmp_path / "db" / "models.py").write_text("""
class Transaction:
    def __init__(self, amount):
        self.amount = amount
""")

    # payments/processor.py
    (tmp_path / "payments").mkdir()
    (tmp_path / "payments" / "__init__.py").write_text("")
    (tmp_path / "payments" / "processor.py").write_text("""
from utils.logger import log
from db.models import Transaction

class PaymentProcessor:
    def charge(self, amount):
        log("charging")
        txn = Transaction(amount=amount)
        return txn
""")

    # main.py
    (tmp_path / "main.py").write_text("""
from payments.processor import PaymentProcessor

def run():
    p = PaymentProcessor()
    p.charge(100)
""")

    return tmp_path


@pytest.fixture
def cyclic_project(tmp_path):
    """Create a project with a circular import."""
    (tmp_path / "a.py").write_text("from b import something\n")
    (tmp_path / "b.py").write_text("from a import something\n")
    (tmp_path / "c.py").write_text("import a\nimport b\n")
    return tmp_path


@pytest.fixture
def built_graph(fake_project):
    files = crawl_project(str(fake_project))
    modules = parse_project(files, fake_project)
    return build_graph(modules), modules


# ─────────────────────────────────────────────
#  Crawler tests
# ─────────────────────────────────────────────

class TestCrawler:

    def test_finds_all_py_files(self, fake_project):
        files = crawl_project(str(fake_project))
        names = [f.name for f in files]
        assert "logger.py" in names
        assert "models.py" in names
        assert "processor.py" in names
        assert "main.py" in names

    def test_excludes_pycache(self, fake_project):
        pycache = fake_project / "__pycache__"
        pycache.mkdir()
        (pycache / "module.py").write_text("")
        files = crawl_project(str(fake_project))
        assert not any("__pycache__" in str(f) for f in files)

    def test_raises_on_missing_path(self):
        with pytest.raises(FileNotFoundError):
            crawl_project("/nonexistent/path/xyz")

    def test_returns_sorted_paths(self, fake_project):
        files = crawl_project(str(fake_project))
        assert files == sorted(files)


# ─────────────────────────────────────────────
#  Parser tests
# ─────────────────────────────────────────────

class TestParser:

    def test_module_naming(self, fake_project):
        proc = fake_project / "payments" / "processor.py"
        name = filepath_to_module(proc, fake_project)
        assert name == "payments.processor"

    def test_init_module_naming(self, fake_project):
        init = fake_project / "payments" / "__init__.py"
        name = filepath_to_module(init, fake_project)
        assert name == "payments"

    def test_extracts_imports(self, fake_project):
        proc = fake_project / "payments" / "processor.py"
        parsed = parse_file(proc, fake_project)
        combined = parsed.imports + parsed.from_imports
        assert any("logger" in imp for imp in combined)
        assert any("Transaction" in imp for imp in combined)

    def test_extracts_classes(self, fake_project):
        proc = fake_project / "payments" / "processor.py"
        parsed = parse_file(proc, fake_project)
        assert any("PaymentProcessor" in cls for cls in parsed.classes)

    def test_extracts_functions(self, fake_project):
        proc = fake_project / "payments" / "processor.py"
        parsed = parse_file(proc, fake_project)
        assert any("charge" in fn for fn in parsed.functions)

    def test_handles_syntax_error(self, tmp_path):
        bad = tmp_path / "bad.py"
        bad.write_text("def broken(:\n    pass\n")
        parsed = parse_file(bad, tmp_path)
        assert len(parsed.errors) > 0


# ─────────────────────────────────────────────
#  Graph tests
# ─────────────────────────────────────────────

class TestGraph:

    def test_graph_has_nodes(self, built_graph):
        G, _ = built_graph
        assert G.number_of_nodes() > 0

    def test_graph_is_directed(self, built_graph):
        G, _ = built_graph
        assert isinstance(G, nx.DiGraph)

    def test_module_nodes_exist(self, built_graph):
        G, _ = built_graph
        nodes = list(G.nodes)
        assert any("payments" in n for n in nodes)
        assert any("db" in n for n in nodes)
        assert any("utils" in n for n in nodes)

    def test_summary_structure(self, built_graph):
        G, modules = built_graph
        summary = get_summary(G, modules)
        assert "total_files" in summary
        assert "total_modules" in summary
        assert "total_edges" in summary
        assert summary["total_files"] > 0


# ─────────────────────────────────────────────
#  Analyzer tests
# ─────────────────────────────────────────────

class TestAnalyzer:

    def test_blast_radius_returns_result(self, built_graph):
        G, _ = built_graph
        analyzer = Analyzer(G)
        # Pick any module node
        module_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "module"]
        if module_nodes:
            result = analyzer.blast_radius(module_nodes[0])
            assert result.target == module_nodes[0]
            assert isinstance(result.total_impact, int)

    def test_blast_radius_invalid_node(self, built_graph):
        G, _ = built_graph
        analyzer = Analyzer(G)
        with pytest.raises(ValueError):
            analyzer.blast_radius("nonexistent.module.xyz")

    def test_no_cycles_in_clean_project(self, built_graph):
        G, _ = built_graph
        analyzer = Analyzer(G)
        cycles = analyzer.find_cycles()
        assert cycles == []

    def test_detects_cycles(self, cyclic_project):
        files = crawl_project(str(cyclic_project))
        modules = parse_project(files, cyclic_project)
        G = build_graph(modules)
        analyzer = Analyzer(G)
        cycles = analyzer.find_cycles()
        assert len(cycles) > 0

    def test_cycle_has_severity(self, cyclic_project):
        files = crawl_project(str(cyclic_project))
        modules = parse_project(files, cyclic_project)
        G = build_graph(modules)
        analyzer = Analyzer(G)
        cycles = analyzer.find_cycles()
        for cycle in cycles:
            assert cycle.severity in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
            assert len(cycle.suggestion) > 0

    def test_orphan_detection(self, built_graph):
        G, _ = built_graph
        analyzer = Analyzer(G)
        orphans = analyzer.find_orphans()
        assert isinstance(orphans, list)

    def test_dependencies_of(self, built_graph):
        G, _ = built_graph
        analyzer = Analyzer(G)
        module_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "module"]
        if module_nodes:
            result = analyzer.dependencies_of(module_nodes[0])
            assert "direct" in result
            assert "transitive" in result

    def test_most_depended_on(self, built_graph):
        G, _ = built_graph
        analyzer = Analyzer(G)
        hot = analyzer.most_depended_on(top_n=3)
        assert len(hot) <= 3
        # Should be sorted descending
        counts = [count for _, count in hot]
        assert counts == sorted(counts, reverse=True)

    def test_full_report(self, built_graph):
        G, _ = built_graph
        analyzer = Analyzer(G)
        report = analyzer.full_report()
        assert hasattr(report, "cycles")
        assert hasattr(report, "orphans")
        assert hasattr(report, "most_depended_on")