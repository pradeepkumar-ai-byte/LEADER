"""
Leader – VS Code / Cursor Integration Helper

Generates the configuration files needed to integrate Leader into
VS Code, Cursor, or any VS Code-compatible editor as an extension.

Usage (from Python — generates the extension scaffold):

    from leader.plugins import VSCodePlugin
    plugin = VSCodePlugin()
    plugin.generate_extension("/path/to/output")

Usage (from CLI):

    leader vscode-extension --output ./leader-vscode

This generates a ready-to-install VS Code extension that:
- Adds a "Leader: Run Task" command to the command palette
- Forwards tasks to Leader's REST API server
- Displays results in the VS Code output panel
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from .base import BasePlugin
from ..sdk import Leader


class VSCodePlugin(BasePlugin):
    """
    VS Code / Cursor integration plugin.

    This plugin generates a VS Code extension scaffold that communicates
    with Leader's REST API. The extension can be installed in VS Code,
    Cursor, Windsurf, or any VS Code-compatible editor.
    """

    def __init__(
        self,
        leader: Leader | None = None,
        config: dict | None = None,
        server_url: str = "http://127.0.0.1:8585",
    ):
        super().__init__(leader=leader, config=config)
        self.server_url = server_url

    @property
    def name(self) -> str:
        return "Leader for VS Code"

    async def install(self, host: Any) -> None:
        """
        For VS Code, 'install' means generating the extension files.
        Pass the output directory path as the host argument.
        """
        output_dir = Path(str(host))
        self.generate_extension(output_dir)
        self._installed = True

    async def on_task(self, prompt: str, context: dict | None = None) -> dict:
        """Route a task through Leader (used when called programmatically)."""
        result = await self.route_task(prompt, category=(context or {}).get("category"))
        return self.result_to_dict(result)

    def generate_extension(self, output_dir: Path | str) -> None:
        """
        Generate a complete VS Code extension scaffold.

        Args:
            output_dir: Directory to write the extension files into.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        self._write_package_json(output_dir)
        self._write_extension_js(output_dir)
        self._write_readme(output_dir)

        print(f"✓ VS Code extension generated at {output_dir}")
        print(f"  To install:")
        print(f"    1. Start Leader server: leader serve")
        print(f"    2. Open VS Code → Extensions → '...' → Install from VSIX")
        print(f"    3. Or copy to ~/.vscode/extensions/leader-vscode/")

    def _write_package_json(self, output_dir: Path):
        package = {
            "name": "leader-vscode",
            "displayName": "Leader — AI Agent Router",
            "description": "Route tasks to the best AI backend from VS Code",
            "version": "0.1.0",
            "publisher": "leader-agent",
            "engines": {"vscode": "^1.80.0"},
            "categories": ["Other"],
            "activationEvents": [],
            "main": "./extension.js",
            "contributes": {
                "commands": [
                    {
                        "command": "leader.runTask",
                        "title": "Leader: Run Task",
                    },
                    {
                        "command": "leader.runSelection",
                        "title": "Leader: Run Selected Text",
                    },
                    {
                        "command": "leader.showBackends",
                        "title": "Leader: Show Backends",
                    },
                ],
                "configuration": {
                    "title": "Leader",
                    "properties": {
                        "leader.serverUrl": {
                            "type": "string",
                            "default": self.server_url,
                            "description": "URL of the Leader API server",
                        },
                    },
                },
            },
        }
        (output_dir / "package.json").write_text(
            json.dumps(package, indent=2), encoding="utf-8"
        )

    def _write_extension_js(self, output_dir: Path):
        js = """\
const vscode = require('vscode');

/**
 * Leader VS Code Extension
 *
 * Connects to a running Leader API server and routes tasks
 * to the best AI backend from within VS Code / Cursor.
 */

function getServerUrl() {
    const config = vscode.workspace.getConfiguration('leader');
    return config.get('serverUrl', 'http://127.0.0.1:8585');
}

async function callLeader(endpoint, method = 'GET', body = null) {
    const url = `${getServerUrl()}${endpoint}`;
    const options = {
        method,
        headers: { 'Content-Type': 'application/json' },
    };
    if (body) options.body = JSON.stringify(body);

    try {
        const response = await fetch(url, options);
        return await response.json();
    } catch (err) {
        vscode.window.showErrorMessage(
            `Leader: Cannot connect to server at ${getServerUrl()}. ` +
            `Start it with: leader serve`
        );
        return null;
    }
}

function activate(context) {
    // Output channel for results
    const output = vscode.window.createOutputChannel('Leader');

    // Command: Run Task (prompt user for input)
    const runTask = vscode.commands.registerCommand('leader.runTask', async () => {
        const prompt = await vscode.window.showInputBox({
            prompt: 'What would you like Leader to do?',
            placeHolder: 'e.g., "write a function to sort a list"',
        });
        if (!prompt) return;

        output.show();
        output.appendLine(`\\n→ Task: ${prompt}`);
        output.appendLine('  Routing...');

        const result = await callLeader('/api/run', 'POST', { prompt });
        if (!result) return;

        if (result.success) {
            output.appendLine(`  ✓ Backend: ${result.backend_id}`);
            output.appendLine(`  ✓ Latency: ${Math.round(result.latency_ms)}ms`);
            output.appendLine(`\\n${result.output}\\n`);
        } else {
            output.appendLine(`  ✗ Error: ${result.error}`);
        }
    });

    // Command: Run Selected Text
    const runSelection = vscode.commands.registerCommand('leader.runSelection', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showWarningMessage('No active editor');
            return;
        }
        const selection = editor.document.getText(editor.selection);
        if (!selection) {
            vscode.window.showWarningMessage('No text selected');
            return;
        }

        output.show();
        output.appendLine(`\\n→ Task (selection): ${selection.substring(0, 100)}...`);
        output.appendLine('  Routing...');

        const result = await callLeader('/api/run', 'POST', {
            prompt: selection,
            category: 'coding',
        });
        if (!result) return;

        if (result.success) {
            output.appendLine(`  ✓ Backend: ${result.backend_id}`);
            output.appendLine(`\\n${result.output}\\n`);
        } else {
            output.appendLine(`  ✗ Error: ${result.error}`);
        }
    });

    // Command: Show Backends
    const showBackends = vscode.commands.registerCommand('leader.showBackends', async () => {
        const data = await callLeader('/api/backends');
        if (!data) return;

        output.show();
        output.appendLine('\\n── Leader Backends ──');
        output.appendLine(`Connected: ${data.connected.length}`);
        data.connected.forEach(b => {
            output.appendLine(`  ● ${b.name} (${b.id}) — ${b.strengths.join(', ')}`);
        });
        output.appendLine(`Available (not connected): ${data.available.length}`);
        data.available.forEach(b => {
            output.appendLine(`  ○ ${b.name} (${b.id})`);
        });
    });

    context.subscriptions.push(runTask, runSelection, showBackends);
}

function deactivate() {}

module.exports = { activate, deactivate };
"""
        (output_dir / "extension.js").write_text(js, encoding="utf-8")

    def _write_readme(self, output_dir: Path):
        readme = """\
# Leader for VS Code

Routes tasks to the best AI backend from within VS Code, Cursor, or any
VS Code-compatible editor.

## Requirements

Leader server must be running:

```bash
pip install leader-agent
leader init
leader serve
```

## Commands

- **Leader: Run Task** — Opens an input box, routes your prompt
- **Leader: Run Selected Text** — Routes the currently selected text
- **Leader: Show Backends** — Lists connected and available backends

## Configuration

- `leader.serverUrl`: URL of the Leader server (default: `http://127.0.0.1:8585`)
"""
        (output_dir / "README.md").write_text(readme, encoding="utf-8")
