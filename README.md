<p align="center">
  <img src="assets/banner.jpg" alt="Leader Logo" width="320"/>
</p>

<h1 align="center">Leader</h1>

<p align="center">
  <strong>The Invisible Conductor for the Multi-Agent Era.</strong>
</p>

<p align="center">
  <a href="https://github.com/pradeepkumar-ai-byte/LEADER/actions"><img src="https://github.com/pradeepkumar-ai-byte/LEADER/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/leader-agent/"><img src="https://img.shields.io/pypi/v/leader-agent?color=blue" alt="PyPI"></a>
  <a href="https://github.com/pradeepkumar-ai-byte/LEADER/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python"></a>
  <a href="https://hub.docker.com/"><img src="https://img.shields.io/badge/docker-ready-blue" alt="Docker"></a>
</p>

---

## 📖 The Story

### The Silent Crisis of the Agent Era
We were promised a world of autonomous AI agents. So, we built them. 
* We set up **OpenClaw** to handle our team messages and notifications.
* We spun up **Microsoft AutoGen** to coordinate multi-agent developer squads.
* We wrote custom **LangChain** pipelines for deep academic research.
* We built lightweight **ZeroClaw** engines in Rust for low-overhead scripting.
* We configured **n8n** and **Zapier** to glue our business apps together.

But then, we hit the wall. 

Every time we had a new task, we had to manually decide: *Which tool should I open? Which agent is online? Who is actually good at this specific task?* 

We tried writing static `if/else` scripts to route tasks, but they broke the moment a server went down or an API key expired. We ended up copying and pasting prompts between five different dashboards. The "automation" era became a chore of manual orchestration.

### Enter Leader: The Invisible Conductor
**Leader does not build agents. Leader has no models. Leader has no opinions about which platform is best — until it has seen enough of yours to learn.**

Leader is a credential-aware, learning router that sits *above* your entire AI ecosystem. It acts as the single gateway. You send a task to Leader; Leader inspects what is currently online, scores their historical performance, dispatches the task, manages fallbacks if the primary agent fails, and silently returns the result.

It turns a fragmented mess of disconnected AI tools into a single, unified, self-evolving system. 

---

## ⚡ The Magic in Action

When you run a task through Leader, three things happen instantly:

```
                  "Write a Python script to parse this CSV"
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. CREDENTIAL-AWARE FILTERING                                           │
│    Leader checks active API keys & base URLs.                           │
│    Only connected/online backends are allowed to play.                  │
└─────────────────────────────────────┬───────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 2. EVOLVED TASK SCORING                                                 │
│    Leader classifies the task as "coding" and scores available agents:  │
│    • ZeroClaw (Static Strength: 2.0 | Win Rate: 92% | Speed: 150ms)     │
│    • OpenClaw (Static Strength: 1.0 | Win Rate: 40% | Speed: 800ms)     │
│    • Direct LLM (Fallback)                                              │
└─────────────────────────────────────┬───────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 3. DISPATCH & REINFORCEMENT                                             │
│    • Dispatch: ZeroClaw executes the task.                              │
│    • Fallback: If ZeroClaw fails, AutoGen is immediately called.        │
│    • Learn: Leader records the speed, outcome, and your feedback.        │
└─────────────────────────────────────────────────────────────────────────┘
```

> [!NOTE]
> **Why this is different:** Other routers (like LiteLLM) route between raw *models* (GPT-4 vs Claude). **Leader is the first router built for complete *agent platforms* and *workflows* (OpenClaw, AutoGen, n8n).**

---

## 🚀 Get Started in 60 Seconds

### Install
```bash
pip install leader-agent
leader init        # Creates secure config at ~/.leader/config.yaml
```

### Configure (Zero-Disk-Secrets)
Leader is designed to run securely. Instead of writing sensitive keys to files, you can set them as environment variables. Leader reads them automatically:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-proj-..."
export LEADER_API_KEY_OPENCLAW="your-openclaw-key"
```

---

## 🛠️ Five Ways to Embed Leader

Leader is not a standalone silo. It is designed to live **inside** your existing workflow.

### 1. 🐍 Embed in Python (SDK)
Add intelligent routing to any Python script in three lines:
```python
from leader import Leader

leader = Leader()
result = await leader.run("coordinate three agents to write a PR review")

print(f"Executed by: {result.backend_id} in {result.latency_ms}ms")
print(result.output)
```

### 2. 🔌 Embed in OpenClaw (Dashboard Plugin)
Mount Leader directly inside your OpenClaw server so you can use Leader's routing logic as an OpenClaw skill:
```python
from leader.plugins import OpenClawPlugin

plugin = OpenClawPlugin()
await plugin.install(openclaw_app)  # Leader is now an active OpenClaw skill!
```

### 3. 🌐 Spin Up a REST API Server
Expose Leader over HTTP so any tool, shell script, or microservice can route tasks:
```bash
leader serve --port 8585
```
```bash
curl -X POST http://localhost:8585/api/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "send a slack notification to engineering", "parallel": true}'
```

### 4. 💻 Route Directly from VS Code / Cursor
Generate a fully packaged VS Code extension template configured to talk to your local Leader server:
```bash
leader vscode-extension --output ./leader-extension
```
*Gives you command palette shortcuts to highlight code, press a button, and route it to your best local coding agent.*

### 🐳 5. Containerized Deployment (Docker)
Run the Leader API server as a background service with persistent logging:
```bash
docker-compose up -d
```

---

## 📊 CLI Reference

Run these commands in your terminal to manage your orchestrator:

| Command | Action |
|---------|--------|
| `leader init` | Scaffolds the configuration file |
| `leader run "prompt"` | Routes and executes a task |
| `leader run "prompt" --parallel` | Races all connected backends; fastest success wins |
| `leader backends` | Lists all 30+ supported backends and connection status |
| `leader ping` | Health-checks all online webhooks and endpoints |
| `leader stats` | Shows historical win-rates and average latency per backend |
| `leader feedback <task_id> <1-5>` | Submits a manual score, dynamically shaping the routing brain |
| `leader serve` | Launches the REST API server |

---

## 🔌 Supported Backends (30+)

Leader ships with adapters for the industry's leading platforms out of the box:

| Category | Supported Adaptors |
|----------|-------------------|
| **AI Agents** | OpenClaw, AutoGPT, AgentGPT, BabyAGI, Hermes, ZeroClaw, NanoClaw, Reworkd AI |
| **Multi-Agent** | Microsoft Autogen, CrewAI, MetaGPT, TaskWeaver |
| **LLM Providers** | Direct LLM (Anthropic/OpenAI/OpenRouter), LiteLLM, Azure OpenAI, Vertex AI, AWS Bedrock, HuggingFace, Replicate |
| **Frameworks** | LangChain, LlamaIndex, Semantic Kernel, Griptape |
| **Automation** | n8n, Make (Integromat), Zapier |
| **Memory & Ops** | Stability AI, Mem0, MLflow |

---

## 🔒 Security & Hardening

* **Owner-Only Permissions**: Config files are initialized with `600` permissions (readable only by your system user) to protect local keys.
* **Database Migrations**: Uses SQLite `PRAGMA user_version` schema management so future updates never corrupt your run history.
* **No Credential Leaks**: API keys are filtered out of all database logs, outputs, and CLI print statements.

---

## 🤝 Contributing

We welcome adapters for new agent platforms! Check out [CONTRIBUTING.md](CONTRIBUTING.md) for local setup instructions and template files.

```bash
git clone https://github.com/pradeepkumar-ai-byte/LEADER.git
cd LEADER
pip install -e ".[dev]"
pytest leader/ -v
```

---

## ✉️ Maintainer

**Created & maintained by Krish**

* GitHub: [@pradeepkumar-ai-byte](https://github.com/pradeepkumar-ai-byte)
* Issues: [Open an Issue](https://github.com/pradeepkumar-ai-byte/LEADER/issues)
* Email: pradeepkumar.ai.byte@gmail.com

---

## 📄 License

MIT © 2026 Krish. Free and open source forever.
