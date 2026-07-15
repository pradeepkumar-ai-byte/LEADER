"""
Leader – adapter plugins for various agent backends
"""
from .base import BaseAdapter
from .direct_llm import DirectLLMAdapter
from .openclaw import OpenClawAdapter
from .hermes import HermesAdapter
from .zeroclaw import ZeroClawAdapter
from .generic_rest import GenericRestAdapter
from .autogpt import AutoGPTAdapter
from .agentgpt import AgentGPTAdapter
from .langchain import LangChainAdapter
from .autogen import AutogenAdapter
from .taskweaver import TaskWeaverAdapter
from .n8n import N8NAdapter
from .make import MakeAdapter
from .zapier import ZapierAdapter
from .babyagi import BabyAGIAdapter
from .metagpt import MetaGPTAdapter
from .griptape import GriptapeAdapter
from .reworkdai import ReworkdAIAdapter
from .replicate import ReplicateAdapter
from .huggingface import HuggingFaceAdapter
from .litellm import LiteLLMAdapter
from .vertexai import VertexAIAdapter
from .azureopenai import AzureOpenAIAdapter
from .llamaindex import LlamaIndexAdapter
from .bedrock import BedrockAdapter
from .semantickernel import SemanticKernelAdapter
from .mem0 import Mem0Adapter
from .mlflow import MLflowAdapter
from .stabilityai import StabilityAIAdapter

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
]
