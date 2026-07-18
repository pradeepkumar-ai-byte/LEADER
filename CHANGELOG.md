# Changelog

All notable changes to the **Leader** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-07-19

### Added
- **Intelligent Codebase Review (`leader review`)**: Added autonomous codebase-wide code audit and auto-fix loop using connected specialist backends, executing concurrently across source files.
- **Diff Preview Mode**: Interactive git-style Unified Diff preview with color syntax highlighting using `Rich` for reviewing proposed changes, requiring user confirmation before overwriting code (or skipping using `--auto-approve`).
- **Snapshot Backup & Restore**: Auto-saves file snapshots prior to applying autonomous fixes, enabling instant rollbacks with `leader restore`.
- **Semantic Router Classifier**: Completely overhauled the task classifier to use TF-IDF weighted bi-gram phrase scoring with negative weight suppressors, correctly routing complex coding prompts like "Write me a bug report".
- **Path Traversal Safety**: Implemented resolved path sub-path containment checks in `restore_snapshot` to prevent directory traversal writing outside the project root.
- **Uniqueness Guarantee**: Switched `task_id` generation to `uuid.uuid4` to eliminate collision potential during high-frequency parallel executions.
- **Closed-Loop Feedback Routing**: Wired human feedback ratings (1-5 scale) directly into routing decisions, shifting the evolutionary router formula to a 50/30/20 history, static, and user-feedback blend.
- **PyPI & CI Repair**: Fixed pyproject.toml packaging compatibility by removing the deprecated License classifier, updated GitHub Actions to run the full test suite (91 passing tests), and added an automated publish release workflow `.github/workflows/publish.yml`.
- **Cost Tracking**: Fully wired model cost calculation from input/output tokens in direct_llm provider queries.
- **Interactive Setup Helper**: Created `leader setup <backend>` with detailed guides for pip, binaries, and self-hosted instances.
- **Docker Adapter Bridge**: Expanded `docker-compose.adapters.yml` with a Python-based FastAPI mock bridge container that instantly mocks all REST-based agent platforms to facilitate testing and local development.

## [0.1.0] - 2026-07-16

This is the initial open-source release of Leader.

### Added
- **Core Routing Engine**: Intelligent keyword-based task classification into 8 categories.
- **Evolved Scoring**: Blended scoring system combining static capabilities (40%) and local win-rates/latency history (60%).
- **Fallback Chains**: Automatically routes to fallback backends on execution failure.
- **Parallel Mode**: Race multiple backends simultaneously and return the fastest successful result.
- **Introspection Tools**: CLI commands `backends`, `stats`, `ping`, and `feedback`.
- **Smart Retries**: Automatic exponential backoff retries for transient network errors (safely avoiding side-effecting tasks like messaging).
- **Built-in Adapters**: Support for 30+ adapters including agent platforms, orchestration frameworks, LLM providers, and no-code automation.
- **Python SDK**: Simple 3-line embedding interface (`from leader import Leader`).
- **REST API Server**: aiohttp-based API server with endpoints for routing, execution, and stats.
- **Middleware**: Drop-in middleware for existing aiohttp apps.
- **Plugin System**: Native wrappers for OpenClaw (registering Leader as a skill) and generic webhooks (e.g. for n8n/Make/Zapier).
- **VS Code Extension Generator**: CLI command to generate a ready-to-use VS Code extension scaffold.
- **Docker Support**: Dockerfile and Docker Compose configurations for containerized deployment.
