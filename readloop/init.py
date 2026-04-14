"""Setup Wizard -- `readloop init` interactive configuration."""
from __future__ import annotations

import os
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


def run_init(console: Console | None = None) -> None:
    """Interactive setup wizard for ReadLoop."""
    if console is None:
        console = Console(force_terminal=True)

    banner = Text()
    banner.append("  ReadLoop Setup Wizard\n", style="bold cyan")
    banner.append("  Configure your environment step by step", style="dim")
    console.print(Panel(banner, border_style="cyan", padding=(0, 1)))
    console.print()

    env_lines: list[str] = []
    env_path = Path.cwd() / ".env"

    # Load existing .env if present
    existing: dict[str, str] = {}
    if env_path.exists():
        console.print(f"[dim]Found existing .env at {env_path}[/]\n")
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                existing[key.strip()] = val.strip().strip('"').strip("'")

    # ── Step 1: LLM provider ──
    console.print("[bold]Step 1: LLM Provider[/]")
    console.print("  1. DeepSeek (recommended, cost-effective)")
    console.print("  2. Claude (Anthropic)")
    console.print("  3. Both (DeepSeek primary + Claude fallback)")
    console.print("  4. Custom OpenAI-compatible endpoint")
    console.print()

    choice = _prompt(console, "Choose provider [1-4]", default="3")

    if choice in ("1", "3", "4"):
        key = _prompt(
            console, "DeepSeek API key",
            default=_mask(existing.get("DEEPSEEK_API_KEY", "")),
            secret=True,
        )
        if key and not key.startswith("***"):
            env_lines.append(f'DEEPSEEK_API_KEY="{key}"')
        elif existing.get("DEEPSEEK_API_KEY"):
            env_lines.append(f'DEEPSEEK_API_KEY="{existing["DEEPSEEK_API_KEY"]}"')

        if choice == "4":
            base = _prompt(
                console, "DeepSeek base URL",
                default=existing.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            )
            env_lines.append(f'DEEPSEEK_BASE_URL="{base}"')
            model = _prompt(
                console, "DeepSeek model name",
                default=existing.get("DEEPSEEK_MODEL", "deepseek-chat"),
            )
            env_lines.append(f'DEEPSEEK_MODEL="{model}"')

    if choice in ("2", "3"):
        key = _prompt(
            console, "Claude API key",
            default=_mask(existing.get("CLAUDE_API_KEY", "")),
            secret=True,
        )
        if key and not key.startswith("***"):
            env_lines.append(f'CLAUDE_API_KEY="{key}"')
        elif existing.get("CLAUDE_API_KEY"):
            env_lines.append(f'CLAUDE_API_KEY="{existing["CLAUDE_API_KEY"]}"')

    console.print()

    # ── Step 2: Paper directories ──
    console.print("[bold]Step 2: Paper Directories[/]")
    console.print("  Where are your PDF papers stored?")
    console.print()

    default_ref1 = existing.get("REFERENCE_DIR_1", str(Path.cwd() / "papers"))
    ref1 = _prompt(console, "Primary paper directory", default=default_ref1)
    env_lines.append(f'REFERENCE_DIR_1="{ref1}"')

    ref1_path = Path(ref1)
    if not ref1_path.exists():
        create = _prompt(console, f"  Directory doesn't exist. Create it? [y/n]", default="y")
        if create.lower() in ("y", "yes"):
            ref1_path.mkdir(parents=True, exist_ok=True)
            console.print(f"  [green]Created: {ref1_path}[/]")

    ref2 = _prompt(console, "Secondary paper directory (optional, Enter to skip)", default="")
    if ref2:
        env_lines.append(f'REFERENCE_DIR_2="{ref2}"')

    console.print()

    # ── Step 3: Output directory ──
    console.print("[bold]Step 3: Output Directory[/]")
    default_output = existing.get("OUTPUT_DIR", str(Path.cwd() / "output"))
    output = _prompt(console, "Output directory", default=default_output)
    env_lines.append(f'OUTPUT_DIR="{output}"')

    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)

    console.print()

    # ── Step 4: Verify connectivity ──
    console.print("[bold]Step 4: Verify LLM Connectivity[/]")
    verify = _prompt(console, "Test API connection now? [y/n]", default="y")

    if verify.lower() in ("y", "yes"):
        _verify_connectivity(console, env_lines)

    console.print()

    # ── Step 5: Check embedding model ──
    console.print("[bold]Step 5: Embedding Model[/]")
    try:
        from sentence_transformers import SentenceTransformer
        console.print("  [green]sentence-transformers already installed[/]")
        console.print("  [dim]Checking model availability...[/]")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        console.print("  [green]all-MiniLM-L6-v2 ready[/]")
    except ImportError:
        console.print("  [yellow]sentence-transformers not installed[/]")
        console.print("  [dim]Run: pip install sentence-transformers[/]")
    except Exception as e:
        console.print(f"  [yellow]Model check failed: {e}[/]")

    console.print()

    # ── Save .env ──
    if env_lines:
        console.print("[bold]Saving configuration...[/]")

        # Preserve existing lines not being overwritten
        new_keys = set()
        for line in env_lines:
            key = line.split("=", 1)[0]
            new_keys.add(key)

        final_lines: list[str] = []

        # Keep existing entries that aren't being replaced
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    key = stripped.split("=", 1)[0].strip()
                    if key in new_keys:
                        continue
                final_lines.append(line)

        # Add new/updated entries
        if final_lines and final_lines[-1].strip():
            final_lines.append("")
        final_lines.extend(env_lines)

        env_path.write_text("\n".join(final_lines) + "\n", encoding="utf-8")
        console.print(f"  [green]Saved: {env_path}[/]")
    else:
        console.print("[yellow]No configuration to save[/]")

    console.print()
    console.print(
        Panel(
            "[bold green]Setup complete![/]\n\n"
            "  Run [bold cyan]readloop[/] to start the interactive CLI\n"
            "  Run [bold cyan]readloop --list[/] to see available papers",
            border_style="green",
        )
    )


def _prompt(console: Console, label: str, default: str = "", secret: bool = False) -> str:
    """Prompt user for input with optional default."""
    if default:
        hint = f" [{_mask(default)}]" if secret else f" [{default}]"
        try:
            value = input(f"  {label}{hint}: ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Cancelled[/]")
            raise SystemExit(0)
        return value if value else default
    else:
        try:
            value = input(f"  {label}: ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Cancelled[/]")
            raise SystemExit(0)
        return value


def _mask(value: str) -> str:
    """Mask an API key for display."""
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return value[:4] + "***" + value[-4:]


def _verify_connectivity(console: Console, env_lines: list[str]) -> None:
    """Quick connectivity test using configured API keys."""
    # Parse keys from env_lines
    keys: dict[str, str] = {}
    for line in env_lines:
        k, _, v = line.partition("=")
        keys[k.strip()] = v.strip().strip('"')

    deepseek_key = keys.get("DEEPSEEK_API_KEY", "")
    claude_key = keys.get("CLAUDE_API_KEY", "")

    if deepseek_key:
        console.print("  [dim]Testing DeepSeek...[/]", end="")
        try:
            from openai import OpenAI
            import httpx
            client = OpenAI(
                api_key=deepseek_key,
                base_url=keys.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                http_client=httpx.Client(timeout=30.0),
            )
            resp = client.chat.completions.create(
                model=keys.get("DEEPSEEK_MODEL", "deepseek-chat"),
                messages=[{"role": "user", "content": "Reply with just 'ok'"}],
                max_tokens=5,
            )
            if resp.choices:
                console.print(" [green]OK[/]")
            else:
                console.print(" [yellow]No response[/]")
        except Exception as e:
            console.print(f" [red]Failed: {e}[/]")

    if claude_key:
        console.print("  [dim]Testing Claude...[/]", end="")
        try:
            from openai import OpenAI
            import httpx
            client = OpenAI(
                api_key=claude_key,
                base_url=keys.get("CLAUDE_BASE_URL", "https://api.ccodezh.com/v1"),
                http_client=httpx.Client(timeout=30.0),
            )
            resp = client.chat.completions.create(
                model=keys.get("CLAUDE_MODEL", "claude-sonnet-4-6-n"),
                messages=[{"role": "user", "content": "Reply with just 'ok'"}],
                max_tokens=5,
            )
            if resp.choices:
                console.print(" [green]OK[/]")
            else:
                console.print(" [yellow]No response[/]")
        except Exception as e:
            console.print(f" [red]Failed: {e}[/]")
