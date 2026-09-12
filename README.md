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

**Leader** is a lightweight, credential-aware routing layer that sits above these frameworks. Instead of manually writing complex conditional logic to dispatch tasks, Leader dynamically classifies incoming prompts, filters backends by credential availability, routes to the best-performing service, and adapts based on latency, success history, and human feedback.

---

## Architecture

```
                     ┌─────────────────────────────────────┐
                     │            User Prompt              │
                     └──────────────┬──────────────────────┘
                                    │
                                    ▼
                     ┌──────────────────────────────────────┐
                     │   1. Semantic Classifier (router.py) │
                     │   TF-IDF weighted bi-gram phrases    │
                     │   + keyword scoring + suppression    │
                     │   → CODING | RESEARCH | CREATIVE ... │
                     └──────────────┬───────────────────────┘
                                    │
                                    ▼
                     ┌──────────────────────────────────────┐
                     │   2. Evolved Scoring (router.py)     │
                     │   Score = 0.3×Static + 0.5×WinRate   │
                     │         + 0.2×Feedback − Latency     │
                     └──────────────┬───────────────────────┘
                                    │
                                    ▼
                     ┌──────────────────────────────────────┐
                     │   3. Credential Filter (registry.py) │
                     │   Only connected backends with valid │
                     │   API keys / base_urls are eligible  │
                     └──────────────┬───────────────────────┘
                                    │
                ┌───────────────────┼───────────────────────┐
                ▼                   ▼                       ▼
         ┌────────────┐    ┌──────────────┐        ┌────────────┐
         │  Primary   │    │  Fallback 1  │  ...   │ Fallback N │
         │  Backend   │    │  Backend     │        │  Backend   │
         └─────┬──────┘    └──────────────┘        └────────────┘
               │
               ▼
         ┌──────────────────────────────────────┐
         │   4. TaskLogger (SQLite)             │
         │   Records dispatch, result, feedback │
         │   → feeds back into evolved scoring  │
         └──────────────────────────────────────┘
```

### The Scoring Algorithm

The routing decision uses a hybrid formula that learns from your workload:

| Component | Weight | Source |
|-----------|--------|--------|
| **Historical Win Rate** | 50% | Success/failure ratio from SQLite task log |
| **Static Affinity** | 30% | Pre-configured strengths/weaknesses per backend |
| **Human Feedback** | 20% | User ratings (1-5) normalised to 0-1 |
| **Latency Penalty** | −0.5 max | `min(avg_latency_ms / 10000, 0.5)` |

$$\text{Score} = 0.3 \times \text{Static} + 0.5 \times \text{WinRate} \times 2 + 0.2 \times \text{Feedback} \times 2 - \text{LatencyPenalty}$$

> See [ARCHITECTURE.md](ARCHITECTURE.md) for the full system design with Mermaid diagrams.

---

## Quick Start

### 1. Install
```bash
pip install leader-agent
leader init        # Scaffolds configuration at ~/.leader/config.yaml
```

### 2. Configure Credentials
Leader prioritizes security by resolving credentials from environment variables first:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-proj-..."
```

### 3. Run
```bash
leader run "Fix the authentication bug in login.py"
```

---

## Integration Scenarios

### 1. Python SDK (3 lines)
```python
from leader import Leader

leader = Leader()
result = await leader.run("Run code review on commit 4f2a1")

print(f"Dispatched to: {result.backend_id} | Cost: ${result.cost_estimate:.4f}")
print(result.output)
```

### 2. REST API Server
```bash
leader serve --port 8585
```
```bash
curl -X POST http://localhost:8585/api/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "send slack notification to triage channel"}'
```

### 3. Autonomous Code Review
```bash
leader review ./src                # Interactive diff preview before each fix
leader review ./src --auto-approve # Auto-apply all fixes (snapshot saved for rollback)
leader restore ./src               # Instant rollback to pre-fix snapshot
```

### 4. Backend Setup Helper
```bash
leader setup autogen    # Step-by-step install + config instructions
leader setup crewai     # Works for all 30+ adapters
```

### 5. Multi-Agent Framework Bridges (AutoGen & CrewAI Drop-in Security)

Secure enterprise multi-agent workflows in **three lines of code**:

#### Microsoft AutoGen
```python
from autogen import AssistantAgent, UserProxyAgent, GroupChat
from leader.bridges.autogen import LeaderGroupChatManager, LeaderSpeakerSelector

coder = AssistantAgent(name="Coder", llm_config={"model": "gpt-4o"})
reviewer = AssistantAgent(name="Reviewer", llm_config={"model": "gpt-4o"})
user_proxy = UserProxyAgent(name="Admin", human_input_mode="NEVER")

groupchat = GroupChat(agents=[user_proxy, coder, reviewer], messages=[], max_round=10)

# Drop-in secure manager: intercepts prompt injections, halts infinite ping-pong loops & drift
manager = LeaderGroupChatManager(groupchat=groupchat, speaker_selector=LeaderSpeakerSelector())
user_proxy.initiate_chat(manager, message="Refactor database connection pool and write unit tests")
```

#### CrewAI
```python
from crewai import Agent, Task, Process
from leader.bridges.crewai import LeaderCrew, LeaderStepCallback, LeaderTaskCallback

# Drop in LeaderCrew to automatically enforce prompt firewalls, drift tracking, and circuit breaker output validation
crew = LeaderCrew(
    agents=[researcher, writer],
    tasks=[task1, task2],
    process=Process.sequential,
)
result = crew.kickoff(inputs={"topic": "EV Battery Market 2026"})
```

> See [docs/PRODUCTION_INTEGRATION.md](docs/PRODUCTION_INTEGRATION.md) for full enterprise integration documentation.

### 6. Docker Deployment
```bash
docker-compose up -d                                    # Leader API server
docker-compose -f docker-compose.adapters.yml up -d     # Adapter backends
```

---

## Load Stress Testing & Concurrency Benchmarks

LEADER provides a dedicated, high-concurrency simulation engine (`evals/stress_test.py`) to benchmark async firewalls, loop detectors, circuit breakers, and SQLite WAL persistence under massive production workloads.

```bash
python -m evals.stress_test --concurrency 50 --total-requests 200
```

| Test Scenario | Total Operations | Throughput (RPS) | Latency P50 | Latency P99 | Safety Efficacy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Benign Routing & Scoring** | 200 | 4,945.1 req/s | 0.16 ms | 0.55 ms | **100.0%** |
| **Concurrent Adversarial Attacks** | 200 | 5,644.1 req/s | 0.16 ms | 0.43 ms | **100.0%** |
| **Multi-Agent Drift & Loops** | 100 | 821.3 req/s | 1.01 ms | 8.27 ms | **100.0%** |
| **Circuit Breaker Exploit Tripping** | 200 | 7,723.5 req/s | 0.09 ms | 0.25 ms | **100.0%** |
| **SQLite WAL Persistence** | 200 | 4,904.9 req/s | 0.09 ms | 8.33 ms | **100.0%** |

> See [evals/STRESS_TEST_REPORT.md](evals/STRESS_TEST_REPORT.md) for detailed empirical benchmark breakdown.

---

## CLI Command Reference

```bash
leader run "prompt"              # Route and execute a task
leader run "prompt" --parallel   # Race all connected backends; fastest wins
leader backends                  # List all 30+ backends and connection status
leader ping                      # Health-check connected endpoints
leader stats                     # Show routing win-rates and latencies
leader feedback <task_id> <1-5>  # Submit manual score to update scoring weights
leader review [path]             # Autonomous code audit with diff preview
leader restore [path]            # Rollback to pre-review snapshot
leader setup <backend>           # Show installation instructions for a backend
leader serve                     # Start REST API server (default: port 8585)
leader init                      # Create ~/.leader/config.yaml
leader vscode-extension          # Generate VS Code / Cursor extension scaffold
```

---

## Supported Backends (30+)

| Category | Backends |
|----------|----------|
| **Orchestration** | Microsoft AutoGen, CrewAI, MetaGPT, TaskWeaver, BabyAGI |
| **LLM Providers** | Anthropic, OpenAI, OpenRouter, LiteLLM, AWS Bedrock, Google Vertex AI, Azure OpenAI |
| **Frameworks** | LangChain, LlamaIndex, Semantic Kernel, Griptape |
| **No-Code** | n8n, Make (Integromat), Zapier |
| **ML Platforms** | HuggingFace, Replicate, MLflow, Stability AI |
| **Agents** | AutoGPT, AgentGPT, OpenClaw, ZeroClaw, Hermes, NanoClaw |
| **Memory** | Mem0 |

---

## Test Suite

Leader ships with **193+ unit, integration, bridge, and load stress tests** covering:

- Multi-agent framework drop-in bridges (AutoGen & CrewAI)
- High-concurrency load stress testing (throughput, zero-drop rate, latency percentiles)
- Feedback loop detection (2-agent ping-pong, N-cycles, depth limits) & semantic drift tracking
- Safety circuit breakers & adversarial exploit isolation
- Semantic classifier edge cases (35+ parametrised prompts)
- Router evolved scoring with feedback loop & anti-reward gaming penalties
- Executor retry logic with side-effect safety guards
- File snapshot backup/restore with path traversal protection
- Auditor deduplication and malformed JSON handling
- Real HTTP integration tests against live FastAPI mock bridges

```bash
pip install -e ".[dev]"
pytest leader/ -v
```

---

## Security

* **Pre-Execution Firewall**: Real-time entropy, character anomaly, and prompt-injection signature inspection.
* **Autonomous Circuit Breaker**: Response scanning for sandbox escapes and credential leaks with automatic backend isolation.
* **Specification Gaming Prevention**: Alignment penalties decrement scoring for backends executing jailbreaks.
* **Config Isolation**: `leader init` restricts config file permissions to `600` (owner read/write only) on Unix.
* **Env-First Resolution**: API credentials are read from environment variables, preventing plain-text keys in config files.
* **Path Traversal Protection**: Snapshot restore validates all paths stay within the project root.
* **Side-Effect Safety**: Tasks in MESSAGING/AUTOMATION categories never retry to prevent duplicate delivery.
* **Structured Exception Hierarchy**: All errors use typed exceptions (`LeaderError`, `BackendNotFoundError`, etc.) for safe programmatic handling.

---

## Project Structure

```
leader/
├── __init__.py              # Public API surface & framework bridge exports
├── models.py                # Task, TaskResult, RouteDecision, ChainSession, ChainStep
├── exceptions.py            # Structured exception hierarchy
├── router.py                # Semantic classifier + evolved scoring + alignment penalties
├── registry.py              # Backend catalogue (30+ specs) + Registry
├── executor.py              # Dispatch, retry, fallback chain, parallel mode
├── firewall_middleware.py   # Async pre-execution firewall & anomaly detector
├── circuit_breaker.py       # Runtime safety circuit breaker & endpoint isolation
├── chain_diagnostics.py     # Feedback loop detector & semantic drift tracker
├── logger.py                # SQLite WAL persistence + schema migrations v1, v2, v3
├── config.py                # YAML config loader + env var resolution
├── sdk.py                   # Leader SDK entrypoint (run, run_chain, route)
├── cli.py                   # CLI commands (argparse)
├── server.py                # aiohttp REST API server
├── auditor.py               # Autonomous code review engine
├── file_utils.py            # Codebase gathering + snapshot backup/restore
├── setup_helper.py          # Backend installation guides
├── conftest.py              # Shared test fixtures
├── bridges/                 # AutoGen & CrewAI drop-in wrappers and callbacks
│   ├── __init__.py
│   ├── autogen.py           # LeaderGroupChatManager, LeaderSpeakerSelector
│   └── crewai.py            # LeaderCrew, LeaderStepCallback, LeaderTaskCallback
├── adapters/                # 31 backend adapters (base.py + implementations)
└── plugins/                 # OpenClaw skill + webhook plugins
```

---

## License & Maintainer

* **Created & maintained by Pradeep Kumar (Krish)** (pradeepkumar.workai@gmail.com)
* **GitHub**: [@pradeepkumar-ai-byte](https://github.com/pradeepkumar-ai-byte)
* **License**: MIT (Open Source)
