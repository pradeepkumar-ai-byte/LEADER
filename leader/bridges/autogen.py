"""
Leader – Microsoft AutoGen Drop-in Infrastructure Wrapper

Provides specialized, drop-in wrappers designed to replace standard unprotected
routers and conversation managers inside Microsoft AutoGen pipelines.

Key Features:
  • LeaderGroupChatManager: Drop-in conversation manager that intercepts every
    inter-agent turn with FirewallMiddleware, ChainMonitor, and CircuitBreaker.
  • LeaderSpeakerSelector: Intelligent speaker selection using LEADER semantic
    routing instead of expensive / unaligned LLM votes.
  • LeaderAutoGenHook: Protocol-level message interceptor hook for AutoGen agents.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional, Union

from ..chain_diagnostics import ChainMonitor
from ..circuit_breaker import CircuitBreaker
from ..firewall_middleware import FirewallMiddleware, SafetyAction
from ..logger import TaskLogger
from ..models import (
    ChainAction,
    ChainStep,
    ChainStepVerdict,
    Task,
    TaskCategory,
    TaskResult,
)
from ..router import Router

logger = logging.getLogger("leader.bridges.autogen")

# Optional AutoGen import guard
try:
    import autogen
    from autogen import Agent, ConversableAgent, GroupChat, GroupChatManager

    AUTOGEN_AVAILABLE = True
except ImportError:
    autogen = None
    Agent = object
    ConversableAgent = object
    GroupChat = object
    GroupChatManager = object
    AUTOGEN_AVAILABLE = False


class LeaderSpeakerSelector:
    """
    Intelligent speaker selection for AutoGen GroupChats.

    Replaces default round-robin or costly LLM speaker selection by classifying
    the current conversation turn using LEADER's semantic matrix and selecting
    the agent whose registered capability/role best matches the step.
    """

    def __init__(
        self,
        router: Optional[Router] = None,
        agent_category_map: Optional[Dict[str, TaskCategory]] = None,
    ):
        self.router = router
        self.agent_category_map = agent_category_map or {}

    def select_speaker(
        self,
        last_speaker: Any,
        groupchat: Any,
    ) -> Any:
        """Select next speaker based on the latest message content."""
        messages = getattr(groupchat, "messages", [])
        if not messages:
            return groupchat.agents[0] if getattr(groupchat, "agents", None) else None

        last_msg = messages[-1]
        content = last_msg.get("content", "") if isinstance(last_msg, dict) else str(last_msg)

        # If agent category map is provided, use semantic classification
        if self.router:
            decision = self.router.decide(Task(prompt=content))
            cat = decision.category
        else:
            from ..router import classify

            cat = classify(content)

        # 1. Exact match with agent category map
        for agent in getattr(groupchat, "agents", []):
            agent_name = getattr(agent, "name", str(agent)).lower()
            if agent_name in self.agent_category_map:
                if self.agent_category_map[agent_name] == cat:
                    return agent

        # 2. Heuristic match on agent name or role description
        for agent in getattr(groupchat, "agents", []):
            agent_name = getattr(agent, "name", str(agent)).lower()
            agent_desc = getattr(agent, "description", "").lower()
            if cat.value in agent_name or cat.value in agent_desc:
                return agent

        # 3. Fallback: pick next agent in sequence (excluding last speaker if multiple exist)
        agents = getattr(groupchat, "agents", [])
        if len(agents) > 1 and last_speaker in agents:
            idx = agents.index(last_speaker)
            return agents[(idx + 1) % len(agents)]
        return agents[0] if agents else None


class LeaderAutoGenHook:
    """
    Protocol-level safety middleware hook for AutoGen agents.
    Can be registered via agent.register_hook() or called manually.
    """

    def __init__(
        self,
        chain_monitor: Optional[ChainMonitor] = None,
        firewall: Optional[FirewallMiddleware] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        logger_instance: Optional[TaskLogger] = None,
    ):
        self.chain_monitor = chain_monitor or ChainMonitor()
        self.firewall = firewall or FirewallMiddleware()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.task_logger = logger_instance or TaskLogger()

    async def process_message_async(
        self,
        message: Union[dict, str],
        sender: Any,
        recipient: Any,
        chain_id: str,
        root_prompt: str,
        step_index: int,
        parent_prompt: Optional[str] = None,
    ) -> tuple[bool, str, Optional[ChainStepVerdict]]:
        """
        Inspect an inter-agent message before delivery.

        Returns:
            (allow_delivery, processed_or_error_content, verdict)
        """
        raw_text = message.get("content", "") if isinstance(message, dict) else str(message)
        sender_name = getattr(sender, "name", str(sender))
        recipient_name = getattr(recipient, "name", str(recipient))

        # 1. Pre-execution Firewall Interception
        firewall_verdict = await self.firewall.evaluate(raw_text)
        if firewall_verdict.action == SafetyAction.BLOCK:
            err_msg = (
                f"[LEADER SECURITY FIREWALL] Message from '{sender_name}' blocked. "
                f"Threat: {firewall_verdict.threat_category.value} (score={firewall_verdict.composite_score:.2f}). "
                f"Summary: {firewall_verdict.summary}"
            )
            logger.warning(err_msg)
            return False, err_msg, None

        # 2. Multi-Agent Chain Diagnostics (Loop & Semantic Drift)
        step = ChainStep(
            prompt=raw_text,
            source_backend=sender_name,
            target_backend=recipient_name,
            step_index=step_index,
            chain_id=chain_id,
        )

        verdict = self.chain_monitor.inspect_step(
            step=step,
            root_prompt=root_prompt,
            parent_prompt=parent_prompt,
        )

        # 3. Administrative Break Actions
        if verdict.action in (ChainAction.TERMINATE_LOOP, ChainAction.TERMINATE_DRIFT):
            err_msg = (
                f"[LEADER CHAIN INTERVENTION] Action: {verdict.action.value}. "
                f"Summary: {verdict.summary}"
            )
            logger.critical(err_msg)
            self.task_logger.log_chain_step(step, verdict, output_payload=raw_text)
            return False, err_msg, verdict

        # 4. Post-execution Output Exploit Scanning (Circuit Breaker)
        dummy_result = TaskResult(
            task_id=step.step_id,
            backend_id=sender_name,
            output=raw_text,
            success=True,
            latency_ms=verdict.latency_ms,
        )
        violation = self.circuit_breaker.scan_response(dummy_result)
        if violation:
            err_msg = (
                f"[LEADER CIRCUIT BREAKER] Exploit signature detected: "
                f"{violation.violation_type.value} [{violation.signature_id}]. "
                f"Matched: '{violation.matched_span[:100]}...'"
            )
            logger.critical(err_msg)
            self.task_logger.log_result(
                dummy_result,
                alignment_failure=True,
                security_payload=err_msg,
            )
            return False, err_msg, verdict

        # Clean step passed all safety gates
        self.task_logger.log_chain_step(step, verdict, output_payload=raw_text)
        return True, raw_text, verdict

    def process_message_sync(
        self,
        message: Union[dict, str],
        sender: Any,
        recipient: Any,
        chain_id: str,
        root_prompt: str,
        step_index: int,
        parent_prompt: Optional[str] = None,
    ) -> tuple[bool, str, Optional[ChainStepVerdict]]:
        """Synchronous wrapper for message processing."""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    self.process_message_async(
                        message=message,
                        sender=sender,
                        recipient=recipient,
                        chain_id=chain_id,
                        root_prompt=root_prompt,
                        step_index=step_index,
                        parent_prompt=parent_prompt,
                    ),
                )
                return future.result()
        else:
            return asyncio.run(
                self.process_message_async(
                    message=message,
                    sender=sender,
                    recipient=recipient,
                    chain_id=chain_id,
                    root_prompt=root_prompt,
                    step_index=step_index,
                    parent_prompt=parent_prompt,
                )
            )


class LeaderGroupChatManager(GroupChatManager if AUTOGEN_AVAILABLE else object):
    """
    Drop-in replacement for AutoGen's GroupChatManager.

    Secures multi-agent AutoGen conversations by intercepting every message turn,
    enforcing prompt firewalls, preventing token-burning feedback loops,
    tracking semantic drift, and isolating dangerous backend outputs.
    """

    def __init__(
        self,
        groupchat: Any,
        name: str = "leader_manager",
        max_consecutive_auto_reply: Optional[int] = None,
        human_input_mode: str = "NEVER",
        system_message: str = "LEADER Secure Group Chat Manager",
        chain_monitor: Optional[ChainMonitor] = None,
        firewall: Optional[FirewallMiddleware] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        logger_instance: Optional[TaskLogger] = None,
        speaker_selector: Optional[LeaderSpeakerSelector] = None,
        **kwargs: Any,
    ):
        if AUTOGEN_AVAILABLE and issubclass(LeaderGroupChatManager, GroupChatManager):
            super().__init__(
                groupchat=groupchat,
                name=name,
                max_consecutive_auto_reply=max_consecutive_auto_reply,
                human_input_mode=human_input_mode,
                system_message=system_message,
                **kwargs,
            )
        else:
            self.groupchat = groupchat
            self.name = name
            self.max_consecutive_auto_reply = max_consecutive_auto_reply
            self.human_input_mode = human_input_mode
            self.system_message = system_message

        self.hook = LeaderAutoGenHook(
            chain_monitor=chain_monitor,
            firewall=firewall,
            circuit_breaker=circuit_breaker,
            logger_instance=logger_instance,
        )
        self.speaker_selector = speaker_selector or LeaderSpeakerSelector()
        self.chain_id = uuid.uuid4().hex
        self.root_prompt: Optional[str] = None
        self.step_index: int = 0
        self.parent_prompt: Optional[str] = None
        self.session_verdicts: List[ChainStepVerdict] = []
        self.is_terminated: bool = False
        self.termination_reason: str = ""

    def reset_session(self, root_prompt: Optional[str] = None) -> None:
        """Reset conversation telemetry for a new multi-agent session."""
        self.chain_id = uuid.uuid4().hex
        self.root_prompt = root_prompt
        self.step_index = 0
        self.parent_prompt = None
        self.session_verdicts = []
        self.is_terminated = False
        self.termination_reason = ""
        self.hook.chain_monitor.loop_detector.clear_chain(self.chain_id)

    def intercept_message(
        self,
        message: Union[dict, str],
        sender: Any,
        recipient: Any,
    ) -> tuple[bool, str]:
        """
        Intercepts and inspects a message turn synchronously.
        """
        if self.is_terminated:
            return False, f"[LEADER HALT] Session previously terminated: {self.termination_reason}"

        raw_text = message.get("content", "") if isinstance(message, dict) else str(message)
        if self.root_prompt is None:
            self.root_prompt = raw_text

        allowed, content, verdict = self.hook.process_message_sync(
            message=message,
            sender=sender,
            recipient=recipient,
            chain_id=self.chain_id,
            root_prompt=self.root_prompt,
            step_index=self.step_index,
            parent_prompt=self.parent_prompt,
        )

        if verdict:
            self.session_verdicts.append(verdict)

        if not allowed:
            self.is_terminated = True
            self.termination_reason = content
            return False, content

        self.parent_prompt = raw_text
        self.step_index += 1
        return True, content

    def select_speaker(self, speaker: Any, groupchat: Any) -> Any:
        """Override default speaker selection with LEADER's intelligent router."""
        if self.speaker_selector:
            return self.speaker_selector.select_speaker(speaker, groupchat)
        if AUTOGEN_AVAILABLE and hasattr(super(), "select_speaker"):
            return super().select_speaker(speaker, groupchat)
        agents = getattr(groupchat, "agents", [])
        return agents[0] if agents else None
