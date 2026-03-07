"""
cli.py — Command-line interface for depgraph using Typer + Rich.

Commands:
    depgraph scan      <path>              — Scan & summarize a project
    depgraph impact    <path> <symbol>     — Blast radius of a symbol
    depgraph cycles    <path>              — Detect circular imports
    depgraph orphans   <path>              — Find unused modules
    depgraph deps      <path> <symbol>     — What does a symbol depend on?
    depgraph visualize <path>              — Open interactive graph in browser
"""

import sys
import webbrowser
import tempfile
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.text import Text

from depgraph.crawler import crawl_project
from depgraph.parser import parse_project
from depgraph.graph import build_graph, get_summary
from depgraph.analyzer import Analyzer
from depgraph.visualizer import visualize


app = typer.Typer(
    name="depgraph",
    help="🔍 Interactive Python dependency graph & blast-radius analyzer",
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()


# ── Shared helper ──────────────────────────────────────────────────────────────

def _load(project_path: str):
    """Crawl, parse, and build graph. Returns (graph, modules, summary)."""
    root = Path(project_path).resolve()

    with console.status(f"[bold cyan]Scanning {root}...[/]"):
        py_files = crawl_project(str(root))
        if not py_files:
            console.print("[red]No Python files found.[/red]")
            raise typer.Exit(1)
        modules = parse_project(py_files, root)
        graph   = build_graph(modules)
        summary = get_summary(graph, modules)

    return graph, modules, summary, root


# ── Commands ───────────────────────────────────────────────────────────────────

@app.command()
def scan(
    project_path: str = typer.Argument(".", help="Path to your Python project"),
):
    """
    📊 Scan a project and show a full dependency summary.
    """
    graph, modules, summary, root = _load(project_path)
    analyzer = Analyzer(graph)

    # Header
    console.print(Panel.fit(
        f"[bold cyan]depgraph[/bold cyan] — [white]{root}[/white]",
        border_style="cyan"
    ))

    # Summary table
    table = Table(box=box.ROUNDED, show_header=False, border_style="cyan")
    table.add_column("Metric", style="bold white")
    table.add_column("Value",  style="cyan")

    table.add_row("📁 Python files",    str(summary["total_files"]))
    table.add_row("📦 Modules",         str(summary["total_modules"]))
    table.add_row("🏛️  Classes",         str(summary["total_classes"]))
    table.add_row("⚙️  Functions",        str(summary["total_functions"]))
    table.add_row("🔗 Dependencies",    str(summary["total_edges"]))

    cycles  = analyzer.find_cycles()
    orphans = analyzer.find_orphans()
    cycle_count  = len(cycles)
    orphan_count = len(orphans)

    cycle_txt  = f"[red]{cycle_count}[/red]"  if cycle_count  else "[green]0[/green]"
    orphan_txt = f"[yellow]{orphan_count}[/yellow]" if orphan_count else "[green]0[/green]"

    table.add_row("🔴 Circular imports", cycle_txt)
    table.add_row("👻 Orphan modules",   orphan_txt)

    console.print(table)

    # Errors
    if summary["parse_errors"]:
        console.print(f"\n[yellow]⚠️  {len(summary['parse_errors'])} file(s) had parse errors:[/yellow]")
        for err in summary["parse_errors"][:5]:
            console.print(f"  • [dim]{err['module']}[/dim]: {err['errors'][0]}")

    # Hot spots
    hot = analyzer.most_depended_on(top_n=5)
    if hot:
        console.print("\n[bold]🔥 Most depended-on modules:[/bold]")
        for node, count in hot:
            bar = "█" * min(count, 20)
            console.print(f"  [cyan]{node:<45}[/cyan] [white]{bar}[/white] {count}")

    console.print(
        "\n[dim]Run [bold]depgraph visualize .[/bold] to open the interactive graph.[/dim]"
    )


# ──────────────────────────────────────────────────────────────────────────────

@app.command()
def impact(
    project_path: str = typer.Argument(".", help="Path to your Python project"),
    symbol: str       = typer.Argument(..., help="Module, class, or function to analyze"),
):
    """
    💥 Show the blast radius — what breaks if a symbol is removed.
    """
    graph, modules, summary, root = _load(project_path)
    analyzer = Analyzer(graph)

    try:
        result = analyzer.blast_radius(symbol)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    console.print(Panel.fit(
        f"[bold red]💥 Blast Radius[/bold red] — [white]{symbol}[/white]",
        border_style="red"
    ))

    console.print(f"\n[bold]Total impact:[/bold] "
                  f"[red]{result.total_impact}[/red] node(s) affected "
                  f"([red]{result.impact_percentage}%[/red] of project)\n")

    if result.direct_dependents:
        console.print("[bold orange1]🔴 Direct dependents (break immediately):[/bold orange1]")
        for dep in result.direct_dependents:
            console.print(f"  → [orange1]{dep}[/orange1]")

    if result.transitive_dependents:
        console.print("\n[bold yellow]🟡 Transitive dependents (break indirectly):[/bold yellow]")
        for dep in result.transitive_dependents[:20]:
            console.print(f"  → [yellow]{dep}[/yellow]")
        if len(result.transitive_dependents) > 20:
            console.print(f"  [dim]... and {len(result.transitive_dependents) - 20} more[/dim]")

    if not result.direct_dependents and not result.transitive_dependents:
        console.print("[green]✅ Nothing depends on this symbol — safe to remove![/green]")

    # Offer visualization
    console.print(
        f"\n[dim]Run [bold]depgraph visualize . --highlight {symbol}[/bold] "
        f"to see this in the interactive graph.[/dim]"
    )


# ──────────────────────────────────────────────────────────────────────────────

@app.command()
def cycles(
    project_path: str = typer.Argument(".", help="Path to your Python project"),
    strict: bool = typer.Option(False, "--strict", help="Exit with code 1 if cycles found"),
):
    """
    🔄 Detect all circular imports in the project.
    """
    graph, modules, summary, root = _load(project_path)
    analyzer = Analyzer(graph)
    found = analyzer.find_cycles()

    console.print(Panel.fit(
        "[bold red]🔄 Circular Import Analysis[/bold red]",
        border_style="red"
    ))

    if not found:
        console.print("[green]✅ No circular imports found! Your project is clean.[/green]")
        return

    console.print(f"[red]Found {len(found)} circular import(s):[/red]\n")

    severity_color = {
        "CRITICAL": "red",
        "HIGH":     "orange1",
        "MEDIUM":   "yellow",
        "LOW":      "dim",
    }

    for i, cycle in enumerate(found, 1):
        color = severity_color.get(cycle.severity, "white")
        chain = " → ".join(cycle.nodes) + f" → {cycle.nodes[0]}"

        console.print(
            f"[{color}][{cycle.severity}][/{color}] "
            f"Cycle {i} ({cycle.length} nodes)"
        )
        console.print(f"  [white]{chain}[/white]")
        console.print(f"  [dim]💡 {cycle.suggestion}[/dim]\n")

    if strict:
        raise typer.Exit(1)


# ──────────────────────────────────────────────────────────────────────────────

@app.command()
def orphans(
    project_path: str = typer.Argument(".", help="Path to your Python project"),
):
    """
    👻 Find modules that nothing depends on (potential dead code or entry points).
    """
    graph, modules, summary, root = _load(project_path)
    analyzer = Analyzer(graph)
    found = analyzer.find_orphans()

    console.print(Panel.fit(
        "[bold yellow]👻 Orphan Module Analysis[/bold yellow]",
        border_style="yellow"
    ))

    if not found:
        console.print("[green]✅ No orphan modules found![/green]")
        return

    console.print(f"[yellow]{len(found)} orphan(s) found[/yellow] "
                  f"[dim](nothing imports them):[/dim]\n")

    for node in found:
        node_type = graph.nodes[node].get("type", "module")
        filepath  = graph.nodes[node].get("filepath", "")
        console.print(f"  [yellow]👻[/yellow] [white]{node}[/white] "
                      f"[dim]({node_type}) — {filepath}[/dim]")

    console.print(
        "\n[dim]These may be entry points (main.py, cli.py) or unused dead code.[/dim]"
    )


# ──────────────────────────────────────────────────────────────────────────────

@app.command()
def deps(
    project_path: str = typer.Argument(".", help="Path to your Python project"),
    symbol: str       = typer.Argument(..., help="Module, class, or function to inspect"),
):
    """
    🔗 Show what a symbol depends on (its own imports and usages).
    """
    graph, modules, summary, root = _load(project_path)
    analyzer = Analyzer(graph)

    try:
        result = analyzer.dependencies_of(symbol)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    console.print(Panel.fit(
        f"[bold cyan]🔗 Dependencies of[/bold cyan] [white]{symbol}[/white]",
        border_style="cyan"
    ))

    if result["direct"]:
        console.print("\n[bold cyan]Direct dependencies:[/bold cyan]")
        for dep in result["direct"]:
            console.print(f"  → [cyan]{dep}[/cyan]")

    if result["transitive"]:
        console.print("\n[bold dim]Transitive dependencies:[/bold dim]")
        for dep in result["transitive"][:20]:
            console.print(f"  → [dim]{dep}[/dim]")
        if len(result["transitive"]) > 20:
            console.print(f"  [dim]... and {len(result['transitive']) - 20} more[/dim]")

    if not result["direct"] and not result["transitive"]:
        console.print("[green]✅ This symbol has no internal dependencies.[/green]")


# ──────────────────────────────────────────────────────────────────────────────

@app.command()
def visualize_cmd(
    project_path: str = typer.Argument(".", help="Path to your Python project"),
    highlight: Optional[str] = typer.Option(None, "--highlight", "-h",
                                             help="Highlight blast radius of this symbol"),
    output: str = typer.Option("depgraph.html", "--output", "-o",
                                help="Output HTML file path"),
    no_open: bool = typer.Option(False, "--no-open", help="Don't open in browser"),
):
    """
    🌐 Generate and open the interactive dependency graph in your browser.
    """
    graph, modules, summary, root = _load(project_path)
    analyzer = Analyzer(graph)

    cycles_list = analyzer.find_cycles()
    orphans_list = analyzer.find_orphans()

    # Blast radius if highlight requested
    blast_direct = blast_transitive = None
    if highlight:
        try:
            br = analyzer.blast_radius(highlight)
            blast_direct = br.direct_dependents
            blast_transitive = br.transitive_dependents
        except ValueError as e:
            console.print(f"[yellow]Warning:[/yellow] {e}")
            highlight = None

    with console.status("[cyan]Generating interactive graph...[/cyan]"):
        html_path = visualize(
            graph=graph,
            output_path=output,
            cycles=cycles_list,
            orphans=orphans_list,
            blast_target=highlight,
            blast_direct=blast_direct,
            blast_transitive=blast_transitive,
        )

    console.print(f"[green]✅ Graph saved to:[/green] [white]{html_path}[/white]")

    if not no_open:
        webbrowser.open(f"file://{html_path}")
        console.print("[dim]Opened in your default browser.[/dim]")

    # Print legend
    console.print("\n[bold]Legend:[/bold]")
    console.print("  [blue]● Blue[/blue]   = Module")
    console.print("  [purple]● Purple[/purple] = Class")
    console.print("  [cyan]● Teal[/cyan]   = Function")
    console.print("  [red]● Red[/red]    = In a cycle")
    console.print("  [yellow]● Yellow[/yellow] = Orphan (nothing imports it)")
    if highlight:
        console.print(f"  [red]★ Star[/red]   = Blast target: {highlight}")
        console.print("  [orange1]◆ Orange[/orange1] = Direct dependents")
        console.print("  [yellow]● Gold[/yellow]  = Transitive dependents")


# Register visualize_cmd as `depgraph visualize`
app.command(name="visualize")(visualize_cmd)


# ──────────────────────────────────────────────────────────────────────────────

def main():
    app()


if __name__ == "__main__":
    main()