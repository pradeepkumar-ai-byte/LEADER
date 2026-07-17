"""
Leader – config loader with validation

Supports environment variable fallback for API keys:
  ANTHROPIC_API_KEY, OPENAI_API_KEY, OPENROUTER_API_KEY
  LEADER_API_KEY_{BACKEND_ID}  (e.g. LEADER_API_KEY_OPENCLAW)
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import yaml

from .models import TaskCategory
from .registry import BackendSpec, Registry

CONFIG_PATH = Path.home() / ".leader" / "config.yaml"

# ── environment variable mapping ─────────────────────────────────────────────

_ENV_KEY_MAP: dict[str, list[str]] = {
    "anthropic": ["ANTHROPIC_API_KEY"],
    "openai": ["OPENAI_API_KEY"],
    "openrouter": ["OPENROUTER_API_KEY"],
}


def _resolve_api_key(backend_id: str, bconf: dict) -> str | None:
    """
    Resolve an API key for a backend, checking (in order):
      1. Explicit value in the config file
      2. Provider-specific env var (e.g. ANTHROPIC_API_KEY)
      3. Generic env var  LEADER_API_KEY_{BACKEND_ID}
    """
    # 1. Config file value
    key = bconf.get("api_key")
    if key:
        return key

    # 2. Provider-specific env var (for direct_llm)
    provider = bconf.get("provider", "")
    for env_name in _ENV_KEY_MAP.get(provider, []):
        val = os.environ.get(env_name)
        if val:
            return val

    # 3. Generic per-backend env var
    generic_env = f"LEADER_API_KEY_{backend_id.upper()}"
    val = os.environ.get(generic_env)
    if val:
        return val

    return None


class ConfigError(Exception):
    pass


def _validate_backend(backend_id: str, bconf: dict) -> list[str]:
    errors = []
    if backend_id == "direct_llm":
        if not bconf.get("provider"):
            errors.append(
                f"[{backend_id}] 'provider' is required (anthropic | openai | openrouter)"
            )
        if not _resolve_api_key(backend_id, bconf):
            errors.append(
                f"[{backend_id}] 'api_key' is required — set it in config or as an "
                f"environment variable (e.g. ANTHROPIC_API_KEY)"
            )
    elif backend_id in ("openclaw", "hermes"):
        if not bconf.get("base_url"):
            errors.append(f"[{backend_id}] 'base_url' is required (e.g. http://localhost:8888)")
    elif backend_id == "zeroclaw":
        if not bconf.get("base_url") and not bconf.get("binary"):
            errors.append(f"[{backend_id}] either 'base_url' or 'binary' is required")
    return errors


def load(registry: Registry, config_path: Path | None = None) -> list[str]:
    """
    Read config, validate, and update registry in-place.
    Returns a list of validation warnings (non-fatal).
    """
    if config_path is None:
        config_path = CONFIG_PATH

    if not config_path.exists():
        return []

    with open(config_path) as f:
        cfg = yaml.safe_load(f) or {}

    backends_cfg: dict = cfg.get("backends") or {}
    warnings = []

    for backend_id, bconf in backends_cfg.items():
        bconf = bconf or {}

        # Resolve API key from environment variables if not in config
        resolved_key = _resolve_api_key(backend_id, bconf)
        if resolved_key and not bconf.get("api_key"):
            bconf["api_key"] = resolved_key

        errs = _validate_backend(backend_id, bconf)
        if errs:
            warnings.extend(errs)
            continue  # don't mark as connected if config is broken

        if backend_id in registry._specs:
            spec = registry._specs[backend_id]
            spec.connected = True
            spec.config = bconf
        else:
            strengths = [TaskCategory(s) for s in bconf.get("strengths", ["general"])]
            spec = BackendSpec(
                id=backend_id,
                display_name=bconf.get("display_name", backend_id),
                description=bconf.get("description", "User-added backend"),
                strengths=strengths,
                weaknesses=[],
                homepage=bconf.get("homepage", ""),
                adapter_class=bconf.get(
                    "adapter_class",
                    "leader.adapters.generic_rest.GenericRestAdapter",
                ),
                connected=True,
                config=bconf,
            )
            registry.register(spec)

    return warnings


def _secure_file(path: Path) -> None:
    """Set restrictive file permissions (owner-only) on Unix/macOS."""
    if sys.platform != "win32":
        try:
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600
        except OSError:
            pass  # best-effort; some filesystems don't support chmod


def _secure_directory(path: Path) -> None:
    """Set restrictive directory permissions (owner-only) on Unix/macOS."""
    if sys.platform != "win32":
        try:
            path.chmod(stat.S_IRWXU)  # 0o700
        except OSError:
            pass


def scaffold(config_path: Path | None = None) -> None:
    if config_path is None:
        config_path = CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)

    _secure_directory(config_path.parent)

    if config_path.exists():
        print(f"Config already exists at {config_path}")
        return
    template = """\
# Leader configuration
# Leader works with whichever backends you connect. Nothing is required.
# The fastest start is direct_llm — just paste an API key, no extra software.
#
# TIP: You can also set API keys as environment variables instead of writing
# them here. Leader checks these automatically:
#   ANTHROPIC_API_KEY, OPENAI_API_KEY, OPENROUTER_API_KEY
#   LEADER_API_KEY_{BACKEND_ID}  (e.g. LEADER_API_KEY_OPENCLAW)

backends:

  # ── FASTEST START: works with just an API key, no extra software ──────────
  # direct_llm:
  #   provider: anthropic           # or: openai | openrouter
  #   api_key: sk-ant-...           # or set ANTHROPIC_API_KEY env var
  #   model: claude-sonnet-4-6      # optional override

  # ── AGENT BACKENDS: connect any you already run ───────────────────────────
  # openclaw:
  #   base_url: http://localhost:8888
  #   api_key: your-openclaw-key    # optional, or set LEADER_API_KEY_OPENCLAW

  # hermes:
  #   base_url: http://localhost:7777

  # zeroclaw:
  #   binary: /usr/local/bin/zeroclaw
  #   # or:
  #   # base_url: http://localhost:9999

  # ── CUSTOM: any REST backend ──────────────────────────────────────────────
  # my_agent:
  #   display_name: My Internal Agent
  #   description: Handles company-specific tasks
  #   strengths: [coding, automation]
  #   base_url: http://internal.company.com/agent
  #   endpoint: /api/run
  #   prompt_field: query
  #   output_field: answer
  #   auth_header: Authorization
  #   auth_value: Bearer my-token
"""
    config_path.write_text(template, encoding="utf-8")
    _secure_file(config_path)

    print(f"✓ Config written to {config_path}")
    print("  Edit it to add backends, then run: leader backends")
