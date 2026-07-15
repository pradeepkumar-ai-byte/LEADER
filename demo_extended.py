#!/usr/bin/env python
"""
Leader – Extended Demo showing all 30+ backends and advanced features
"""
import asyncio
from leader import Task, TaskCategory, Registry, Router, Executor, TaskLogger

async def main():
    print("\n" + "="*80)
    print("Leader – Intelligent Multi-Backend AI Agent Router".center(80))
    print("="*80 + "\n")

    # Build components
    print("[1/5] Initializing Leader with 30+ backends...")
    registry = Registry()
    logger = TaskLogger()
    router = Router(registry, logger)
    executor = Executor(registry)
    
    # Show all backends
    all_backends = registry.all()
    print(f"✓ {len(all_backends)} backends available:\n")
    
    # Group by type
    ai_agents = ["openclaw", "autogpt", "agentgpt", "babyagi", "hermes", "zeroclaw", "nanoclaw", "reworkdai"]
    multiagent = ["autogen", "crewai", "metagpt", "taskweaver"]
    llm = ["direct_llm", "litellm", "azureopenai", "vertexai", "bedrock", "huggingface", "replicate"]
    frameworks = ["langchain", "llamaindex", "semantickernel", "griptape"]
    automation = ["n8n", "make", "zapier"]
    specialized = ["stabilityai", "mem0", "mlflow"]
    
    print("  AI Agents (8):")
    for b_id in ai_agents:
        b = registry.get(b_id) or next((x for x in all_backends if x.id == b_id), None)
        if b:
            print(f"    • {b.display_name:<25} → {b.description[:45]}...")
    
    print("\n  Multi-Agent Frameworks (4):")
    for b_id in multiagent:
        b = registry.get(b_id) or next((x for x in all_backends if x.id == b_id), None)
        if b:
            print(f"    • {b.display_name:<25} → {b.description[:45]}...")
    
    print("\n  LLM Providers (7):")
    for b_id in llm:
        b = registry.get(b_id) or next((x for x in all_backends if x.id == b_id), None)
        if b:
            print(f"    • {b.display_name:<25} → {b.description[:45]}...")
    
    print("\n  Frameworks & RAG (4):")
    for b_id in frameworks:
        b = registry.get(b_id) or next((x for x in all_backends if x.id == b_id), None)
        if b:
            print(f"    • {b.display_name:<25} → {b.description[:45]}...")
    
    print("\n  No-Code Automation (3):")
    for b_id in automation:
        b = registry.get(b_id) or next((x for x in all_backends if x.id == b_id), None)
        if b:
            print(f"    • {b.display_name:<25} → {b.description[:45]}...")
    
    print("\n  Specialized Services (3):")
    for b_id in specialized:
        b = registry.get(b_id) or next((x for x in all_backends if x.id == b_id), None)
        if b:
            print(f"    • {b.display_name:<25} → {b.description[:45]}...")
    
    print("\n" + "-"*80)
    print("[2/5] Demonstrating intelligent routing\n")
    
    # Demo tasks
    demo_tasks = [
        ("send daily standup to slack channel", TaskCategory.MESSAGING),
        ("build a REST API in Python with FastAPI", TaskCategory.CODING),
        ("research latest developments in quantum computing", TaskCategory.RESEARCH),
        ("write a dystopian short story about AI", TaskCategory.CREATIVE),
        ("analyze sales data and create visualizations", TaskCategory.DATA),
        ("schedule weekly emails to customers", TaskCategory.AUTOMATION),
        ("coordinate team of 5 agents to build a SaaS app", TaskCategory.MULTIAGENT),
    ]
    
    for prompt, category in demo_tasks:
        task = Task(prompt=prompt, category=category)
        decision = router.decide(task)
        
        print(f"📌 {prompt[:50]}...")
        cat_str = category.value if category else "auto-detected"
        print(f"   Category: {cat_str:<15} → Primary: {decision.primary}")
        if decision.fallback_chain:
            fallback_str = ", ".join(decision.fallback_chain[:2])
            print(f"   Fallbacks: {fallback_str}")
        print()
    
    print("-"*80)
    print("[3/5] Understanding the intelligent routing")
    print("""
Leader automatically:
  ✓ Classifies tasks into 8 categories
  ✓ Routes to the best backend based on strengths
  ✓ Learns from your usage history (evolving scores)
  ✓ Provides fallback chains for reliability
  ✓ Suggests better backends if available
  ✓ Reports performance metrics (win rates, latency)
  ✓ Supports parallel execution (fastest wins)
""")
    
    print("-"*80)
    print("[4/5] How to use Leader with your backends\n")
    print("1. Add backends to ~/.leader/config.yaml:")
    print("""
    backends:
      autogpt:
        base_url: http://localhost:8000
        model: gpt-4
      
      n8n:
        base_url: http://localhost:5678
        workflow_id: my-workflow
      
      directllm:
        provider: anthropic
        api_key: sk-ant-YOUR-KEY
""")
    
    print("\n2. Run tasks:")
    print("""
    leader run "Write a blog post about AI"
    leader run "Calculate ROI" --category data
    leader run "Schedule emails" --parallel
    leader stats
    leader feedback TASK_ID 5  # Rate results
""")
    
    print("\n" + "-"*80)
    print("[5/5] Why Leader is Different\n")
    print("""
  🎯 NOT just another wrapper
     • Unique: Sits ABOVE multiple backends, not replacing them
     • You keep using all your existing tools
     • Leader adds intelligence on top
  
  📊 Actually learns from your usage
     • 60% history, 40% static knowledge
     • Evolves routing based on your patterns
     • Shows win-rates per backend per category
  
  🤝 DevOps-friendly design
     • Works with 30+ real-world platforms
     • No database required (local SQLite)
     • Easy to self-host or manage
  
  💡 Transparent recommendations
     • Tells you "connecting X would improve this"
     • Never pretends current result is optimal
     • Proactive backend optimization
  
  ⚡ Production-ready features
     • Async/parallel execution
     • Comprehensive error handling
     • Task timeout management
     • Cost estimation built-in
""")
    
    print("="*80 + "\n")
    print("Get started now: leader init && leader run \"your first task\"")
    print("View all backends: cat BACKENDS.md")
    print("GitHub: https://github.com/leader-agent/leader\n")

if __name__ == "__main__":
    asyncio.run(main())
