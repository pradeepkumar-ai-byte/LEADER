"""
Leader – Multi-Agent Framework Bridges

Provides production-ready drop-in wrappers and safety hooks for enterprise
multi-agent frameworks including Microsoft AutoGen and CrewAI.
"""

from .autogen import (
    AUTOGEN_AVAILABLE,
    LeaderAutoGenHook,
    LeaderGroupChatManager,
    LeaderSpeakerSelector,
)
from .crewai import (
    CREWAI_AVAILABLE,
    LeaderCrew,
    LeaderCrewRouter,
    LeaderStepCallback,
    LeaderTaskCallback,
)

__all__ = [
    # AutoGen Bridge
    "AUTOGEN_AVAILABLE",
    "LeaderGroupChatManager",
    "LeaderSpeakerSelector",
    "LeaderAutoGenHook",
    # CrewAI Bridge
    "CREWAI_AVAILABLE",
    "LeaderCrew",
    "LeaderStepCallback",
    "LeaderTaskCallback",
    "LeaderCrewRouter",
]
