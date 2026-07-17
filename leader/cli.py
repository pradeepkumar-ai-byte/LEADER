"""
Leader – CLI

Usage:
  leader run "your task"
  leader run "your task" --category coding --parallel
  leader serve                     # start REST API server
  leader serve --port 9000         # custom port
  leader backends
  leader stats
  leader init
  leader feedback <task_id> <1-5>
  leader ping                      # health-check all connected backends
  leader vscode-extension           # generate VS Code extension
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import aiohttp
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import config as cfg_module
from .auditor import AutonomousAuditor
from .executor import Executor
from .file_utils import latest_snapshot, restore_snapshot
from .logger import TaskLogger
from .models import Task, TaskCategory
from .registry import Registry
from .router import Router

console = Console()


def build_context() -> tuple[Registry, TaskLogger, Router, Executor]:
    registry = Registry()
    warnings = cfg_module.load(registry)
    for w in warnings:
        console.print(f"[yellow]⚠ Config warning:[/] {w}")
    logger = TaskLogger()
    router = Router(registry, logger)
    executor = Executor(registry)
    return registry, logger, router, executor


# ── commands ─────────────────────────────────────────────────────────────────


def cmd_run(args):
    prompt = " ".join(args.prompt)
    category = TaskCategory(args.category) if args.category else None
    parallel = getattr(args, "parallel", False)
    task = Task(prompt=prompt, category=category)

    registry, logger, router, executor = build_context()

    console.print("\n[bold cyan]Leader[/] routing task…")
    decision = router.decide(task)

    console.print(f"  [dim]Category :[/] {task.category.value if task.category else 'unknown'}")
    console.print(f"  [dim]Backend  :[/] [green]{decision.primary}[/]")
    if decision.fallback_chain:
        console.print(f"  [dim]Fallbacks:[/] {', '.join(decision.fallback_chain)}")
    if parallel and len(decision.fallback_chain) > 0:
        console.print("  [dim]Mode     :[/] [magenta]parallel[/] (fastest result wins)")
    console.print(f"  [dim]Reason   :[/] {decision.rationale}\n")

    logger.log_dispatch(task, decision)
    result = asyncio.run(executor.run(task, decision, parallel=parallel))
    logger.log_result(result)

    if result.success:
        console.print(
            Panel(
                result.output,
                title=f"[green]Result from {result.backend_id}[/]",
                expand=False,
            )
        )
        cost_str = f"  ~${result.cost_estimate:.5f}" if result.cost_estimate else ""
        console.print(f"  [dim]Latency: {result.latency_ms:.0f}ms{cost_str}[/]\n")
    else:
        console.print(f"[red]✗ Task failed:[/] {result.error}\n")

    if decision.recommendation:
        console.print(f"[yellow]💡[/] {decision.recommendation}\n")

    console.print(f"[dim]Task ID: {task.task_id}  |  Rate: leader feedback {task.task_id} <1-5>[/]")


def cmd_backends(args):
    registry, *_ = build_context()
    table = Table(title="Leader – backends", show_lines=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name")
    table.add_column("Status", justify="center")
    table.add_column("Strengths")
    table.add_column("Notes", style="dim")

    for spec in registry.all():
        if spec.connected:
            status = "[green]● connected[/]"
        else:
            status = "[dim]○ not connected[/]"
        strengths = ", ".join(s.value for s in spec.strengths)
        notes = spec.homepage if spec.homepage else spec.description[:50]
        table.add_row(spec.id, spec.display_name, status, strengths, notes)

    console.print(table)
    console.print("\n  Edit [bold]~/.leader/config.yaml[/] to connect backends.\n")


async def _ping_all(registry: Registry):
    connected = registry.connected()
    if not connected:
        console.print("[dim]No backends connected.[/]")
        return
    console.print("\n[bold]Pinging connected backends…[/]\n")
    for spec in connected:
        if spec.id == "direct_llm":
            console.print(f"  [green]✓[/] {spec.display_name}  [dim](API — no ping needed)[/]")
            continue
        url = spec.config.get("base_url", "")
        if not url:
            console.print(f"  [yellow]?[/] {spec.display_name}  [dim](no base_url to ping)[/]")
            continue
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                    if r.status < 500:
                        console.print(f"  [green]✓[/] {spec.display_name}  [dim]HTTP {r.status}[/]")
                    else:
                        console.print(f"  [red]✗[/] {spec.display_name}  [dim]HTTP {r.status}[/]")
        except Exception as e:
            console.print(f"  [red]✗[/] {spec.display_name}  [dim]{e}[/]")


def cmd_ping(args):
    registry, *_ = build_context()
    asyncio.run(_ping_all(registry))


def cmd_stats(args):
    _, logger, *_ = build_context()
    win_rates = logger.win_rates()
    latencies = logger.avg_latency()

    if not win_rates:
        console.print("[dim]No task history yet. Run some tasks first.[/]")
        return

    table = Table(title="Leader – routing stats (evolved scores)", show_lines=True)
    table.add_column("Backend", style="cyan")
    table.add_column("Category")
    table.add_column("Win rate", justify="right")
    table.add_column("Avg latency", justify="right")

    for backend_id, categories in sorted(win_rates.items()):
        for cat, rate in sorted(categories.items()):
            lat = latencies.get(backend_id)
            lat_s = f"{lat:.0f}ms" if lat else "–"
            colour = "green" if rate >= 0.7 else ("yellow" if rate >= 0.4 else "red")
            table.add_row(
                backend_id,
                cat,
                f"[{colour}]{rate*100:.0f}%[/]",
                lat_s,
            )
    console.print(table)


def cmd_feedback(args):
    _, logger, *_ = build_context()
    try:
        rating = int(args.rating)
        assert 1 <= rating <= 5
    except Exception:
        console.print("[red]Rating must be 1–5[/]")
        sys.exit(1)
    logger.log_feedback(args.task_id, rating)
    console.print(f"[green]✓ Feedback recorded for {args.task_id}[/]")


def cmd_init(args):
    cfg_module.scaffold()


def cmd_serve(args):
    """Start the Leader REST API server."""
    from .server import run_server

    host = getattr(args, "host", "127.0.0.1")
    port = getattr(args, "port", 8585)
    config = getattr(args, "config", None)

    console.print(
        Panel(
            f"[bold cyan]Leader API Server[/]\n\n"
            f"  Host: {host}\n"
            f"  Port: {port}\n\n"
            f"  Any tool can now call Leader over HTTP.\n"
            f"  [dim]Ctrl+C to stop.[/]",
            title="⚡ Starting Leader Server",
            expand=False,
        )
    )
    run_server(host=host, port=port, config_path=config)


def cmd_vscode_extension(args):
    """Generate VS Code extension scaffold."""
    from .plugins.vscode import VSCodePlugin

    output = getattr(args, "output", "./leader-vscode")
    server_url = getattr(args, "server_url", "http://127.0.0.1:8585")

    plugin = VSCodePlugin(server_url=server_url)
    plugin.generate_extension(output)
    console.print(f"\n[green]✓ VS Code extension generated at {output}[/]")
    console.print("  [dim]Make sure Leader server is running: leader serve[/]\n")


# ── entry point ───────────────────────────────────────────────────────────────


def cmd_review(args):
    target = getattr(args, "path", ".")
    auto_approve = getattr(args, "auto_approve", False)
    registry, logger, _, executor = build_context()
    auditor = AutonomousAuditor(registry, logger, executor)
    asyncio.run(auditor.audit_and_fix(target, max_issues=15, auto_approve=auto_approve))


def cmd_restore(args):
    target = getattr(args, "path", ".")
    snapshot = getattr(args, "snapshot", None)

    if snapshot:
        restored = restore_snapshot(snapshot, root_path=target)
        console.print(f"[green]✓ Restored {restored} files from snapshot {snapshot}[/]")
        return

    latest = latest_snapshot(target)
    if latest is None:
        console.print("[red]No snapshot found to restore.[/]")
        return

    restored = restore_snapshot(latest, root_path=target)
    console.print(f"[green]✓ Restored {restored} files from latest snapshot {latest}[/]")


def main():
    parser = argparse.ArgumentParser(
        prog="leader",
        description="Leader — headless router that dispatches tasks to the best available AI agent backend",
    )
    sub = parser.add_subparsers(dest="command")

    # run
    p_run = sub.add_parser("run", help="Run a task")
    p_run.add_argument("prompt", nargs="+")
    p_run.add_argument("--category", choices=[c.value for c in TaskCategory], default=None)
    p_run.add_argument(
        "--parallel",
        action="store_true",
        help="Run multiple backends simultaneously, use fastest success",
    )

    # serve
    p_serve = sub.add_parser("serve", help="Start the Leader REST API server")
    p_serve.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    p_serve.add_argument("--port", type=int, default=8585, help="Port to listen on (default: 8585)")
    p_serve.add_argument("--config", default=None, help="Path to config file")

    # backends, ping, stats, init
    sub.add_parser("backends", help="List all known backends and connection status")
    sub.add_parser("ping", help="Health-check all connected backends")
    sub.add_parser("stats", help="Show routing history and evolved scores")
    sub.add_parser("init", help="Create ~/.leader/config.yaml")

    # feedback
    p_fb = sub.add_parser("feedback", help="Rate a result (helps router learn)")
    p_fb.add_argument("task_id")
    p_fb.add_argument("rating", help="1 (bad) to 5 (great)")

    # vscode-extension
    p_vsc = sub.add_parser("vscode-extension", help="Generate VS Code / Cursor extension")
    p_vsc.add_argument("--output", default="./leader-vscode", help="Output directory")
    p_vsc.add_argument("--server-url", default="http://127.0.0.1:8585", help="Leader server URL")

    # review
    p_review = sub.add_parser("review", help="Autonomous multi-agent code audit and auto-fix")
    p_review.add_argument("path", nargs="?", default=".", help="Directory to audit (default: ./)")
    p_review.add_argument(
        "--auto-approve", action="store_true", help="Apply fixes without prompting for confirmation"
    )

    # restore
    p_restore = sub.add_parser(
        "restore", help="Restore files from the latest or specified snapshot"
    )
    p_restore.add_argument("path", nargs="?", default=".", help="Project root (default: ./)")
    p_restore.add_argument("--snapshot", default=None, help="Snapshot directory to restore from")

    args = parser.parse_args()
    dispatch = {
        "run": cmd_run,
        "backends": cmd_backends,
        "ping": cmd_ping,
        "stats": cmd_stats,
        "feedback": cmd_feedback,
        "init": cmd_init,
        "serve": cmd_serve,
        "vscode-extension": cmd_vscode_extension,
        "review": cmd_review,
        "restore": cmd_restore,
    }
    if args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
