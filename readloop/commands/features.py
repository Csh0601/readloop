"""Feature commands (literature review, concept tracking, proposals)."""
from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown

from ..client import LLMClient


def cmd_review(console: Console, client: LLMClient, topic: str) -> None:
    """Generate a literature review on a topic."""
    console.print(f"[bold]Generating review: {topic}[/]")
    from ..features.review import generate_review

    path = generate_review(topic, client)
    content = path.read_text(encoding="utf-8")
    console.print(Markdown(content[:3000]))
    if len(content) > 3000:
        console.print("[dim]... truncated[/]")
    console.print(f"\n[green]Saved: {path}[/]")


def cmd_track_concept(console: Console, client: LLMClient, concept: str) -> None:
    """Track concept evolution across papers."""
    console.print(f"[bold]Tracking: {concept}[/]")
    from ..features.evolution import track_concept

    try:
        path = track_concept(concept, client)
        content = path.read_text(encoding="utf-8")
        console.print(Markdown(content[:2000]))
        console.print(f"\n[green]Saved: {path}[/]")
    except ValueError as e:
        console.print(f"[red]{e}[/]")


def cmd_propose(console: Console, client: LLMClient, topic: str | None = None) -> None:
    """Generate research proposals."""
    console.print("[bold]Generating research proposals...[/]")
    from ..features.proposals import generate_proposals

    path = generate_proposals(client, topic)
    content = path.read_text(encoding="utf-8")
    console.print(Markdown(content[:3000]))
    if len(content) > 3000:
        console.print("[dim]... truncated[/]")
    console.print(f"\n[green]Saved: {path}[/]")
