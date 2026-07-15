# Contributing to Leader

Thank you for your interest in contributing to Leader! 🎉

## ⚠️ Maintenance Notice

**Leader is a low-maintenance open-source project.**
- We review and merge PRs every 2–4 weeks (best-effort)
- We may not respond to all issues immediately
- For urgent production needs, please maintain your own fork
- All contributions are voluntary and unpaid

If you need faster support, consider hiring a consultant or forking Leader.

---

## Getting Started

1. **Fork** the repository on GitHub
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/LEADER.git
   cd LEADER
   ```
3. **Install** in development mode:
   ```bash
   pip install -e ".[dev]"
   ```
4. **Run the tests** to make sure everything works:
   ```bash
   pytest leader/test_leader.py -v
   ```

## Development Workflow

1. Create a new branch for your feature or fix:
   ```bash
   git checkout -b feature/my-awesome-feature
   ```
2. Make your changes and write tests.
3. Run the full test suite:
   ```bash
   pytest leader/test_leader.py -v
   pytest leader/test_integration.py -v
   ```
4. Run the formatter and linter:
   ```bash
   black leader/
   ruff check leader/
   ```
5. Commit and push your changes.
6. Open a Pull Request on the main repository.

### Pull Request Guidelines
- **Draft PRs**: If your changes are a work in progress, open it as a Draft.
- **Single Responsibility**: Each PR should focus on a single feature, adapter, or bug fix.
- **Test Coverage**: All new features or adapters must include corresponding tests.
- **Documentation**: If your change affects configurations or features, update the relevant `.md` files.

### Code Review Process
- All Pull Requests require at least one approval from a maintainer before merge.
- Maintainers will run the CI pipeline automatically on your PR.
- Any feedback should be addressed by pushing new commits to the same branch.


## Adding a New Backend Adapter

This is the most common type of contribution. To add a new backend:

1. Create a new file in `leader/adapters/` (e.g., `my_backend.py`)
2. Inherit from `BaseAdapter` and implement:
   - `is_available()` — check if the backend is properly configured
   - `run(task)` — execute a task and return a `TaskResult`
3. Add a `BackendSpec` entry to the `CATALOGUE` in `leader/registry.py`
4. Add tests for your adapter
5. Update `BACKENDS.md` with usage documentation

### Adapter Template

```python
"""
Leader – MyBackend adapter
"""
from __future__ import annotations
import time
import aiohttp
from ..models import Task, TaskResult
from .base import BaseAdapter


class MyBackendAdapter(BaseAdapter):

    def is_available(self) -> bool:
        return bool(self.config.get("base_url"))

    async def run(self, task: Task) -> TaskResult:
        base_url = self.config.get("base_url", "").rstrip("/")
        t0 = time.monotonic()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base_url}/api/run",
                    json={"prompt": task.prompt},
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    latency = (time.monotonic() - t0) * 1000
                    if resp.status == 200:
                        data = await resp.json()
                        return TaskResult(
                            task_id=task.task_id,
                            backend_id="my_backend",
                            output=data.get("result", ""),
                            success=True,
                            latency_ms=latency,
                        )
                    else:
                        return TaskResult(
                            task_id=task.task_id,
                            backend_id="my_backend",
                            output="",
                            success=False,
                            latency_ms=latency,
                            error=f"HTTP {resp.status}",
                        )
        except Exception as exc:
            return TaskResult(
                task_id=task.task_id,
                backend_id="my_backend",
                output="",
                success=False,
                latency_ms=(time.monotonic() - t0) * 1000,
                error=str(exc),
            )
```

## Code Style

- We use **Black** for formatting (line length 100)
- We use **Ruff** for linting
- All code must be **type-hinted**
- All public functions must have **docstrings**

## Reporting Issues

We use GitHub Issues to track bugs, suggest features, and discuss general improvements.

### Bug Reports
- Please search the existing issues before filing a new one.
- Use the **Bug Report** template when opening an issue.
- Clearly describe the bug, how to reproduce it, and the environment details (OS, Python version, Leader version).
- Include minimal reproducible code or commands, and relevant error traceback logs.

### Feature Requests
- Propose new features by opening a **Feature Request** issue.
- Explain the motivation behind the feature and how it should behave.
- If you're planning to implement the feature yourself, state it in the description so we can coordinate.


## License

By contributing, you agree that your contributions will be licensed under the MIT License.
