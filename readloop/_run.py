"""ReadLoop v2 -- Script mode (argparse).

Interactive mode (recommended):
    readloop                                      # Launch interactive CLI

Script mode (for automation):
    readloop --list                               # List available papers
    readloop --single "A-MEM"                     # Analyze single paper
    readloop --build-graph                        # Build knowledge graph
    readloop --ask "query"                        # Semantic search + LLM answer
    readloop --help                               # Show all script options
"""
import argparse
import sys

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from rich.console import Console

from readloop.config import OUTPUT_DIR

console = Console(force_terminal=True)


def main():
    parser = argparse.ArgumentParser(description="ReadLoop v2")

    # Setup
    parser.add_argument("--init", action="store_true", help="Run interactive setup wizard")

    # Analysis
    parser.add_argument("--single", type=str, help="Analyze single paper (keyword)")
    parser.add_argument("--source", choices=["ref", "agent"])
    parser.add_argument("--cat", choices=["A", "B", "C"])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--cross-only", action="store_true")
    parser.add_argument("--list", action="store_true")

    # Knowledge Graph
    parser.add_argument("--build-graph", action="store_true", help="Build knowledge graph")
    parser.add_argument("--show-graph", action="store_true", help="Show graph stats")
    parser.add_argument("--viz-graph", action="store_true", help="Open interactive graph")
    parser.add_argument("--gaps", action="store_true", help="Find research gaps")
    parser.add_argument("--cluster", action="store_true", help="Run community detection")
    parser.add_argument("--analyze-graph", action="store_true", help="God nodes + surprises")
    parser.add_argument("--questions", action="store_true", help="Generate research questions")

    # Export
    parser.add_argument("--export-wiki", type=str, metavar="DIR", help="Export Obsidian wiki")
    parser.add_argument("--export-graphml", type=str, metavar="FILE", help="Export GraphML")

    # Memory
    parser.add_argument("--build-memory", action="store_true", help="Build memory store")
    parser.add_argument("--ask", type=str, help="Query the knowledge base")
    parser.add_argument("--memory-stats", action="store_true")

    # Features
    parser.add_argument("--review", type=str, help="Generate literature review on topic")
    parser.add_argument("--track-concept", type=str, help="Track concept evolution")
    parser.add_argument("--propose", action="store_true", help="Generate research proposals")
    parser.add_argument("--topic", type=str, help="Topic for proposals")

    args = parser.parse_args()

    # --- Setup wizard ---
    if args.init:
        from readloop.init import run_init
        run_init(console)
        return

    # --- List papers (no LLM needed) ---
    if args.list:
        from readloop.commands.papers import list_papers
        list_papers(console, args.source, args.cat)
        return

    # --- Knowledge Graph commands ---
    if args.build_graph:
        from readloop.commands.graph import cmd_build_graph
        cmd_build_graph(console, _client())
        return

    if args.show_graph:
        from readloop.commands.graph import cmd_show_graph
        cmd_show_graph(console)
        return

    if args.viz_graph:
        from readloop.commands.graph import cmd_viz_graph
        cmd_viz_graph(console)
        return

    if args.gaps:
        from readloop.commands.graph import cmd_gaps
        cmd_gaps(console, _client())
        return

    if args.cluster:
        from readloop.commands.graph import cmd_cluster
        cmd_cluster(console)
        return

    if args.analyze_graph:
        from readloop.commands.graph import cmd_analyze_graph
        cmd_analyze_graph(console)
        return

    if args.questions:
        from readloop.commands.graph import cmd_questions
        cmd_questions(console)
        return

    if args.export_wiki:
        from readloop.commands.export import cmd_export_wiki
        cmd_export_wiki(console, args.export_wiki)
        return

    if args.export_graphml:
        from readloop.commands.export import cmd_export_graphml
        cmd_export_graphml(console, args.export_graphml)
        return

    # --- Memory commands ---
    if args.build_memory:
        from readloop.commands.memory import cmd_build_memory
        cmd_build_memory(console, _client())
        return

    if args.ask:
        from readloop.commands.memory import cmd_ask
        cmd_ask(console, _client(), args.ask)
        return

    if args.memory_stats:
        from readloop.commands.memory import cmd_memory_stats
        cmd_memory_stats(console)
        return

    # --- Feature commands ---
    if args.review:
        from readloop.commands.features import cmd_review
        cmd_review(console, _client(), args.review)
        return

    if args.track_concept:
        from readloop.commands.features import cmd_track_concept
        cmd_track_concept(console, _client(), args.track_concept)
        return

    if args.propose:
        from readloop.commands.features import cmd_propose
        cmd_propose(console, _client(), args.topic)
        return

    # --- No script args: launch interactive mode ---
    if not any([args.single, args.source, args.all, args.cross_only]):
        from readloop.cli import run_interactive
        run_interactive()
        return

    # --- Analysis commands (script mode) ---
    console.print("[bold]ReadLoop v2[/]")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = _client()

    if args.single:
        from readloop.commands.analysis import cmd_analyze
        cmd_analyze(console, client, args.single)

    elif args.cross_only:
        from readloop.commands.analysis import cmd_cross
        cmd_cross(console, client)

    else:
        from readloop.commands.analysis import cmd_batch
        cmd_batch(console, client, args.source, args.cat)


_cached_client = None


def _client():
    """Lazy cached LLM client construction."""
    global _cached_client
    if _cached_client is None:
        from readloop.client import LLMClient
        _cached_client = LLMClient()
    return _cached_client


if __name__ == "__main__":
    main()
