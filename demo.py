#!/usr/bin/env python
"""
Leader – Demo script showing how to use the routing system
"""
import asyncio
from leader import Task, TaskCategory, Registry, Router, Executor, TaskLogger

async def main():
    print("\n" + "="*70)
    print("Leader Demo – Intelligent Task Routing".center(70))
    print("="*70 + "\n")

    # Build components
    print("[1/4] Initializing Leader components...")
    registry = Registry()
    logger = TaskLogger()
    router = Router(registry, logger)
    executor = Executor(registry)
    print("✓ Registry, Logger, Router, and Executor ready\n")

    # Check what backends are connected
    print("[2/4] Checking connected backends...")
    connected = registry.connected()
    if not connected:
        print("⚠ No backends connected. Edit ~/.leader/config.yaml to add one.")
        print("  Quick start: add a direct_llm backend with an API key.\n")
        print("Demo tasks (routing only, no execution):")
    else:
        print(f"✓ Found {len(connected)} connected backend(s)")
        for spec in connected:
            print(f"  • {spec.display_name} ({spec.id})")
        print()

    # Define some demo tasks
    tasks = [
        ("send a slack notification about the new deploy", None),
        ("write a python function to calculate fibonacci", TaskCategory.CODING),
        ("find me the latest news on AI safety", TaskCategory.RESEARCH),
        ("brainstorm ideas for a sci-fi novel", TaskCategory.CREATIVE),
    ]

    # Route tasks
    print("[3/4] Routing tasks to the best backend...\n")
    for prompt, category in tasks:
        task = Task(prompt=prompt, category=category)
        decision = router.decide(task)
        
        print(f"📌 Task: {prompt[:50]}...")
        print(f"   Category: {task.category.value if task.category else 'auto-detected'}")
        print(f"   Primary:  {decision.primary}")
        if decision.fallback_chain:
            print(f"   Fallback: {', '.join(decision.fallback_chain)}")
        print(f"   Reason:   {decision.rationale}")
        if decision.recommendation:
            print(f"   💡 Tip:   {decision.recommendation[:60]}...")
        print()

    print("[4/4] Summary")
    print("-" * 70)
    print("Leader automatically:")
    print("  ✓ Classifies incoming tasks by category")
    print("  ✓ Selects the best-suited backend (or evolves based on your history)")
    print("  ✓ Provides fallback chains for reliability")
    print("  ✓ Suggests better backends to connect for improvements")
    print("\nTo execute a task, run:  leader run \"your task here\"")
    print("To add backends, edit:   ~/.leader/config.yaml")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
