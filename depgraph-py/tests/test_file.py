# save this as test_manual.py inside the depgraph/ folder

from pathlib import Path
from depgraph.crawler import crawl_project
from depgraph.parser import parse_project
from depgraph.graph import build_graph, get_summary
from depgraph.analyzer import Analyzer

# Point it at itself — test depgraph ON depgraph!
root = Path(".")

# Step 1 — crawl
files = crawl_project(str(root))
print(f"✅ Files found: {len(files)}")
for f in files:
    print(f"   → {f}")

# Step 2 — parse
modules = parse_project(files, root)
print(f"\n✅ Modules parsed: {len(modules)}")
for m in modules:
    print(f"   → {m.module_name} | classes: {m.classes} | imports: {m.imports}")

# Step 3 — build graph
G = build_graph(modules)
print(f"\n✅ Graph built")
print(f"   Nodes : {G.number_of_nodes()}")
print(f"   Edges : {G.number_of_edges()}")

# Step 4 — analyze
analyzer = Analyzer(G)

cycles = analyzer.find_cycles()
print(f"\n✅ Cycles found: {len(cycles)}")
for c in cycles:
    print(f"   [{c.severity}] {' → '.join(c.nodes)}")

orphans = analyzer.find_orphans()
print(f"\n✅ Orphans found: {len(orphans)}")
for o in orphans:
    print(f"   → {o}")

most_used = analyzer.most_depended_on(top_n=3)
print(f"\n✅ Most depended-on:")
for node, count in most_used:
    print(f"   → {node} ({count} dependents)")

print("\n🎉 All core logic working!")