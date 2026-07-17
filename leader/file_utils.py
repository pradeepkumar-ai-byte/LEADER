"""
Leader - File Utilities for reading codebases safely
"""

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

IGNORED_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    "venv",
    ".venv",
    ".env",
    "build",
    "dist",
    ".idea",
    ".vscode",
}
IGNORED_EXTS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".so",
    ".dll",
    ".exe",
    ".bin",
    ".jpg",
    ".png",
    ".gif",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
}


def _backup_root(root: Path) -> Path:
    return root / ".leader" / "backups"


def create_snapshot(root_path: str | Path, files: Iterable[str | Path]) -> Path:
    """Create a restorable snapshot of selected files under the project root."""
    root = Path(root_path).resolve()
    backup_root = _backup_root(root)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot_dir = backup_root / stamp
    suffix = 1
    while snapshot_dir.exists():
        snapshot_dir = backup_root / f"{stamp}-{suffix}"
        suffix += 1

    snapshot_dir.mkdir(parents=True, exist_ok=False)

    manifest_files: list[str] = []
    for file_item in files:
        source = Path(file_item).resolve()
        if not source.exists() or not source.is_file():
            continue
        try:
            relative_path = source.relative_to(root)
        except ValueError:
            continue

        destination = snapshot_dir / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        manifest_files.append(str(relative_path))

    manifest = {
        "root": str(root),
        "created_at": stamp,
        "files": manifest_files,
    }
    (snapshot_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return snapshot_dir


def latest_snapshot(root_path: str | Path) -> Path | None:
    root = Path(root_path).resolve()
    backup_root = _backup_root(root)
    if not backup_root.exists():
        return None

    snapshots = [p for p in backup_root.iterdir() if p.is_dir() and (p / "manifest.json").exists()]
    if not snapshots:
        return None
    return max(snapshots, key=lambda p: p.stat().st_mtime)


def restore_snapshot(snapshot_dir: str | Path, root_path: str | Path | None = None) -> int:
    """Restore a snapshot back into the original project tree."""
    snapshot = Path(snapshot_dir).resolve()
    manifest_path = snapshot / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Snapshot manifest not found: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = Path(root_path).resolve() if root_path is not None else Path(manifest["root"]).resolve()

    restored = 0
    resolved_root = root.resolve()
    for relative in manifest.get("files", []):
        source = snapshot / relative
        destination = (root / relative).resolve()
        try:
            destination.relative_to(resolved_root)
        except ValueError:
            # Skip files that attempt to escape the project root
            continue
        if not source.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        restored += 1

    return restored


def gather_codebase(root_path: str | Path, max_files: int = 1000, max_bytes: int = 500_000) -> str:
    """Reads a directory and returns a formatted string of the source files."""
    root = Path(root_path).resolve()
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root_path}")

    code_text = []
    file_count = 0
    total_bytes = 0

    for dirpath, dirnames, filenames in os.walk(root):
        # Filter ignored directories in place
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS and not d.startswith(".")]

        for file in filenames:
            if file.startswith("."):
                continue
            ext = os.path.splitext(file)[1].lower()
            if ext in IGNORED_EXTS:
                continue

            path = Path(dirpath) / file

            # Skip files that are too large (e.g., > 100KB)
            try:
                size = path.stat().st_size
                if size > 100_000:
                    continue
            except OSError:
                continue

            try:
                content = path.read_text(encoding="utf-8")
                # Pre-check context limits to avoid confusing the LLM with appended strings
                content_bytes = len(content.encode("utf-8"))

                # Format with standard code block wrapper
                rel_path = path.relative_to(root)
                code_text.append(f"--- {rel_path} ---\n{content}\n")
                file_count += 1
                total_bytes += content_bytes

                if total_bytes >= max_bytes:
                    print(
                        f"\n\033[93m[WARNING] Codebase truncated! Reached max {max_bytes} bytes limit.\033[0m"
                    )
                    print(
                        "\033[93mConsider running `leader review` on a specific subfolder (e.g., ./src) to avoid missing context.\033[0m\n"
                    )
                    return "\n".join(code_text)

                if file_count >= max_files:
                    print(
                        f"\n\033[93m[WARNING] Codebase truncated! Reached max {max_files} files limit.\033[0m"
                    )
                    print(
                        "\033[93mConsider running `leader review` on a specific subfolder.\033[0m\n"
                    )
                    return "\n".join(code_text)

            except UnicodeDecodeError:
                pass  # Skip binary files that don't have ignored extensions
            except OSError:
                pass

    return "\n".join(code_text)
