"""
Leader – Plugin System

Provides base classes and utilities for embedding Leader inside
host applications (OpenClaw, VS Code, Cursor, custom apps, etc.)
"""

from .base import BasePlugin
from .openclaw_plugin import OpenClawPlugin
from .vscode import VSCodePlugin
from .webhook import WebhookPlugin

__all__ = [
    "BasePlugin",
    "OpenClawPlugin",
    "WebhookPlugin",
    "VSCodePlugin",
]
