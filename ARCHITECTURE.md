# Architecture

> System design document for the Leader routing engine.
> Last updated: v0.2.0

---

## Overview

Leader is a **credential-aware task router** that classifies incoming prompts, scores available backends using a hybrid evolutionary algorithm, and dispatches tasks with automatic fallback and retry logic. It sits above agent platforms (AutoGen, CrewAI, OpenClaw), LLM providers (Anthropic, OpenAI), and automation tools (n8n, Zapier).

---

## Dispatch Pipeline

```mermaid
flowchart TD
    A["User Prompt"] --> B["Router.classify()"]
    B --> C{"Category Detected?"}
    C -->|Yes| D["Router._evolved_score()"]
    C -->|No| E["Default: GENERAL"]
    E --> D
    D --> F["Registry.connected()"]
    F --> G["Rank backends by score"]
    G --> H["RouteDecision\n(primary + fallback_chain)"]
    H --> I["Executor.run()"]
    I --> J{"Primary succeeds?"}
    J -->|Yes| K["TaskResult ✓"]
    J -->|No| L["Try fallback chain"]
    L --> M{"Any fallback succeeds?"}
    M -->|Yes| K
    M -->|No| N["TaskResult ✗\n(all backends failed)"]
    K --> O["TaskLogger.log_result()"]
    N --> O
    O --> P["SQLite history\n(feeds back into scoring)"]

    style A fill:#4A90D9,color:#fff
    style K fill:#27AE60,color:#fff
    style N fill:#E74C3C,color:#fff
    style P fill:#8E44AD,color:#fff
```

---

## Scoring Algorithm

The router uses a **three-component hybrid score** that evolves with usage:

```mermaid
flowchart LR
    subgraph Inputs
        S["Static Affinity\n(strengths/weaknesses)"]
        W["Historical Win Rate\n(SQLite task log)"]
        F["Human Feedback\n(1-5 ratings → 0-1)"]
        L["Avg Latency\n(ms → penalty)"]
    end

    subgraph Formula
        S -->|"× 0.3"| SCORE
        W -->|"× 0.5 × 2"| SCORE
        F -->|"× 0.2 × 2"| SCORE
        L -->|"− min(lat/10000, 0.5)"| SCORE
    end

    SCORE["Final Score"] --> R["Ranked Backend List"]

    style SCORE fill:#F39C12,color:#fff
    style R fill:#27AE60,color:#fff
```

| Component | Weight | Data Source | Fallback |
|-----------|--------|-------------|----------|
| Historical Win Rate | 50% | `TaskLogger.win_rates()` → SQLite | Uses static score if no history |
| Static Affinity | 30% | `BackendSpec.strengths` / `.weaknesses` | Always available |
| Human Feedback | 20% | `TaskLogger.feedback_scores()` → SQLite | Uses static score if no feedback |
| Latency Penalty | −0.5 max | `TaskLogger.avg_latency()` → SQLite | 0 if no data |

---

## Component Architecture

```mermaid
graph TB
    subgraph "Public API"
        SDK["sdk.py\nLeader class"]
        CLI["cli.py\nargparse commands"]
        SRV["server.py\naiohttp REST API"]
        MW["middleware.py\naiohttp middleware"]
    end

    subgraph "Core Engine"
        RTR["router.py\nclassify() + _evolved_score()"]
        REG["registry.py\nBackendSpec + CATALOGUE"]
        EXE["executor.py\nretry + fallback + parallel"]
        LOG["logger.py\nSQLite + migrations"]
        MDL["models.py\nTask, TaskResult, RouteDecision"]
        EXC["exceptions.py\nLeaderError hierarchy"]
    end

    subgraph "Adapters (31 files)"
        BASE["base.py\nBaseAdapter ABC"]
        DLM["direct_llm.py\nAnthropic/OpenAI/OpenRouter"]
        REST["hermes.py, babyagi.py, ...\nREST HTTP adapters"]
        BIN["openclaw.py, zeroclaw.py\nBinary subprocess adapters"]
    end

    subgraph "Tools"
        AUD["auditor.py\nAutonomous code review"]
        FU["file_utils.py\nGather + snapshot + restore"]
        SH["setup_helper.py\nBackend install guides"]
        CFG["config.py\nYAML + env var loader"]
    end

    SDK --> RTR
    SDK --> EXE
    SDK --> LOG
    CLI --> RTR
    CLI --> EXE
    CLI --> AUD
    SRV --> RTR
    SRV --> EXE
    RTR --> REG
    RTR --> LOG
    EXE --> BASE
    BASE --> DLM
    BASE --> REST
    BASE --> BIN
    AUD --> FU
    AUD --> EXE

    style SDK fill:#3498DB,color:#fff
    style RTR fill:#E67E22,color:#fff
    style EXE fill:#E74C3C,color:#fff
    style LOG fill:#8E44AD,color:#fff
    style BASE fill:#2ECC71,color:#fff
```

---

## Adapter Type Hierarchy

```mermaid
classDiagram
    class BaseAdapter {
        <<abstract>>
        +config: dict
        +id: str
        +is_available()* bool
        +run(task: Task)* TaskResult
        +health_check() bool
    }

    class DirectLLMAdapter {
        Built-in LLM provider
        Anthropic / OpenAI / OpenRouter
        Real cost calculation from tokens
    }

    class OpenClawAdapter {
        Binary subprocess adapter
        Shells out to local binary
    }

    class ZeroClawAdapter {
        Binary subprocess adapter
        Rust-based CLI
    }

    class HermesAdapter {
        REST HTTP adapter
        POST /api/run
    }

    class GenericRestAdapter {
        REST HTTP adapter
        Any REST endpoint
    }

    BaseAdapter <|-- DirectLLMAdapter : SDK/Native
    BaseAdapter <|-- OpenClawAdapter : Binary
    BaseAdapter <|-- ZeroClawAdapter : Binary
    BaseAdapter <|-- HermesAdapter : REST HTTP
    BaseAdapter <|-- GenericRestAdapter : REST HTTP
```

---

## Exception Hierarchy

```mermaid
classDiagram
    class LeaderError {
        Base exception
    }
    class ConfigurationError
    class BackendNotFoundError {
        +backend_id: str
    }
    class BackendUnavailableError {
        +backend_id: str
        +reason: str
    }
    class NoBackendsConnectedError
    class AdapterLoadError {
        +adapter_class: str
    }
    class TaskExecutionError {
        +task_id: str
        +errors: list
    }
    class ClassificationError
    class SnapshotError

    LeaderError <|-- ConfigurationError
    LeaderError <|-- BackendNotFoundError
    LeaderError <|-- BackendUnavailableError
    LeaderError <|-- NoBackendsConnectedError
    LeaderError <|-- AdapterLoadError
    LeaderError <|-- TaskExecutionError
    LeaderError <|-- ClassificationError
    LeaderError <|-- SnapshotError
```

---

## Data Model

```mermaid
erDiagram
    DISPATCHES {
        text task_id PK
        text category
        int prompt_len
        text backend_id
        text rationale
        real timestamp
    }

    RESULTS {
        text task_id PK, FK
        text backend_id
        int success
        real latency_ms
        real cost_usd
        text error
        real timestamp
    }

    FEEDBACK {
        text task_id FK
        int rating
        text comment
        real timestamp
    }

    DISPATCHES ||--o| RESULTS : "1:1"
    DISPATCHES ||--o{ FEEDBACK : "1:N"
```

---

## Retry & Side-Effect Safety

The executor implements **smart retry logic** with safety guards:

| Behaviour | Condition |
|-----------|-----------|
| **Retry with backoff** | Transient errors (`TimeoutError`, `ConnectionError`, `OSError`) on safe categories |
| **Fail immediately** | Programming errors (`TypeError`, `ValueError`, `KeyError`) |
| **Never retry** | Tasks in `MESSAGING` or `AUTOMATION` categories (side-effect risk) |
| **Max attempts** | 3 retries with exponential backoff (1.0s × 1.5^attempt) |

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| `uuid4` for `task_id` | Millisecond timestamps collide under parallel execution |
| Deep copy of `CATALOGUE` in Registry | Prevents tests and concurrent users from mutating shared state |
| TF-IDF bi-gram classifier | Compound phrases ("bug report") must outweigh single keywords ("write") |
| Suppression penalties | Prevents cross-category false positives (e.g. "write code" ≠ CREATIVE) |
| 50/30/20 scoring blend | Balances learning from history with static knowledge and human override |
| Path traversal checks | `restore_snapshot` validates all paths resolve within the project root |
| Side-effect category guard | MESSAGING/AUTOMATION tasks never retry to prevent duplicate delivery |
| Structured exception hierarchy | All errors use typed exceptions for safe programmatic error handling |

---

## Directory Structure

```
LEADER/
├── leader/                          # Main package
│   ├── __init__.py                  # Public API + version
│   ├── models.py                    # Task, TaskResult, RouteDecision
│   ├── exceptions.py                # LeaderError hierarchy
│   ├── router.py                    # Semantic classifier + evolved scoring
│   ├── registry.py                  # 30-backend catalogue + Registry
│   ├── executor.py                  # Dispatch + retry + fallback + parallel
│   ├── logger.py                    # SQLite persistence + migrations
│   ├── config.py                    # YAML + env var config loader
│   ├── sdk.py                       # Leader class (SDK entry point)
│   ├── cli.py                       # CLI commands
│   ├── server.py                    # aiohttp REST API
│   ├── middleware.py                # Drop-in aiohttp middleware
│   ├── auditor.py                   # Autonomous code review engine
│   ├── file_utils.py                # Codebase gathering + snapshots
│   ├── setup_helper.py              # Backend installation guides
│   ├── conftest.py                  # Shared test fixtures
│   ├── adapters/                    # 31 backend adapters
│   │   ├── base.py                  # BaseAdapter ABC
│   │   ├── direct_llm.py            # Built-in LLM adapter
│   │   └── ...                      # REST + binary adapters
│   └── plugins/                     # OpenClaw skill + webhooks
├── bridges/
│   └── agent_bridge.py              # FastAPI mock bridge for testing
├── .github/
│   ├── workflows/ci.yml             # Test + lint + security CI
│   └── workflows/publish.yml        # PyPI publish on release
├── pyproject.toml                   # Package metadata + tool config
├── Dockerfile                       # Container deployment
├── docker-compose.yml               # Leader API container
└── docker-compose.adapters.yml      # Adapter backend containers
```
