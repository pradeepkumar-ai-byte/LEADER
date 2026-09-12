"""
Leader – CrewAI Drop-in Infrastructure Wrapper

Provides specialized, drop-in wrappers designed to replace standard unprotected
routers, step loops, and task execution pipelines inside CrewAI applications.

Key Features:
  • LeaderCrew: Drop-in replacement for `crewai.Crew` that automatically injects
    safety interception across all agent steps and task handoffs.
  • LeaderStepCallback: Reusable step callback tracking inter-agent semantic drift
    and isolating endless feedback loops during execution.
  • LeaderTaskCallback: Reusable task callback validating final agent outputs
    against exploit signatures with the safety circuit breaker.
  • LeaderCrewRouter: Dynamic delegation router for hierarchical CrewAI teams.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Callable, Dict, List, Optional, Sequence

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

logger = logging.getLogger("leader.bridges.crewai")

# Optional CrewAI import guard
try:
    import crewai
    from crewai import Agent, Crew, Process
    from crewai import Task as CrewTask

    CREWAI_AVAILABLE = True
except ImportError:
    crewai = None
    Agent = object
    Crew = object
    Process = object
    CrewTask = object
    CREWAI_AVAILABLE = False


class LeaderStepCallback:
    """
    Step callback for CrewAI agents and crews.

    Monitors inter-agent communication, measures semantic drift from the root
    alignment mission, and catches infinite ping-pong or cyclic execution loops.
    """

    def __init__(
        self,
        chain_monitor: Optional[ChainMonitor] = None,
        task_logger: Optional[TaskLogger] = None,
        chain_id: Optional[str] = None,
        root_prompt: Optional[str] = None,
        strict_break: bool = True,
    ):
        self.chain_monitor = chain_monitor or ChainMonitor()
        self.task_logger = task_logger or TaskLogger()
        self.chain_id = chain_id or uuid.uuid4().hex
        self.root_prompt = root_prompt
        self.strict_break = strict_break
        self.step_index: int = 0
        self.parent_prompt: Optional[str] = None
        self.verdicts: List[ChainStepVerdict] = []
        self.is_interrupted: bool = False
        self.interruption_reason: str = ""

    def __call__(self, step_output: Any) -> None:
        """Called by CrewAI after every agent step."""
        # Normalize step text
        if hasattr(step_output, "text"):
            text = str(step_output.text)
        elif hasattr(step_output, "result"):
            text = str(step_output.result)
        elif isinstance(step_output, (list, tuple)) and step_output:
            text = " ".join(str(item) for item in step_output)
        else:
            text = str(step_output)

        if not self.root_prompt:
            self.root_prompt = text

        step = ChainStep(
            prompt=text,
            source_backend="crewai_agent",
            target_backend="crew_orchestrator",
            step_index=self.step_index,
            chain_id=self.chain_id,
        )

        verdict = self.chain_monitor.inspect_step(
            step=step,
            root_prompt=self.root_prompt,
            parent_prompt=self.parent_prompt,
        )
        self.verdicts.append(verdict)
        self.task_logger.log_chain_step(step, verdict, output_payload=text)

        if verdict.action in (ChainAction.TERMINATE_LOOP, ChainAction.TERMINATE_DRIFT):
            self.is_interrupted = True
            self.interruption_reason = f"[{verdict.action.value}] {verdict.summary}"
            logger.critical("LeaderStepCallback intervention: %s", self.interruption_reason)
            if self.strict_break:
                raise RuntimeError(f"LEADER Safety Intervention: {self.interruption_reason}")

        self.parent_prompt = text
        self.step_index += 1


class LeaderTaskCallback:
    """
    Task callback for CrewAI tasks and crews.

    Scans completed task outputs against exploit signatures using the
    Leader CircuitBreaker, isolating backends if exploit patterns emerge.
    """

    def __init__(
        self,
        circuit_breaker: Optional[CircuitBreaker] = None,
        task_logger: Optional[TaskLogger] = None,
    ):
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.task_logger = task_logger or TaskLogger()
        self.violations_found: List[str] = []

    def __call__(self, task_output: Any) -> None:
        """Called by CrewAI when a task finishes."""
        raw_text = (
            getattr(task_output, "raw", None)
            or getattr(task_output, "output", None)
            or str(task_output)
        )

        res = TaskResult(
            task_id=uuid.uuid4().hex,
            backend_id="crewai_task_executor",
            output=raw_text,
            success=True,
            latency_ms=0.0,
        )

        violation = self.circuit_breaker.scan_response(res)
        if violation:
            v_msg = (
                f"Exploit signature {violation.signature_id} ({violation.violation_type.value}) "
                f"matched: {violation.matched_span[:100]}"
            )
            self.violations_found.append(v_msg)
            self.task_logger.log_result(
                res,
                alignment_failure=True,
                security_payload=v_msg,
            )
            logger.critical("LeaderTaskCallback: %s", v_msg)


class LeaderCrewRouter:
    """
    Manager router for hierarchical CrewAI crews.

    Dispatches sub-tasks to the most qualified agent in the crew using
    LEADER's semantic classification engine rather than unconstrained LLM calls.
    """

    def __init__(
        self,
        router: Optional[Router] = None,
        agent_specialties: Optional[Dict[str, TaskCategory]] = None,
    ):
        self.router = router
        self.agent_specialties = agent_specialties or {}

    def route_task(self, task_description: str, agents: Sequence[Any]) -> Any:
        """Select the best agent from agents list for a given task description."""
        if not agents:
            return None

        if self.router:
            decision = self.router.decide(Task(prompt=task_description))
            cat = decision.category
        else:
            from ..router import classify

            cat = classify(task_description)

        for agent in agents:
            role = getattr(agent, "role", "").lower()
            agent_name = getattr(agent, "name", str(agent)).lower()
            if agent_name in self.agent_specialties and self.agent_specialties[agent_name] == cat:
                return agent
            if cat.value in role or cat.value in agent_name:
                return agent

        return agents[0]


class LeaderCrew(Crew if CREWAI_AVAILABLE else object):
    """
    Drop-in replacement for CrewAI `Crew`.

    Secures CrewAI pipelines by wrapping execution with real-time prompt
    firewalls, semantic drift monitoring, loop breakers, and circuit breaker
    output validation.
    """

    def __init__(
        self,
        agents: Optional[List[Any]] = None,
        tasks: Optional[List[Any]] = None,
        process: Any = None,
        verbose: bool = False,
        chain_monitor: Optional[ChainMonitor] = None,
        firewall: Optional[FirewallMiddleware] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        task_logger: Optional[TaskLogger] = None,
        step_callback: Optional[Callable] = None,
        task_callback: Optional[Callable] = None,
        **kwargs: Any,
    ):
        self.custom_logger = task_logger or TaskLogger()
        self.chain_monitor = chain_monitor or ChainMonitor()
        self.firewall = firewall or FirewallMiddleware()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()

        self.leader_step_cb = LeaderStepCallback(
            chain_monitor=self.chain_monitor,
            task_logger=self.custom_logger,
        )
        self.leader_task_cb = LeaderTaskCallback(
            circuit_breaker=self.circuit_breaker,
            task_logger=self.custom_logger,
        )

        def _combined_step_cb(step_out: Any):
            self.leader_step_cb(step_out)
            if step_callback:
                step_callback(step_out)

        def _combined_task_cb(task_out: Any):
            self.leader_task_cb(task_out)
            if task_callback:
                task_callback(task_out)

        if CREWAI_AVAILABLE and issubclass(LeaderCrew, Crew):
            super().__init__(
                agents=agents or [],
                tasks=tasks or [],
                process=process or getattr(Process, "sequential", None),
                verbose=verbose,
                step_callback=_combined_step_cb,
                task_callback=_combined_task_cb,
                **kwargs,
            )
        else:
            self.agents = agents or []
            self.tasks = tasks or []
            self.process = process
            self.verbose = verbose
            self.step_callback = _combined_step_cb
            self.task_callback = _combined_task_cb

    def kickoff(self, inputs: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute the crew workflow with pre-execution firewall validation
        and active multi-agent monitoring.
        """
        # 1. Pre-execution input validation
        if inputs:
            import asyncio

            input_text = " ".join(str(v) for v in inputs.values())
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    fw_res = pool.submit(asyncio.run, self.firewall.evaluate(input_text)).result()
            else:
                fw_res = asyncio.run(self.firewall.evaluate(input_text))

            if fw_res.action == SafetyAction.BLOCK:
                err = (
                    f"LEADER Firewall blocked Crew kickoff: Threat={fw_res.threat_category.value} "
                    f"(score={fw_res.composite_score:.2f}). Summary: {fw_res.summary}"
                )
                logger.critical(err)
                raise PermissionError(err)

            self.leader_step_cb.root_prompt = input_text

        # 2. Execute underlying Crew workflow
        if CREWAI_AVAILABLE and hasattr(super(), "kickoff"):
            return super().kickoff(inputs=inputs)

        # Fallback simulation if CrewAI is mocked/uninstalled
        results = []
        for t in self.tasks:
            desc = getattr(t, "description", str(t))
            self.leader_step_cb(f"Executing step for task: {desc}")
            simulated_res = f"[LeaderCrew Simulated Output] Completed: {desc}"
            self.leader_task_cb(simulated_res)
            results.append(simulated_res)

        return "\n".join(results)
