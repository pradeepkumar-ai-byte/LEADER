"""
Leader - Autonomous Auditor and Auto-Fixer
"""

from __future__ import annotations

import asyncio
import difflib
import json
import re
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm
from rich.syntax import Syntax
from rich.table import Table

from .executor import Executor
from .file_utils import create_snapshot, gather_codebase
from .logger import TaskLogger
from .models import RouteDecision, Task, TaskCategory, TaskResult
from .registry import Registry

console = Console()


class AutonomousAuditor:
    def __init__(self, registry: Registry, logger: TaskLogger, executor: Executor):
        self.registry = registry
        self.logger = logger
        self.executor = executor

    async def audit_and_fix(
        self, target_path: str, max_issues: int = 15, auto_approve: bool = False
    ):
        root = Path(target_path).resolve()
        console.print("\n[bold cyan]Leader Autonomous Auditor[/]")
        console.print(f"[dim]Gathering codebase from {root}...[/]")

        try:
            codebase_text = gather_codebase(root)
        except Exception as e:
            console.print(f"[red]Error reading directory:[/] {e}")
            return

        if not codebase_text:
            console.print("[red]No source code found in the directory.[/]")
            return

        coding_backends = [
            s for s in self.registry.connected() if TaskCategory.CODING in s.strengths
        ]

        if not coding_backends:
            console.print("[red]No connected CODING backends available for audit.[/]")
            return

        # Select up to 3 backends for the audit
        auditors = coding_backends[:3]
        auditor_names = [b.display_name for b in auditors]
        console.print(
            f"[dim]Dispatching audit to {len(auditors)} agents: {', '.join(auditor_names)}[/]"
        )

        audit_prompt = f"""
You are an expert security and code quality auditor. Review the following codebase.
Identify the most critical bugs, security vulnerabilities, or severe logic flaws.
Ignore trivial style issues.

Return a JSON array of up to {max_issues} objects. Do NOT include markdown blocks outside the JSON.
Each object must have exactly these keys:
- "file": The relative path to the file.
- "problem": A short description of the issue.

CODEBASE:
{codebase_text}
"""

        tasks = []
        for backend in auditors:
            task = Task(prompt=audit_prompt, category=TaskCategory.CODING)
            decision = RouteDecision(
                primary=backend.id, fallback_chain=[], rationale="Audit broadcast"
            )
            tasks.append(self.executor.run(task, decision, parallel=False))

        results: list[TaskResult] = await asyncio.gather(*tasks)

        # Consolidate issues
        all_issues = []
        for res in results:
            if not res.success:
                continue

            output = res.output
            # Find the first JSON array in the output
            match = re.search(r"\[\s*\{.*?\}\s*\]", output, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                    if isinstance(parsed, list):
                        for item in parsed:
                            if isinstance(item, dict) and "file" in item and "problem" in item:
                                all_issues.append(item)
                except json.JSONDecodeError:
                    pass

        if not all_issues:
            console.print("[green]✓ No critical issues found by the agents![/]")
            return

        # Deduplicate issues loosely by file + problem prefix
        seen = set()
        unique_issues = []
        for issue in all_issues:
            key = (issue["file"], issue["problem"][:20])
            if key not in seen:
                seen.add(key)
                unique_issues.append(issue)

        issues_to_fix = unique_issues[:max_issues]
        remaining = len(unique_issues) - len(issues_to_fix)

        console.print(
            f"\n[bold yellow]Found {len(unique_issues)} unique issues. Auto-fixing {len(issues_to_fix)}...[/]"
        )

        snapshot_files = [
            root / issue["file"] for issue in issues_to_fix if (root / issue["file"]).exists()
        ]
        snapshot_dir = create_snapshot(root, snapshot_files) if snapshot_files else None
        if snapshot_dir:
            console.print(f"[dim]Snapshot saved at {snapshot_dir}[/]")
            console.print("[dim]Use `leader restore --path <snapshot>` to roll back instantly.[/]")

        primary_backend = auditors[0]

        fix_table = Table(title="Autonomous Fix Report", show_lines=True)
        fix_table.add_column("File", style="cyan")
        fix_table.add_column("Problem")
        fix_table.add_column("Status", justify="center")

        for issue in issues_to_fix:
            file_path = issue["file"]
            problem = issue["problem"]

            target_file = root / file_path
            if not target_file.exists():
                fix_table.add_row(file_path, problem, "[red]File not found[/]")
                continue

            original_code = target_file.read_text(encoding="utf-8")

            fix_prompt = f"""
You are an expert autonomous software engineer.
I have a file: {file_path}
The following problem was identified in this file:
{problem}

Here is the current code:
```
{original_code}
```

Rewrite the ENTIRE file to fix this problem. 
DO NOT ADD ANY EXPLANATION. 
OUTPUT ONLY THE NEW RAW FILE CONTENT. Do not wrap it in markdown code blocks.
"""

            task = Task(prompt=fix_prompt, category=TaskCategory.CODING)
            decision = RouteDecision(
                primary=primary_backend.id, fallback_chain=[], rationale="Auto-fix"
            )

            console.print(f"  [dim]Fixing {file_path} using {primary_backend.display_name}...[/]")
            fix_result = await self.executor.run(task, decision, parallel=False)

            if fix_result.success:
                new_code = fix_result.output
                new_code = re.sub(r"^```[a-zA-Z]*\n", "", new_code)
                new_code = re.sub(r"\n```$", "", new_code)

                if new_code != original_code:
                    if not auto_approve:
                        diff = "\n".join(
                            difflib.unified_diff(
                                original_code.splitlines(),
                                new_code.splitlines(),
                                fromfile=file_path,
                                tofile=file_path,
                                lineterm="",
                            )
                        )
                        console.print(f"\n[bold magenta]Proposed fix for {file_path}:[/]")
                        syntax = Syntax(diff, "diff", theme="monokai", line_numbers=False)
                        console.print(syntax)

                        if not Confirm.ask("Apply this fix?"):
                            console.print(f"[yellow]Skipped {file_path}[/]")
                            fix_table.add_row(file_path, problem, "[yellow]Skipped[/]")
                            continue

                target_file.write_text(new_code, encoding="utf-8")
                fix_table.add_row(file_path, problem, "[green]Fixed[/]")
            else:
                fix_table.add_row(file_path, problem, "[red]Failed[/]")

        console.print("\n")
        console.print(fix_table)

        if remaining > 0:
            console.print(
                f"\n[yellow]💡 There were {remaining} more issues identified. Run `leader review` again to fix them![/]"
            )
