"""
Leader - File Utilities for reading codebases safely
"""
import os
from pathlib import Path

IGNORED_DIRS = {".git", "node_modules", "__pycache__", "venv", ".venv", ".env", "build", "dist", ".idea", ".vscode"}
IGNORED_EXTS = {".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe", ".bin", ".jpg", ".png", ".gif", ".pdf", ".zip", ".tar", ".gz"}

def gather_codebase(root_path: str | Path, max_files: int = 100) -> str:
    """Reads a directory and returns a formatted string of the source files."""
    root = Path(root_path).resolve()
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root_path}")
        
    code_text = []
    file_count = 0
    
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
                if path.stat().st_size > 100_000:
                    continue
            except OSError:
                continue

            try:
                content = path.read_text(encoding="utf-8")
                # Format with standard code block wrapper
                rel_path = path.relative_to(root)
                code_text.append(f"--- {rel_path} ---\n{content}\n")
                file_count += 1
                
                if file_count >= max_files:
                    code_text.append("\n[Warning: Codebase truncated to max files limit]")
                    return "\n".join(code_text)
                    
            except UnicodeDecodeError:
                pass  # Skip binary files that don't have ignored extensions
            except OSError:
                pass
                
    return "\n".join(code_text)
