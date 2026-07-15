# Changelog

All notable changes to the **Leader** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
