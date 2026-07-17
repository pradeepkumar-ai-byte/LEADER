"""
Leader – capability registry
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .models import TaskCategory


@dataclass
class BackendSpec:
    id: str
    display_name: str
    description: str
    strengths: list[TaskCategory]
    weaknesses: list[TaskCategory]
    homepage: str
    adapter_class: str
    connected: bool = False
    config: dict = field(default_factory=dict)


CATALOGUE: dict[str, BackendSpec] = {
    "direct_llm": BackendSpec(
        id="direct_llm",
        display_name="Direct LLM",
        description="Built-in adapter. Works with any API key (Anthropic, OpenAI, OpenRouter). No extra software needed. Leader's universal fallback.",
        strengths=[
            TaskCategory.RESEARCH,
            TaskCategory.CREATIVE,
            TaskCategory.CODING,
            TaskCategory.GENERAL,
        ],
        weaknesses=[TaskCategory.MESSAGING, TaskCategory.AUTOMATION],
        homepage="https://github.com/leader-agent/leader",
        adapter_class="leader.adapters.direct_llm.DirectLLMAdapter",
    ),
    "openclaw": BackendSpec(
        id="openclaw",
        display_name="OpenClaw",
        description="Full-featured personal AI assistant with 20+ platform integrations and a large skill marketplace.",
        strengths=[TaskCategory.MESSAGING, TaskCategory.AUTOMATION, TaskCategory.GENERAL],
        weaknesses=[TaskCategory.DATA],
        homepage="https://github.com/openclaw/openclaw",
        adapter_class="leader.adapters.openclaw.OpenClawAdapter",
    ),
    "hermes": BackendSpec(
        id="hermes",
        display_name="Hermes Agent",
        description="Self-improving agent (Nous Research) that writes reusable skills from its own task history.",
        strengths=[TaskCategory.AUTOMATION, TaskCategory.RESEARCH, TaskCategory.GENERAL],
        weaknesses=[TaskCategory.MESSAGING],
        homepage="https://github.com/NousResearch/hermes",
        adapter_class="leader.adapters.hermes.HermesAdapter",
    ),
    "zeroclaw": BackendSpec(
        id="zeroclaw",
        display_name="ZeroClaw",
        description="Lightweight Rust-based agent. Minimal overhead, ideal for constrained or headless environments.",
        strengths=[TaskCategory.CODING, TaskCategory.AUTOMATION],
        weaknesses=[TaskCategory.CREATIVE, TaskCategory.MULTIAGENT],
        homepage="https://github.com/zeroclaw-labs/zeroclaw",
        adapter_class="leader.adapters.zeroclaw.ZeroClawAdapter",
    ),
    "autogpt": BackendSpec(
        id="autogpt",
        display_name="AutoGPT",
        description="Autonomous AI agent that can perform complex multi-step tasks with memory and tool integration.",
        strengths=[TaskCategory.AUTOMATION, TaskCategory.RESEARCH, TaskCategory.CODING],
        weaknesses=[TaskCategory.MESSAGING],
        homepage="https://github.com/Significant-Gravitas/Auto-GPT",
        adapter_class="leader.adapters.autogpt.AutoGPTAdapter",
    ),
    "agentgpt": BackendSpec(
        id="agentgpt",
        display_name="AgentGPT",
        description="Web-based autonomous agent platform with goal-oriented task execution.",
        strengths=[TaskCategory.GENERAL, TaskCategory.AUTOMATION, TaskCategory.RESEARCH],
        weaknesses=[TaskCategory.MESSAGING],
        homepage="https://github.com/reworkd/AgentGPT",
        adapter_class="leader.adapters.agentgpt.AgentGPTAdapter",
    ),
    "langchain": BackendSpec(
        id="langchain",
        display_name="LangChain",
        description="Framework for developing applications powered by language models with agents and chains.",
        strengths=[TaskCategory.RESEARCH, TaskCategory.CODING, TaskCategory.GENERAL],
        weaknesses=[],
        homepage="https://github.com/hwchase17/langchain",
        adapter_class="leader.adapters.langchain.LangChainAdapter",
    ),
    "autogen": BackendSpec(
        id="autogen",
        display_name="Microsoft Autogen",
        description="Multi-agent conversation framework by Microsoft for enabling complex orchestration.",
        strengths=[TaskCategory.MULTIAGENT, TaskCategory.AUTOMATION, TaskCategory.RESEARCH],
        weaknesses=[],
        homepage="https://github.com/microsoft/autogen",
        adapter_class="leader.adapters.autogen.AutogenAdapter",
    ),
    "taskweaver": BackendSpec(
        id="taskweaver",
        display_name="TaskWeaver",
        description="LLM-powered workflow engine for composing and executing complex tasks.",
        strengths=[TaskCategory.AUTOMATION, TaskCategory.CODING, TaskCategory.GENERAL],
        weaknesses=[],
        homepage="https://github.com/microsoft/TaskWeaver",
        adapter_class="leader.adapters.taskweaver.TaskWeaverAdapter",
    ),
    "n8n": BackendSpec(
        id="n8n",
        display_name="n8n",
        description="Powerful no-code/low-code automation platform with 400+ integrations.",
        strengths=[TaskCategory.AUTOMATION, TaskCategory.MESSAGING, TaskCategory.DATA],
        weaknesses=[TaskCategory.CREATIVE],
        homepage="https://github.com/n8n-io/n8n",
        adapter_class="leader.adapters.n8n.N8NAdapter",
    ),
    "make": BackendSpec(
        id="make",
        display_name="Make (Integromat)",
        description="Visual automation platform for connecting apps and automating workflows.",
        strengths=[TaskCategory.AUTOMATION, TaskCategory.MESSAGING, TaskCategory.DATA],
        weaknesses=[TaskCategory.CREATIVE],
        homepage="https://www.make.com",
        adapter_class="leader.adapters.make.MakeAdapter",
    ),
    "zapier": BackendSpec(
        id="zapier",
        display_name="Zapier",
        description="No-code automation with 7000+ app integrations for business workflows.",
        strengths=[TaskCategory.AUTOMATION, TaskCategory.MESSAGING],
        weaknesses=[TaskCategory.CODING],
        homepage="https://www.zapier.com",
        adapter_class="leader.adapters.zapier.ZapierAdapter",
    ),
    "babyagi": BackendSpec(
        id="babyagi",
        display_name="BabyAGI",
        description="Lightweight autonomous AI agent that creates, prioritizes, and executes tasks.",
        strengths=[TaskCategory.AUTOMATION, TaskCategory.RESEARCH],
        weaknesses=[TaskCategory.MESSAGING],
        homepage="https://github.com/yoheinakajima/babyagi",
        adapter_class="leader.adapters.babyagi.BabyAGIAdapter",
    ),
    "metagpt": BackendSpec(
        id="metagpt",
        display_name="MetaGPT",
        description="Multi-agent framework that generates comprehensive project documentation and code.",
        strengths=[TaskCategory.CODING, TaskCategory.AUTOMATION, TaskCategory.MULTIAGENT],
        weaknesses=[],
        homepage="https://github.com/geekan/MetaGPT",
        adapter_class="leader.adapters.metagpt.MetaGPTAdapter",
    ),
    "griptape": BackendSpec(
        id="griptape",
        display_name="Griptape",
        description="Framework for building AI agents with guaranteed accuracy and safety.",
        strengths=[TaskCategory.AUTOMATION, TaskCategory.GENERAL, TaskCategory.CODING],
        weaknesses=[],
        homepage="https://github.com/griptape-ai/griptape",
        adapter_class="leader.adapters.griptape.GriptapeAdapter",
    ),
    "reworkdai": BackendSpec(
        id="reworkdai",
        display_name="Reworkd AI",
        description="Open-source autonomous AI agent platform with goal-driven execution.",
        strengths=[TaskCategory.AUTOMATION, TaskCategory.RESEARCH, TaskCategory.GENERAL],
        weaknesses=[],
        homepage="https://github.com/reworkd/reworkd",
        adapter_class="leader.adapters.reworkdai.ReworkdAIAdapter",
    ),
    "replicate": BackendSpec(
        id="replicate",
        display_name="Replicate",
        description="Run open-source ML models with a cloud API (Stable Diffusion, Llama2, etc).",
        strengths=[TaskCategory.CREATIVE, TaskCategory.CODING, TaskCategory.RESEARCH],
        weaknesses=[],
        homepage="https://replicate.com",
        adapter_class="leader.adapters.replicate.ReplicateAdapter",
    ),
    "huggingface": BackendSpec(
        id="huggingface",
        display_name="Hugging Face",
        description="Inference API and Hub for thousands of open-source AI models.",
        strengths=[TaskCategory.RESEARCH, TaskCategory.CODING, TaskCategory.GENERAL],
        weaknesses=[],
        homepage="https://huggingface.co",
        adapter_class="leader.adapters.huggingface.HuggingFaceAdapter",
    ),
    "litellm": BackendSpec(
        id="litellm",
        display_name="LiteLLM",
        description="Unified API for 50+ LLM providers (OpenAI, Claude, Llama, etc).",
        strengths=[TaskCategory.GENERAL, TaskCategory.RESEARCH, TaskCategory.CODING],
        weaknesses=[],
        homepage="https://github.com/BerriAI/litellm",
        adapter_class="leader.adapters.litellm.LiteLLMAdapter",
    ),
    "vertexai": BackendSpec(
        id="vertexai",
        display_name="Google Vertex AI",
        description="Google Cloud's unified AI platform with PaLM, CodeBison, and enterprise models.",
        strengths=[TaskCategory.CODING, TaskCategory.RESEARCH, TaskCategory.GENERAL],
        weaknesses=[],
        homepage="https://cloud.google.com/vertex-ai",
        adapter_class="leader.adapters.vertexai.VertexAIAdapter",
    ),
    "azureopenai": BackendSpec(
        id="azureopenai",
        display_name="Azure OpenAI",
        description="Enterprise-grade OpenAI models hosted on Microsoft Azure infrastructure.",
        strengths=[TaskCategory.GENERAL, TaskCategory.CODING, TaskCategory.CREATIVE],
        weaknesses=[],
        homepage="https://learn.microsoft.com/azure/ai-services/openai",
        adapter_class="leader.adapters.azureopenai.AzureOpenAIAdapter",
    ),
    "llamaindex": BackendSpec(
        id="llamaindex",
        display_name="LLamaIndex",
        description="Data framework for LLM applications with RAG (Retrieval Augmented Generation).",
        strengths=[TaskCategory.RESEARCH, TaskCategory.DATA, TaskCategory.GENERAL],
        weaknesses=[],
        homepage="https://github.com/jerryjliu/llama_index",
        adapter_class="leader.adapters.llamaindex.LlamaIndexAdapter",
    ),
    "bedrock": BackendSpec(
        id="bedrock",
        display_name="AWS Bedrock",
        description="Fully managed service to build and scale generative AI apps with foundation models.",
        strengths=[TaskCategory.GENERAL, TaskCategory.CODING, TaskCategory.CREATIVE],
        weaknesses=[],
        homepage="https://aws.amazon.com/bedrock",
        adapter_class="leader.adapters.bedrock.BedrockAdapter",
    ),
    "semantickernel": BackendSpec(
        id="semantickernel",
        display_name="Semantic Kernel",
        description="Microsoft's SDK for building intelligent apps with LLMs and embeddings.",
        strengths=[TaskCategory.GENERAL, TaskCategory.AUTOMATION, TaskCategory.CODING],
        weaknesses=[],
        homepage="https://github.com/microsoft/semantic-kernel",
        adapter_class="leader.adapters.semantickernel.SemanticKernelAdapter",
    ),
    "mem0": BackendSpec(
        id="mem0",
        display_name="Mem0",
        description="Platform for adding memory to AI applications (user preferences, interactions).",
        strengths=[TaskCategory.GENERAL, TaskCategory.RESEARCH],
        weaknesses=[],
        homepage="https://mem0.ai",
        adapter_class="leader.adapters.mem0.Mem0Adapter",
    ),
    "mlflow": BackendSpec(
        id="mlflow",
        display_name="MLflow",
        description="Platform for managing ML lifecycle including experimentation and model serving.",
        strengths=[TaskCategory.DATA, TaskCategory.CODING],
        weaknesses=[],
        homepage="https://github.com/mlflow/mlflow",
        adapter_class="leader.adapters.mlflow.MLflowAdapter",
    ),
    "stabilityai": BackendSpec(
        id="stabilityai",
        display_name="Stability AI",
        description="Image generation API (Stable Diffusion, SDXL) for creative content creation.",
        strengths=[TaskCategory.CREATIVE],
        weaknesses=[TaskCategory.CODING],
        homepage="https://stability.ai",
        adapter_class="leader.adapters.stabilityai.StabilityAIAdapter",
    ),
    "nanoclaw": BackendSpec(
        id="nanoclaw",
        display_name="NanoClaw",
        description="Security-first agent with OS-level container isolation per task.",
        strengths=[TaskCategory.CODING, TaskCategory.GENERAL],
        weaknesses=[TaskCategory.MESSAGING],
        homepage="https://github.com/nanocoai/nanoclaw",
        adapter_class="leader.adapters.generic_rest.GenericRestAdapter",
    ),
    "crewai": BackendSpec(
        id="crewai",
        display_name="CrewAI",
        description="Multi-agent orchestration framework with role-based agent teams.",
        strengths=[TaskCategory.MULTIAGENT, TaskCategory.RESEARCH, TaskCategory.CREATIVE],
        weaknesses=[TaskCategory.MESSAGING],
        homepage="https://github.com/joaomdmoura/crewAI",
        adapter_class="leader.adapters.crewai.CrewAIAdapter",
    ),
    "generic": BackendSpec(
        id="generic",
        display_name="Generic REST backend",
        description="Any backend reachable via a REST API. Add your own.",
        strengths=[TaskCategory.GENERAL],
        weaknesses=[],
        homepage="",
        adapter_class="leader.adapters.generic_rest.GenericRestAdapter",
    ),
}


import copy


class Registry:
    def __init__(self, extra: dict[str, BackendSpec] | None = None):
        # Deep copy CATALOGUE to prevent mutating the global template specs
        self._specs: dict[str, BackendSpec] = {k: copy.deepcopy(v) for k, v in CATALOGUE.items()}
        if extra:
            self._specs.update(extra)

    def register(self, spec: BackendSpec) -> None:
        self._specs[spec.id] = spec

    def get(self, backend_id: str) -> Optional[BackendSpec]:
        return self._specs.get(backend_id)

    def connected(self) -> list[BackendSpec]:
        """Only backends that are marked connected AND have usable config."""
        result = []
        for s in self._specs.values():
            if not s.connected:
                continue
            if s.id == "direct_llm":
                if s.config.get("provider") and s.config.get("api_key"):
                    result.append(s)
            elif s.config.get("base_url") or s.config.get("binary") or s.config:
                result.append(s)
        return result

    def all(self) -> list[BackendSpec]:
        return list(self._specs.values())

    def best_for(self, category: TaskCategory, connected_only: bool = True) -> list[BackendSpec]:
        pool = self.connected() if connected_only else self.all()

        def score(spec: BackendSpec) -> int:
            if category in spec.strengths:
                return 2
            if category in spec.weaknesses:
                return 0
            return 1

        return sorted(pool, key=score, reverse=True)

    def missing_specialists(self, category: TaskCategory) -> list[BackendSpec]:
        connected_ids = {s.id for s in self.connected()}
        return [
            s
            for s in self._specs.values()
            if s.id not in connected_ids
            and s.id != "direct_llm"  # universal fallback, not a specialist
            and s.id != "generic"
            and category in s.strengths
        ]
