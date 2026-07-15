<p align="center">
  <img src="assets/banner.jpg" alt="Leader Banner" width="300"/>
</p>

<h1 align="center">Leader</h1>

<p align="center">
  <strong>The invisible intelligence layer that lives inside your tools — not beside them.</strong>
</p>

<p align="center">
  <a href="https://github.com/pradeepkumar-ai-byte/LEADER/actions"><img src="https://github.com/pradeepkumar-ai-byte/LEADER/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/leader-agent/"><img src="https://img.shields.io/pypi/v/leader-agent?color=blue" alt="PyPI"></a>
  <a href="https://github.com/pradeepkumar-ai-byte/LEADER/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python"></a>
  <a href="https://hub.docker.com/"><img src="https://img.shields.io/badge/docker-ready-blue" alt="Docker"></a>
<a href="https://github.com/sponsors/pradeepkumar-ai-byte"><img src="https://img.shields.io/badge/sponsor-%E2%9D%A4-ff69b4" alt="Sponsor"></a>
---

Leader has no model. No agent runtime. No dashboard of its own. It **runs inside** whatever tool you already use — OpenClaw, VS Code, Cursor, n8n, or any app — and silently routes every task to the best AI backend. You never leave your tool. Leader is invisible.

```
┌──────────────────────────────────┐
│  Your Tool (OpenClaw / VS Code)  │
│    └── Leader (invisible)        │──▶ Best backend chosen automatically
└──────────────────────────────────┘
```

---

## Why Leader Exists

Most AI tools do one of two things:
- **Route between LLM models** (OpenAI ↔ Claude ↔ DeepSeek) — e.g. LiteLLM, OpenRouter
- **Build a single agent runtime** (OpenClaw, AutoGPT, CrewAI)

**Leader is neither.** It's the layer that sits *above* all of them — and it runs *inside* whatever tool you already use. If you have OpenClaw for messaging, n8n for automation, and LangChain for research — Leader picks the right one for each task, learns from your results, and gets smarter over time.

Nobody else has built this.

---

## 5 Ways to Use Leader

### 1. 🐍 Python SDK (3 lines)

```python
from leader import Leader

leader = Leader()
result = await leader.run("summarize the latest AI news")

print(result.output)       # The response
print(result.backend_id)   # Which backend handled it
```

### 2. 🌐 REST API Server

```bash
leader serve --port 8585
```

Now **any tool, any language** can call Leader:

```bash
curl -X POST http://localhost:8585/api/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "write a python sort function", "category": "coding"}'
```

**Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/run` | Route and execute a task |
| POST | `/api/route` | Route only (no execution) |
| GET | `/api/backends` | List all backends and status |
| GET | `/api/stats` | Routing performance stats |
| POST | `/api/feedback` | Submit user feedback |
| GET | `/api/health` | Health check |

### 3. 🔌 Plugin System (embed inside any app)

**Inside OpenClaw:**
```python
from leader.plugins import OpenClawPlugin

plugin = OpenClawPlugin()
await plugin.install(openclaw_app)
# Leader is now a skill inside OpenClaw's dashboard
```

**Inside any aiohttp web app:**
```python
from leader.middleware import mount_leader

app = web.Application()
mount_leader(app, prefix="/leader")
# Your app now has Leader's API at /leader/api/run
```

**Webhook for n8n / Make / Zapier:**
```python
from leader.plugins import WebhookPlugin

plugin = WebhookPlugin()
await plugin.install(app)
# POST /webhook/leader with {"prompt": "..."} — works with any automation tool
```

### 4. 💻 VS Code / Cursor Extension

```bash
leader vscode-extension --output ./leader-vscode
```

Generates a ready-to-install VS Code extension with:
- **Leader: Run Task** command in the command palette
- **Leader: Run Selected Text** — highlight code and route it
- **Leader: Show Backends** — see what's connected

### 5. 🐳 Docker (one-command deploy)

```bash
docker-compose up -d
# Leader API is now running at http://localhost:8585
```

Or build manually:
```bash
docker build -t leader .
docker run -p 8585:8585 -e ANTHROPIC_API_KEY=sk-ant-... leader
```

---

## CLI Reference

```bash
leader init                         # create ~/.leader/config.yaml
leader run "your task"              # route and execute
leader run "task" --category coding # explicit category
leader run "task" --parallel        # race all backends
leader serve                       # start REST API server
leader serve --port 9000            # custom port
leader backends                    # list all backends
leader ping                        # health-check connected backends
leader stats                       # view routing history
leader feedback <task_id> 4        # rate a result (helps learning)
leader vscode-extension            # generate VS Code extension
```

---

## Configuration

Edit `~/.leader/config.yaml` or use environment variables:

```bash
# Environment variables (recommended — keeps secrets off disk)
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-proj-..."
export OPENROUTER_API_KEY="sk-or-..."
export LEADER_API_KEY_OPENCLAW="your-key"
```

```yaml
# Config file
backends:
  direct_llm:
    provider: anthropic
    # api_key auto-resolved from ANTHROPIC_API_KEY env var

  openclaw:
    base_url: http://localhost:8888

  my_custom_agent:
    display_name: My Agent
    strengths: [coding, automation]
    base_url: http://internal.company.com/agent
    endpoint: /api/run
    prompt_field: query
    output_field: answer
```

---

## Supported Backends (30+)

| Category | Backends |
|----------|----------|
| **AI Agents** | OpenClaw, AutoGPT, AgentGPT, BabyAGI, Hermes, ZeroClaw, NanoClaw, Reworkd AI |
| **Multi-Agent** | Microsoft Autogen, CrewAI, MetaGPT, TaskWeaver |
| **LLM Providers** | Direct LLM (Claude/GPT/OpenRouter), LiteLLM, Azure OpenAI, Vertex AI, AWS Bedrock, HuggingFace, Replicate |
| **Frameworks** | LangChain, LlamaIndex, Semantic Kernel, Griptape |
| **No-Code Automation** | n8n, Make (Integromat), Zapier |
| **Specialized** | Stability AI, Mem0, MLflow |

See [BACKENDS.md](BACKENDS.md) for detailed configuration for each.

---

## How Leader Learns

Every task is logged to `~/.leader/history.db`. The router blends:

- **Static knowledge** (40%) — what each backend is known to be good at
- **Your history** (60%) — actual win rates per backend per task category

The more tasks Leader runs, the better its routing gets — specifically for your workload.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   HOST APPLICATION                   │
│  (OpenClaw, VS Code, Cursor, your app, CLI, etc.)   │
│                                                      │
│   ┌──────────────────────────────────────────────┐   │
│   │            Leader (invisible)                 │   │
│   │                                              │   │
│   │  ┌─────────┐  ┌────────┐  ┌──────────────┐  │   │
│   │  │ Router  │→ │Executor│→ │   Adapters   │  │   │
│   │  │(classify│  │(async, │  │ (30+ built-  │──│───│──▶ Backends
│   │  │ + score)│  │fallback│  │  in plugins) │  │   │
│   │  └─────────┘  │parallel│  └──────────────┘  │   │
│   │       ↑       └────────┘                     │   │
│   │  ┌─────────┐                                 │   │
│   │  │ Logger  │  ← learns from results          │   │
│   │  └─────────┘                                 │   │
│   └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

---

## Support & Maintenance

Leader is **open source with no paid support**. We provide it as-is:
- Bug reports: Best-effort help via GitHub Issues
- Feature requests: You can fork and add them yourself
- Urgent production needs: Consider maintaining your own fork

The MIT license includes no warranty—you're responsible for your deployment.

### Voluntary Support

If Leader saves you time or money, consider supporting the author:
- **[GitHub Sponsors](https://github.com/sponsors/pradeepkumar-ai-byte)** — Monthly support
- **[One-time donation](https://ko-fi.com/pradeepkumar)** — Pay what you want

100% optional. Leader works the same either way.

---

## Security

- **Environment variable priority** — API keys resolved from env vars first
- **Restricted file permissions** — config secured to owner-only on Unix/macOS
- **No credential logging** — keys never written to history or logs
- **Schema migrations** — database versioned, upgrades never break data

See [SECURITY.md](SECURITY.md) for the full policy.

---

## Contributing

```bash
git clone https://github.com/pradeepkumar-ai-byte/LEADER.git
cd LEADER
pip install -e ".[dev]"
pytest leader/test_leader.py -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## Contact

**Created & maintained by Krish**

- GitHub: [@pradeepkumar-ai-byte](https://github.com/pradeepkumar-ai-byte)
- Repository: [github.com/pradeepkumar-ai-byte/LEADER](https://github.com/pradeepkumar-ai-byte/LEADER)
- Issues: [Report a bug or request a feature](https://github.com/pradeepkumar-ai-byte/LEADER/issues)

---

## License

MIT — free for everyone. See [LICENSE](LICENSE).
