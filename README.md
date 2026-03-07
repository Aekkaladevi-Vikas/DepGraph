# depgraph 🔍

> **Interactive Python dependency graph & blast-radius analyzer**
>
> Know exactly what breaks *before* you refactor.

[![PyPI version](https://badge.fury.io/py/depgraph-py.svg)](https://badge.fury.io/py/depgraph-py)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## The Problem

You want to delete a function, rename a class, or split a module — but you have no idea what else will break. Your IDE shows one level of imports. You need the full picture.

`depgraph` gives you that picture in seconds:

- 💥 **Blast radius** — *"if I delete X, these 14 things break"*
- 🔴 **Circular import detection** — every cycle, with severity scores and fix suggestions
- 👻 **Orphan detection** — dead code that nothing imports
- 🌐 **Interactive D3.js graph** — zoomable, draggable, folder-clustered, with a click-to-inspect node panel

**Zero execution** — purely static analysis via Python's built-in `ast` module.

---

## Install

```bash
pip install depgraph-py
```

---

## Quick Start

```bash
# Scan your project and get a full summary
depgraph scan ./my_project

# Open the interactive graph in your browser
depgraph visualize ./my_project

# Find what breaks if you remove a symbol
depgraph impact ./my_project payments.processor.PaymentProcessor

# Detect all circular imports
depgraph cycles ./my_project

# Find unused modules (dead code candidates)
depgraph orphans ./my_project

# See what a module depends on
depgraph deps ./my_project payments.processor
```

### Using `python -m` (if the CLI command is blocked)

If your organisation's security policy blocks installed entry points, run every command via `python -m depgraph.cli` instead — behaviour is identical:

```bash
python -m depgraph.cli scan     "D:\my_project"
python -m depgraph.cli visualize "D:\my_project"
python -m depgraph.cli impact   "D:\my_project" payments.processor.PaymentProcessor
python -m depgraph.cli cycles   "D:\my_project" --strict
python -m depgraph.cli orphans  "D:\my_project"
python -m depgraph.cli deps     "D:\my_project" smtp
```

> **Windows paths with spaces** must be quoted: (Example)
> ```bash
> python -m depgraph.cli deps "C:\my-project\project" module_name
> ```

---

## Commands

### `depgraph scan <path>`

Full project summary — files, modules, classes, functions, cycle count, orphan count, and a hot-spots table of the most depended-on modules.

```
╭─ depgraph — /home/user/my_project ─╮
│                                     │
│  📁 Python files       42           │
│  📦 Modules            38           │
│  🏛️  Classes           121           │
│  ⚙️  Functions          489           │
│  🔗 Dependencies       734           │
│  🔴 Circular imports     2           │
│  👻 Orphan modules       5           │
│                                     │
╰─────────────────────────────────────╯

🔥 Most depended-on modules:
  utils.logger          ████████████████ 16
  db.models             ████████████     12
  core.config           ████████          8
```

---

### `depgraph impact <path> <symbol>`

Show exactly what depends on a symbol — directly and transitively. Tells you the full blast radius before you touch anything.

```bash
depgraph impact . payments.processor.PaymentProcessor
```

```
💥 Blast Radius — payments.processor.PaymentProcessor

Total impact: 11 nodes affected (22.9% of project)

🔴 Direct dependents (break immediately):
  → api.views.PaymentView
  → tests.test_payments

🟡 Transitive dependents (break indirectly):
  → api.router
  → main
  ... and 7 more
```

---

### `depgraph cycles <path>`

Detect every circular import chain in the project. Each cycle gets a severity rating (CRITICAL / HIGH / MEDIUM / LOW) and a concrete fix suggestion.

```bash
depgraph cycles ./my_project

# Exit with code 1 if any cycles found — useful in CI
depgraph cycles ./my_project --strict
```

```
🔄 Found 2 circular import(s)

[CRITICAL] Cycle 1 (2 nodes)
  auth.service → db.models → auth.service
  💡 Extract shared logic into a new common.py module

[HIGH] Cycle 2 (4 nodes)
  api.views → orders.handler → payments.processor → api.views
  💡 Use dependency injection or move shared types to interfaces.py
```

---

### `depgraph visualize <path>`

Generate a self-contained interactive HTML graph and open it in your browser. No server needed — it's a single file you can share with your team.

```bash
# Full project graph
depgraph visualize ./my_project

# Pre-highlight the blast radius of a symbol
depgraph visualize ./my_project --highlight payments.processor

# Save to a specific path
depgraph visualize ./my_project --output reports/deps.html

# Generate but don't open the browser
depgraph visualize ./my_project --no-open
```

**What you get in the graph:**

| Feature | Description |
|---|---|
| Folder cluster bubbles | Dashed coloured hulls group nodes by top-level package |
| Click to inspect | A slide-in panel shows blast radius, stats, file path, and dependency lists |
| Search bar | Header search — type to filter nodes, ↑↓ to navigate, Enter to jump |
| Folder filter | Click a folder in the sidebar to isolate it |
| View modes | Full Graph / Circular Imports only / Orphan Modules only |
| Zoom & pan | Mouse wheel + drag, or toolbar buttons |
| Blast radius highlight | Orange = direct dependents, gold = transitive |

**Node colour coding:**

| Colour | Meaning |
|---|---|
| 🔵 Blue | Module (.py file) |
| 🟣 Purple | Class |
| 🩵 Teal | Function |
| 🔴 Red (glowing) | Part of a circular import cycle |
| 🟡 Yellow | Orphan — nothing imports this |
| 🟠 Orange | Blast radius — direct dependent of selected node |

---

### `depgraph orphans <path>`

Find modules, classes, or functions that nothing else imports. These are either dead code or entry points (like `main.py` or `cli.py`).

```
👻 5 orphan(s) found (nothing imports them):

  👻 scripts.migrate_data   (module)   — scripts/migrate_data.py
  👻 utils.old_helpers      (module)   — utils/old_helpers.py
  👻 tests.conftest         (module)   — tests/conftest.py
```

---

### `depgraph deps <path> <symbol>`

Show what a specific symbol depends on — its own imports and all transitive dependencies.

```bash
depgraph deps . payments.processor
```

```
🔗 Dependencies of payments.processor

Direct dependencies:
  → utils.logger
  → db.models

Transitive dependencies:
  → core.config
  → core.base
```

---

## Python API

Use `depgraph` programmatically in your own scripts or tools:

```python
from pathlib import Path
from depgraph.crawler import crawl_project
from depgraph.parser import parse_project
from depgraph.graph import build_graph
from depgraph.analyzer import Analyzer
from depgraph.visualizer import visualize

root = Path("./my_project")

# 1. Build the graph
py_files = crawl_project(str(root))
modules  = parse_project(py_files, root)
graph    = build_graph(modules)

# 2. Analyze
analyzer = Analyzer(graph)

# Blast radius of a symbol
result = analyzer.blast_radius("payments.processor.PaymentProcessor")
print(f"Affects {result.total_impact} nodes ({result.impact_percentage}%)")
print("Direct dependents:",     result.direct_dependents)
print("Transitive dependents:", result.transitive_dependents)

# Find all circular imports
for cycle in analyzer.find_cycles():
    print(f"[{cycle.severity}] {' → '.join(cycle.nodes)}")

# Find orphaned modules
print("Orphans:", analyzer.find_orphans())

# 3. Generate the interactive HTML graph
html_path = visualize(
    graph,
    output_path="my_graph.html",
    cycles=analyzer.find_cycles(),
    orphans=analyzer.find_orphans(),
    project_name="my_project",
)
print("Graph saved to:", html_path)
```

---

## CI/CD Integration

Catch circular imports on every pull request:

```yaml
# .github/workflows/depgraph.yml
name: Dependency Check

on: [push, pull_request]

jobs:
  check-cycles:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install depgraph-py
      - name: Check for circular imports
        run: depgraph cycles . --strict
```

---

## How It Works

`depgraph` does everything through **static analysis** — it never runs your code.

```
Your .py files
      ↓
  AST Parser              ← extracts imports, classes, functions
      ↓                      resolves relative imports (., .., ...)
  NetworkX DiGraph        ← directed graph: A → B means A imports B
      ↓
  Impact Analyzer         ← reverse BFS to compute blast radius
  Cycle Detector          ← Tarjan's SCC algorithm
  Orphan Finder           ← nodes with zero incoming edges
      ↓
  D3.js HTML Graph        ← self-contained interactive visualization
```

---

## Project Structure

```
depgraph/
├── crawler.py       — walks .py files, skips venv / __pycache__
├── parser.py        — AST extraction, resolves relative imports
├── graph.py         — builds the NetworkX directed graph
├── analyzer.py      — blast radius, cycle detection, orphan finding
├── visualizer.py    — generates the D3.js interactive HTML
└── cli.py           — Typer CLI (6 commands)
```

---

## Requirements

- Python 3.8+
- `networkx >= 3.0` — graph engine
- `typer >= 0.9.0` — CLI framework
- `rich >= 13.0.0` — terminal output

The visualizer uses **D3.js 7** via CDN — no extra Python dependencies needed. A corporate-friendly CDN fallback is included automatically.

---

## Development

```bash
git clone https://github.com/yourusername/depgraph
cd depgraph
pip install -e .
pytest tests/ -v
```

---

## License

MIT — free for personal and commercial use.
