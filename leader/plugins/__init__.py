"""
Leader – Plugin System

Provides base classes and utilities for embedding Leader inside
host applications (OpenClaw, VS Code, Cursor, custom apps, etc.)
"""
from .base import BasePlugin
from .openclaw_plugin import OpenClawPlugin
from .webhook import WebhookPlugin
from .vscode import VSCodePlugin

__all__ = [
    "BasePlugin",
    "OpenClawPlugin",
    "WebhookPlugin",
    "VSCodePlugin",
]
