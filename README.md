<p align="center">
  <img src="assets/banner.jpg" alt="Leader Logo" width="320"/>
</p>

<h1 align="center">Leader</h1>

<p align="center">
  <strong>A credential-aware task router for AI agents, automation workflows, and LLMs.</strong>
</p>

<p align="center">
  <a href="https://github.com/pradeepkumar-ai-byte/LEADER/actions"><img src="https://github.com/pradeepkumar-ai-byte/LEADER/actions/workflows/ci.yml/badge.svg" alt="CI Status"></a>
  <a href="https://pypi.org/project/leader-agent/"><img src="https://img.shields.io/pypi/v/leader-agent?color=blue" alt="PyPI Version"></a>
  <a href="https://github.com/pradeepkumar-ai-byte/LEADER/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python Support"></a>
  <a href="https://hub.docker.com/"><img src="https://img.shields.io/badge/docker-ready-blue" alt="Docker Support"></a>
</p>

---

## Technical Overview

In modern AI engineering, developers rarely rely on a single model or agent framework. A production workspace often consists of multiple specialized systems:
* **CrewAI** or **Microsoft AutoGen** for multi-agent coordination.
* **n8n** or **Zapier** for database and business tool webhooks.
* **LangChain** or **LlamaIndex** for RAG pipelines.
* **Local Ollama** or **Direct APIs** (Anthropic, OpenAI) for raw model inference.

**Leader** is a lightweight, credential-aware routing layer that sits above these frameworks. Instead of manually writing complex conditional logic to dispatch tasks, Leader dynamically classifies incoming prompts, filters backends by credential availability, routes to the best-performing service, and adapts based on latency and success history.

---

## How It Works

Leader operates as a clean dispatch pipeline:

```
                            User Prompt
                                 │
                                 ▼
                    [ 1. Credential Filter ]
        Checks active environment variables & YAML configs.
        Only connected/online backends are permitted to run.
                                 │
                                 ▼
                     [ 2. Evolved Scoring ]
        Classifies task and scores active backends using:
        Score = (0.4 * StaticWeight) + (0.6 * WinRate * 2) - LatencyPenalty
                                 │
                                 ▼
                     [ 3. Dispatch & Retry ]
        Executes primary backend. On failure, falls back 
        to fallback chain. Logs latency, outcome, and feedback.
```

### The Scoring Algorithm
The routing decision is backed by a hybrid scoring formula:
* **Static Weight (40%)**: Pre-configured affinity matrix mapping backends to task categories (e.g. n8n is highly weighted for `automation`, AutoGen for `multiagent`).
* **Win Rate (60%)**: Lived success rate of the backend on your specific workload, calculated from logged executions.
* **Latency Penalty**: Backends are penalized slightly based on average response time to prevent routing to slow agents when a faster, comparable alternative is available:
  $$\text{Penalty} = \min\left(\frac{\text{Avg Latency (ms)}}{10000}, 0.5\right)$$

---

## Quick Start

### 1. Install
```bash
pip install leader-agent
leader init        # Scaffolds configuration at ~/.leader/config.yaml
```

### 2. Configure Credentials
Leader prioritizes security by resolving credentials from environment variables first, keeping API keys off your disk:

```bash
# Export LLM keys for direct fallback
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-proj-..."

# Export host endpoints for your agent runtimes
export LEADER_API_KEY_CREWAI="your-key-here"
```

---

## Integration Scenarios

Leader is designed to run embedded inside your host application rather than as a separate silo.

### 1. Python SDK
Initialize and execute in 3 lines:
```python
from leader import Leader

leader = Leader()
result = await leader.run("Run code review on commit 4f2a1")

print(f"Dispatched to: {result.backend_id} | Success: {result.success}")
print(result.output)
```

### 2. REST API Server
Run Leader as a local daemon or microservice:
```bash
leader serve --port 8585
```
```bash
curl -X POST http://localhost:8585/api/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "send slack notification to triage channel"}'
```

### 3. Webhook Integration (n8n / Make / Zapier)
Embed Leader as an automation node:
```python
from leader.plugins import WebhookPlugin

plugin = WebhookPlugin()
await plugin.install(app)  # Exposes HTTP POST /webhook/leader
```

### 4. VS Code / Cursor Extension
Generate a packaged editor extension linked to your local router:
```bash
leader vscode-extension --output ./leader-vscode
```

### 5. Docker Deployment
Deploy the API server with persistent volume logging:
```bash
docker-compose up -d
```

---

## CLI Command Reference

```bash
leader run "prompt"              # Route and execute a task
leader run "prompt" --parallel   # Race all connected backends; fastest wins
leader backends                  # List all 30+ backends and connection status
leader ping                      # Health-check connected endpoints
leader stats                     # Show routing win-rates and latencies
leader feedback <task_id> <1-5>  # Submit manual score to update scoring weights
```

---

## Supported Backends (30+)

Leader ships with built-in adapters mapping tasks to standard platforms:

* **Orchestration**: Microsoft AutoGen, CrewAI, MetaGPT, TaskWeaver
* **LLMs**: Anthropic, OpenAI, OpenRouter, LiteLLM, AWS Bedrock, Google Vertex AI, HuggingFace, Replicate
* **Frameworks**: LangChain, LlamaIndex, Semantic Kernel, Griptape
* **No-Code**: n8n, Make (Integromat), Zapier
* **Specialized**: Stability AI, Mem0, MLflow, OpenClaw, ZeroClaw

---

## Verification

Leader includes a comprehensive test suite (42 unit and integration tests) verifying routing decisions, SQLite history logging, database migrations, and adapter execution.

To run tests:
```bash
pip install -e ".[dev]"
pytest leader/ -v
```

---

## Security

* **Config Isolation**: `leader init` automatically restricts config file permissions to `600` (owner read/write only) on Unix-based systems.
* **Env-First Resolution**: API credentials are read from environment variables, preventing plain-text keys from being stored in configuration files.
* **Log Sanitization**: Credentials and tokens are stripped from SQLite storage and CLI print statements.

---

## License & Maintainer

* **Created & maintained by Krish** (pradeepkumar.ai.byte@gmail.com)
* **GitHub**: [@pradeepkumar-ai-byte](https://github.com/pradeepkumar-ai-byte)
* **License**: MIT (Open Source)
