"""Leader – CrewAI native adapter"""
from __future__ import annotations
import time
import asyncio
import importlib.util
from ..models import Task, TaskResult
from .base import BaseAdapter

class CrewAIAdapter(BaseAdapter):
    def is_available(self) -> bool:
        return importlib.util.find_spec("crewai") is not None

    async def run(self, task: Task) -> TaskResult:
        t0 = time.monotonic()
        try:
            crewai = importlib.import_module("crewai")
            
            def _run_crewai():
                # Basic CrewAI dynamic setup
                agent = crewai.Agent(
                    role="AI Assistant",
                    goal="Complete the user's task efficiently and accurately.",
                    backstory="You are a highly capable AI assistant managed by Leader.",
                    verbose=False,
                    allow_delegation=False,
                )
                
                crew_task = crewai.Task(
                    description=task.prompt,
                    expected_output="A complete, accurate response to the user's request.",
                    agent=agent,
                )
                
                crew = crewai.Crew(
                    agents=[agent],
                    tasks=[crew_task],
                    verbose=False,
                )
                
                # Kickoff the crew process
                result = crew.kickoff()
                # Depending on crewai version, result might be an object or string.
                if hasattr(result, "raw"):
                    return result.raw
                return str(result)

            output = await asyncio.to_thread(_run_crewai)
            latency = (time.monotonic() - t0) * 1000
            
            return TaskResult(
                task_id=task.task_id, 
                backend_id="crewai", 
                output=str(output), 
                success=True, 
                latency_ms=latency
            )
        except Exception as exc:
            return TaskResult(
                task_id=task.task_id, 
                backend_id="crewai", 
                output="", 
                success=False, 
                latency_ms=(time.monotonic() - t0) * 1000, 
                error=str(exc)
            )
