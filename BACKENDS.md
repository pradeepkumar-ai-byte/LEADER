# BACKENDS.md

# Leader – 30+ Supported Backends

Leader can route tasks to any of these popular AI & automation platforms. Simply add them to `~/.leader/config.yaml` and they'll be automatically available.

## AI Agent Frameworks (8)

| Backend | Best For | Homepage |
|---------|----------|----------|
| **OpenClaw** | Personal AI assistant with skill marketplace | https://github.com/openclaw/openclaw |
| **AutoGPT** | Autonomous multi-step task execution | https://github.com/Significant-Gravitas/Auto-GPT |
| **AgentGPT** | Web-based autonomous goals | https://github.com/reworkd/AgentGPT |
| **BabyAGI** | Lightweight autonomous agents | https://github.com/yoheinakajima/babyagi |
| **Hermes Agent** | Self-improving agent with skill learning | https://github.com/NousResearch/hermes |
| **ZeroClaw** | Minimal overhead Rust agent | https://github.com/zeroclaw/zeroclaw |
| **NanoClaw** | Security-first with container isolation | https://github.com/nanoclaw/nanoclaw |
| **Reworkd AI** | Goal-driven autonomous execution | https://github.com/reworkd/reworkd |

## Multi-Agent Orchestration (4)

| Backend | Best For | Homepage |
|---------|----------|----------|
| **Microsoft Autogen** | Multi-agent conversations & coordination | https://github.com/microsoft/autogen |
| **CrewAI** | Role-based agent teams | https://github.com/joaomdmoura/crewAI |
| **MetaGPT** | Technical project generation | https://github.com/geekan/MetaGPT |
| **TaskWeaver** | LLM-powered workflow engine | https://github.com/microsoft/TaskWeaver |

## LLM & Language Models (7)

| Backend | Best For | Homepage |
|---------|----------|----------|
| **Direct LLM** | Built-in: Anthropic, OpenAI, OpenRouter | https://github.com/leader-agent/leader |
| **LiteLLM** | Unified 50+ LLM provider proxy | https://github.com/BerriAI/litellm |
| **Azure OpenAI** | Enterprise Azure-hosted models | https://learn.microsoft.com/azure/ai-services/openai |
| **Google Vertex AI** | Google's PaLM, CodeBison models | https://cloud.google.com/vertex-ai |
| **AWS Bedrock** | Claude, Llama2 on AWS | https://aws.amazon.com/bedrock |
| **Hugging Face** | 100k+ open-source models | https://huggingface.co |
| **Replicate** | Stable Diffusion, Llama2, etc | https://replicate.com |

## Development Frameworks (4)

| Backend | Best For | Homepage |
|---------|----------|----------|
| **LangChain** | Building LLM applications with chains | https://github.com/hwchase17/langchain |
| **LLamaIndex** | RAG (Retrieval Augmented Generation) | https://github.com/jerryjliu/llama_index |
| **Semantic Kernel** | Microsoft's intelligent apps SDK | https://github.com/microsoft/semantic-kernel |
| **Griptape** | Safe AI agents with guaranteed accuracy | https://github.com/griptape-ai/griptape |

## No-Code Automation (3)

| Backend | Best For | Homepage |
|---------|----------|----------|
| **n8n** | 400+ workflow integrations | https://github.com/n8n-io/n8n |
| **Make (Integromat)** | Visual automation platform | https://www.make.com |
| **Zapier** | 7000+ app integrations | https://www.zapier.com |

## Specialized Services (3)

| Backend | Best For | Homepage |
|---------|----------|----------|
| **Stability AI** | Image generation (Stable Diffusion) | https://stability.ai |
| **Mem0** | Persistent memory for AI apps | https://mem0.ai |
| **MLflow** | ML model management & serving | https://github.com/mlflow/mlflow |

## Generic REST (1)

| Backend | Best For | Homepage |
|---------|----------|----------|
| **Generic REST** | Any backend with REST API | N/A |

---

## How to Add a Backend

Edit `~/.leader/config.yaml`:

```yaml
backends:
  autogpt:
    base_url: http://localhost:8000
    model: gpt-4
    max_iterations: 5
  
  langchain:
    base_url: http://localhost:8001
    agent_type: conversational
  
  n8n:
    base_url: http://localhost:5678
    workflow_id: my-workflow-123
  
  directllm:
    provider: anthropic
    api_key: sk-ant-...
    model: claude-opus
```

Then run: `leader run "your task here"`

---

## Strengths & Weaknesses

Leader learns which backends perform best for each task category:
- **messaging** - OpenClaw, n8n, Make, Zapier
- **coding** - MetaGPT, Autogen, LangChain, ZeroClaw
- **research** - LangChain, LLamaIndex, LiteLLM, Hermes
- **creative** - Direct LLM, Replicate, Stability AI
- **data** - MLflow, LLamaIndex, n8n
- **automation** - n8n, Make, Zapier, TaskWeaver
- **multiagent** - Autogen, CrewAI, MetaGPT, Griptape
- **general** - Any backend will do

---

## Integration Examples

### Use multiple backends simultaneously (parallel mode):
```bash
leader run "write and test a python script" --parallel
```
Leader will send to all connected backends and use the fastest result.

### Route by category:
```bash
leader run "generate 10 stock images" --category creative
```

### See performance history:
```bash
leader stats
```

This shows which backends win most for each task type, helping Leader learn.

