"""
Leader – adapter plugins for various agent backends
"""

from .agentgpt import AgentGPTAdapter
from .autogen import AutogenAdapter
from .autogpt import AutoGPTAdapter
from .azureopenai import AzureOpenAIAdapter
from .babyagi import BabyAGIAdapter
from .base import BaseAdapter
from .bedrock import BedrockAdapter
from .crewai import CrewAIAdapter
from .direct_llm import DirectLLMAdapter
from .generic_rest import GenericRestAdapter
from .griptape import GriptapeAdapter
from .hermes import HermesAdapter
from .huggingface import HuggingFaceAdapter
from .langchain import LangChainAdapter
from .litellm import LiteLLMAdapter
from .llamaindex import LlamaIndexAdapter
from .make import MakeAdapter
from .mem0 import Mem0Adapter
from .metagpt import MetaGPTAdapter
from .mlflow import MLflowAdapter
from .n8n import N8NAdapter
from .openclaw import OpenClawAdapter
from .replicate import ReplicateAdapter
from .reworkdai import ReworkdAIAdapter
from .semantickernel import SemanticKernelAdapter
from .stabilityai import StabilityAIAdapter
from .taskweaver import TaskWeaverAdapter
from .vertexai import VertexAIAdapter
from .zapier import ZapierAdapter
from .zeroclaw import ZeroClawAdapter

__all__ = [
    "BaseAdapter",
    "DirectLLMAdapter",
    "OpenClawAdapter",
    "HermesAdapter",
    "ZeroClawAdapter",
    "GenericRestAdapter",
    "AutoGPTAdapter",
    "AgentGPTAdapter",
    "LangChainAdapter",
    "AutogenAdapter",
    "TaskWeaverAdapter",
    "N8NAdapter",
    "MakeAdapter",
    "ZapierAdapter",
    "BabyAGIAdapter",
    "MetaGPTAdapter",
    "GriptapeAdapter",
    "ReworkdAIAdapter",
    "ReplicateAdapter",
    "HuggingFaceAdapter",
    "LiteLLMAdapter",
    "VertexAIAdapter",
    "AzureOpenAIAdapter",
    "LlamaIndexAdapter",
    "BedrockAdapter",
    "SemanticKernelAdapter",
    "Mem0Adapter",
    "MLflowAdapter",
    "StabilityAIAdapter",
    "CrewAIAdapter",
]
