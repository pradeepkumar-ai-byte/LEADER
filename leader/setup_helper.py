"""
Leader – Setup Helper

Provides step-by-step installation instructions for each backend adapter.
Run: leader setup <backend_name>
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

# ── Installation guides per backend ──────────────────────────────────────────
# Each entry maps a backend id to a dict with:
#   "type": "pip" | "binary" | "rest" | "cloud"
#   "install": shell command or instructions
#   "verify": how to verify it works
#   "notes": any extra context

_SETUP_GUIDES: dict[str, dict] = {
    "direct_llm": {
        "type": "built-in",
        "install": "No installation needed — this is Leader's built-in adapter.",
        "verify": "leader ping",
        "config": (
            "Add to ~/.leader/config.yaml:\n"
            "  direct_llm:\n"
            "    provider: anthropic  # or openai, openrouter\n"
            "    api_key: sk-ant-..."
        ),
    },
    "autogen": {
        "type": "pip",
        "install": "pip install pyautogen",
        "verify": "python -c \"import autogen; print('AutoGen OK')\"",
        "config": (
            "Add to ~/.leader/config.yaml:\n"
            "  autogen:\n"
            "    api_key: sk-proj-...  # OpenAI key for AutoGen agents\n"
            "    model: gpt-4"
        ),
    },
    "crewai": {
        "type": "pip",
        "install": "pip install crewai",
        "verify": "python -c \"import crewai; print('CrewAI OK')\"",
        "config": (
            "Add to ~/.leader/config.yaml:\n"
            "  crewai:\n"
            "    api_key: sk-proj-...  # OpenAI key used by CrewAI agents"
        ),
    },
    "langchain": {
        "type": "pip",
        "install": "pip install langchain langchain-openai",
        "verify": "python -c \"import langchain; print('LangChain OK')\"",
        "config": (
            "Add to ~/.leader/config.yaml:\n"
            "  langchain:\n"
            "    base_url: http://localhost:8000  # LangServe endpoint\n"
            "    api_key: your-key"
        ),
    },
    "openclaw": {
        "type": "binary",
        "install": (
            "# Install OpenClaw CLI:\n"
            "# macOS/Linux:\n"
            "curl -fsSL https://get.openclaw.dev | sh\n"
            "# Or via package manager:\n"
            "brew install openclaw/tap/openclaw"
        ),
        "verify": "openclaw --version",
        "config": "No config needed — Leader detects the binary in PATH automatically.",
    },
    "zeroclaw": {
        "type": "binary",
        "install": (
            "# Install ZeroClaw (Rust-based):\n"
            "cargo install zeroclaw\n"
            "# Or download binary from:\n"
            "# https://github.com/zeroclaw-labs/zeroclaw/releases"
        ),
        "verify": "zeroclaw --version",
        "config": "No config needed — Leader detects the binary in PATH automatically.",
    },
    "n8n": {
        "type": "rest",
        "install": (
            "# Run n8n via Docker:\n"
            "docker run -d --name n8n -p 5678:5678 n8nio/n8n\n"
            "# Or install globally:\n"
            "npm install -g n8n && n8n start"
        ),
        "verify": "curl http://localhost:5678/healthz",
        "config": (
            "Add to ~/.leader/config.yaml:\n"
            "  n8n:\n"
            "    base_url: http://localhost:5678\n"
            "    api_key: your-n8n-api-key"
        ),
    },
    "babyagi": {
        "type": "rest",
        "install": (
            "# Clone and run BabyAGI:\n"
            "git clone https://github.com/yoheinakajima/babyagi\n"
            "cd babyagi && pip install -r requirements.txt\n"
            "python babyagi.py"
        ),
        "verify": "curl http://localhost:8080/health",
        "config": (
            "Add to ~/.leader/config.yaml:\n"
            "  babyagi:\n"
            "    base_url: http://localhost:8080\n"
            "    api_key: your-openai-key"
        ),
    },
    "metagpt": {
        "type": "pip",
        "install": "pip install metagpt",
        "verify": "python -c \"import metagpt; print('MetaGPT OK')\"",
        "config": (
            "Add to ~/.leader/config.yaml:\n"
            "  metagpt:\n"
            "    base_url: http://localhost:8081\n"
            "    api_key: your-key"
        ),
    },
    "litellm": {
        "type": "pip",
        "install": "pip install litellm",
        "verify": "python -c \"import litellm; print('LiteLLM OK')\"",
        "config": (
            "Add to ~/.leader/config.yaml:\n"
            "  litellm:\n"
            "    base_url: http://localhost:4000  # LiteLLM proxy\n"
            "    api_key: sk-..."
        ),
    },
    "replicate": {
        "type": "cloud",
        "install": "pip install replicate",
        "verify": "python -c \"import replicate; print('Replicate OK')\"",
        "config": (
            "Add to ~/.leader/config.yaml:\n"
            "  replicate:\n"
            "    api_key: r8_...  # Get from replicate.com/account"
        ),
    },
    "huggingface": {
        "type": "cloud",
        "install": "pip install huggingface_hub",
        "verify": "python -c \"import huggingface_hub; print('HF OK')\"",
        "config": (
            "Add to ~/.leader/config.yaml:\n"
            "  huggingface:\n"
            "    api_key: hf_...  # Get from huggingface.co/settings/tokens"
        ),
    },
}


def show_setup(backend_id: str) -> None:
    """Print setup instructions for a specific backend."""
    guide = _SETUP_GUIDES.get(backend_id)

    if guide is None:
        console.print(f"[red]No setup guide available for '{backend_id}'.[/]")
        console.print("[dim]Available guides:[/]")
        for bid in sorted(_SETUP_GUIDES.keys()):
            console.print(f"  • {bid}")
        return

    panel_content = []
    panel_content.append(f"[bold]Type:[/] {guide['type']}")
    panel_content.append("")
    panel_content.append("[bold cyan]1. Install[/]")
    panel_content.append(guide["install"])
    panel_content.append("")
    panel_content.append("[bold cyan]2. Verify[/]")
    panel_content.append(f"  $ {guide['verify']}")
    panel_content.append("")
    panel_content.append("[bold cyan]3. Configure[/]")
    panel_content.append(guide.get("config", "No additional config needed."))

    console.print(
        Panel(
            "\n".join(panel_content),
            title=f"Setup: {backend_id}",
            border_style="green",
        )
    )


def show_all_backends() -> None:
    """Print a summary table of all backends and their setup type."""
    table = Table(title="Backend Setup Overview", show_lines=True)
    table.add_column("Backend", style="cyan")
    table.add_column("Type", style="yellow")
    table.add_column("Install Command")

    for bid, guide in sorted(_SETUP_GUIDES.items()):
        install = guide["install"].split("\n")[0][:60]
        table.add_row(bid, guide["type"], install)

    console.print(table)
    console.print("\n[dim]Run `leader setup <backend>` for detailed instructions.[/]")
