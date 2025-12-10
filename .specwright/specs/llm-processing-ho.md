---
version: "0.1"
tier: C
title: LLM Processing Integration
owner: benthepsychologist
goal: Add native LLM prompt processing as a life_jobs module using the llm Python library
labels: [feature, integration, llm]
project_slug: life-cli
spec_version: 1.0.0
created: 2025-12-10T12:02:12.108833+00:00
updated: 2025-12-10T12:02:12.108833+00:00
orchestrator_contract: "standard"
repo:
  working_branch: "feat/llm-processing"
---

# LLM Processing Integration

## Objective

> Integrate LLM prompt processing into life-cli's job runner using Simon Willison's `llm` library as a first-class Python dependency, enabling YAML-defined jobs to call LLM models directly without subprocess overhead.

### Background

The `/workspace/tools/generate` package demonstrates a working pattern for LLM-based content generation:
- Assembles prompts from static templates + JSON context files
- Calls `llm` CLI via subprocess
- Supports single-run and batch processing with accumulation

However, this approach has limitations:
1. **Subprocess overhead**: Each LLM call spawns a new process
2. **No library integration**: `llm` is a full Python library, not just a CLI
3. **Separate tooling**: Generate lives outside life-cli, requiring shell orchestration
4. **Limited composability**: Can't easily chain LLM calls with Dataverse/Graph operations in a single job

The `llm` library (https://llm.datasette.io/) provides a clean Python API:
```python
import llm
model = llm.get_model("gpt-4o-mini")
response = model.prompt("Your prompt", system="System context")
print(response.text())
```

This spec integrates `llm` as a library dependency, creating `life_jobs.generate` functions that follow the established job runner patterns (no print, return dicts, allowlist-safe).

### Acceptance Criteria

- [ ] `llm` added as optional dependency in pyproject.toml (`[project.optional-dependencies] llm = ["llm>=0.19"]`)
- [ ] New `life_jobs/generate.py` module with functions: `prompt()`, `prompt_with_context()`, `batch()`
- [ ] Functions follow existing patterns: no print, return `{"output": str, "model": str, ...}` dicts
- [ ] Template resolution supports both inline text and file paths (expanduser)
- [ ] Context assembly mirrors tools/generate pattern (JSON files -> markdown blocks)
- [ ] Graceful degradation: clear error if `llm` not installed
- [ ] `batch()` includes production safeguards:
  - [ ] Retry with exponential backoff on transient failures
  - [ ] Rate limiting support (configurable RPM)
  - [ ] Partial failure continuation with per-item error tracking
  - [ ] Unique call_id per LLM invocation for debugging/idempotency
  - [ ] Token usage aggregation across batch
- [ ] Unit tests with mocked LLM responses (no actual API calls in CI)
- [ ] Live acceptance tests gated by `LLM_LIVE_TESTS=1` env var
- [ ] Example job definition in `src/life/jobs/generate.yaml`
- [ ] Health-check job `llm_healthcheck` in job definitions
- [ ] CI green (lint + unit tests pass)

### Constraints

- No edits under protected paths (`src/core/**`, `infra/**`)
- `llm` must be optional dependency (life-cli works without it, just can't run generate jobs)
- No templates bundled in life-cli - templates are user-provided or referenced by path
- Follows existing `life_jobs.*` module patterns exactly

### Not In Scope

- **Context length management**: If assembled prompt exceeds model's max context, behavior is undefined. Future work may add heuristic truncation or file-level priority ordering.
- **Streaming responses**: Initial implementation returns complete text; streaming can be added later.
- **Async batch processing**: Sequential processing only; parallel/async batching is future work.

## Plan

### Step 1: Planning & Design [G0: Plan Approval]

**Prompt:**

Design the `life_jobs.generate` module API. Produce:
1. Function signatures for `prompt()`, `prompt_with_context()`, `batch()`
2. Return shape specifications (must be JSON-serializable dicts)
3. Error handling strategy (ImportError for missing llm, model errors)
4. Template/context resolution approach

Document in `artifacts/plan/generate-api-design.md`.

**Outputs:**

- `artifacts/plan/generate-api-design.md`

### Step 2: Implementation [G1: Code Readiness]

**Prompt:**

Implement `src/life_jobs/generate.py` with:

1. **Import guard**: Wrap `import llm` in try/except, raise clear error on use if missing
2. **`prompt()`**: Basic single prompt with optional system prompt, model selection, output file
3. **`prompt_with_context()`**: Accepts list of JSON/text files, assembles as markdown context blocks (mirroring tools/generate pattern)
4. **`batch()`**: Process JSON array of items, optional accumulation mode
5. **Helper functions**: `_assemble_context()`, `_resolve_template()`, `_expand_path()`

Follow existing module patterns from `life_jobs/dataverse.py`:
- No print statements
- Return simple dicts with predictable keys
- Use Path.expanduser() for path handling
- Type hints on all functions

Update `src/life_jobs/__init__.py` docstring to include generate module.

Update `pyproject.toml` to add optional `llm` dependency.

**Commands:**

```bash
ruff check src/life_jobs/generate.py
```

**Outputs:**

- `src/life_jobs/generate.py` (new)
- `src/life_jobs/__init__.py` (updated docstring)
- `pyproject.toml` (updated optional deps)

### Step 3: Job Definitions [G1: Code Readiness]

**Prompt:**

Create example job definitions in `src/life/jobs/generate.yaml`:

```yaml
jobs:
  simple_prompt:
    description: "Simple LLM prompt"
    steps:
      - name: generate
        call: life_jobs.generate.prompt
        args:
          prompt: "{user_prompt}"
          model: gpt-4o-mini
          output: ~/output/response.md

  summarize_json:
    description: "Summarize JSON data with context"
    steps:
      - name: generate
        call: life_jobs.generate.prompt_with_context
        args:
          prompt: "Summarize the key points from this data."
          context_files: ["{input_file}"]
          system: "You are a helpful assistant that provides concise summaries."
          output: ~/output/summary.md
```

**Outputs:**

- `src/life/jobs/generate.yaml` (new)

### Step 4: Unit and Integration Testing [G2: Pre-Release]

**Prompt:**

Write unit tests in `tests/test_generate.py`:

**Unit tests (mocked, no API calls):**

1. Test `prompt()` with mocked llm model (patch `llm.get_model`)
2. Test `prompt_with_context()` context assembly
3. Test `batch()` with array processing and accumulation
4. Test ImportError handling when llm not installed
5. Test path expansion and file writing
6. Test error propagation from model calls
7. **Production safeguard tests:**
   - Test retry with backoff (mock transient failures then success)
   - Test rate limiting with fake clock (inject time_func/sleep_func, assert sleep durations)
   - Test `continue_on_error=True` captures per-item failures
   - Test `continue_on_error=False` fails fast and returns partial results
   - Test `accumulate=True` defaults to `continue_on_error=False`
   - Test `accumulate=True` with explicit `continue_on_error=True` honors override
   - Test call_id uniqueness (UUIDv4 format, unique across batch items)
   - Test token aggregation shape `{"input": int, "output": int, "total": int}`
   - Test tokens are `None` when model doesn't provide them
   - Test results array ordering matches filtered input

**Integration test (mocked model, real file I/O):**

8. Create temp JSON items file with 3-5 items
9. Use fake llm model returning predictable text and token counts
10. Run `batch()` with rate limiting and retries disabled
11. Assert: count/succeeded/failed correct, each result has call_id/status/tokens/model
12. Assert: output file contains valid JSON array

Use pytest fixtures and monkeypatch for mocking. Rate limiting tests MUST use injectable clock, not wall-clock sleeps.

**Commands:**

```bash
pytest tests/test_generate.py -v
pytest tests/ -q --tb=short
ruff check .
```

**Outputs:**

- `tests/test_generate.py` (new)
- Test coverage report

### Step 4b: Live Acceptance Tests [G3: Final Validation]

**Prompt:**

Write live acceptance tests in `tests/test_generate_live.py` that make real LLM calls.
These run only when `LLM_LIVE_TESTS=1` environment variable is set.

```python
import pytest
import os

pytestmark = pytest.mark.skipif(
    os.environ.get("LLM_LIVE_TESTS") != "1",
    reason="Live LLM tests disabled (set LLM_LIVE_TESTS=1 to run)"
)
```

Tests:
1. `test_live_prompt()` - single prompt returns non-empty text
2. `test_live_prompt_with_context()` - context assembly works end-to-end
3. `test_live_batch_small()` - 2-3 item batch completes with correct structure
4. `test_live_healthcheck()` - run the llm_healthcheck job definition

These tests verify real API connectivity and model availability.

**Commands:**

```bash
LLM_LIVE_TESTS=1 pytest tests/test_generate_live.py -v
```

**Outputs:**

- `tests/test_generate_live.py` (new)

### Step 5: Documentation & Cleanup [G4: Post-Implementation]

**Prompt:**

1. Update README.md with brief section on LLM integration (under Features or new section)
2. Add inline docstrings to all public functions in generate.py
3. Create decision log documenting:
   - Why llm library vs CLI wrapper
   - Why optional dependency
   - Template resolution approach chosen

**Outputs:**

- `README.md` (updated)
- `artifacts/governance/decision-log.md`

## Technical Design Notes

### Function Signatures

```python
def prompt(
    prompt: str,
    *,
    system: Optional[str] = None,
    model: Optional[str] = None,
    output: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a single LLM prompt.

    Returns: {"output": str, "model": str, "tokens": dict, "written": Optional[str]}
    """

def prompt_with_context(
    prompt: str,
    context_files: List[str],
    *,
    system: Optional[str] = None,
    model: Optional[str] = None,
    output: Optional[str] = None,
    smart_order: bool = True,
) -> Dict[str, Any]:
    """Execute prompt with JSON/text files assembled as context.

    Context assembly pattern (from tools/generate):
    - Each file becomes: "## {filename}\n```json\n{content}\n```"
    - smart_order: baseline.json first, then session*delta, then metrics, then rest

    Returns: {"output": str, "model": str, "context_files": list, "written": Optional[str]}
    """

def batch(
    items_file: str,
    prompt: str,
    output: str,
    *,
    context_files: Optional[List[str]] = None,
    system: Optional[str] = None,
    model: Optional[str] = None,
    accumulate: bool = False,
    date_key: str = "date",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    # Production safeguards
    max_retries: int = 3,
    retry_delay: float = 1.0,
    retry_backoff: float = 2.0,
    rate_limit_rpm: Optional[int] = None,  # requests per minute
    continue_on_error: Optional[bool] = None,  # None = auto based on accumulate
) -> Dict[str, Any]:
    """Process JSON array through LLM, optionally accumulating results.

    Production safeguards:
    - Retry with exponential backoff on transient failures
    - Rate limiting to respect API quotas
    - Partial failure continuation
    - Per-item error tracking in results

    IMPORTANT: continue_on_error behavior:
    - If explicitly passed: use that value
    - If None (default) and accumulate=False: continue_on_error=True
    - If None (default) and accumulate=True: continue_on_error=False (fail fast)

    This prevents silently skipping items in accumulation chains where each
    result feeds into the next prompt.

    Returns: {
        "count": int,              # items considered after date filtering
        "succeeded": int,          # items with status="success"
        "failed": int,             # items with status="failed" (after retries exhausted)
        "results": list,           # ordered same as filtered input, one entry per item
        "written": str,            # output file path
        "total_tokens": dict,      # {"input": int, "output": int, "total": int}
    }

    When continue_on_error=False, batch stops at first hard failure but still
    returns results for all items processed up to that point.
    """
```

### Context Assembly (from tools/generate)

```python
def _assemble_context(prompt_text: str, files: List[Path]) -> str:
    """Assemble prompt with context files as markdown blocks."""
    blocks = ["# CONTEXT\n"]
    for f in files:
        content = f.read_text()
        title = f.stem.replace('_', ' ').title()
        if f.suffix == '.json':
            try:
                data = json.loads(content)
                pretty = json.dumps(data, indent=2)
                blocks.append(f"## {title}\n\n```json\n{pretty}\n```\n")
            except json.JSONDecodeError:
                blocks.append(f"## {title}\n\n{content}\n")
        else:
            blocks.append(f"## {title}\n\n{content}\n")
    return f"{prompt_text.strip()}\n\n---\n\n" + "\n".join(blocks)
```

### Import Guard Pattern

```python
_LLM_AVAILABLE = False
try:
    import llm as _llm
    _LLM_AVAILABLE = True
except ImportError:
    _llm = None

def _require_llm():
    if not _LLM_AVAILABLE:
        raise ImportError(
            "llm library not installed. Install with: pip install 'life-cli[llm]'"
        )
```

### Batch Retry & Rate Limiting

```python
import time
import uuid
from typing import Generator

def _retry_with_backoff(
    func,
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
) -> Any:
    """Retry a function with exponential backoff on transient errors."""
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            last_error = e
            # Check if retryable (rate limits, timeouts, server errors)
            if not _is_retryable(e) or attempt == max_retries:
                raise
            sleep_time = delay * (backoff ** attempt)
            time.sleep(sleep_time)
    raise last_error

def _is_retryable(error: Exception) -> bool:
    """Determine if an error is transient and worth retrying."""
    error_str = str(error).lower()
    retryable_patterns = [
        "rate limit", "429", "timeout", "503", "502",
        "connection", "temporarily unavailable"
    ]
    return any(p in error_str for p in retryable_patterns)

class RateLimiter:
    """Simple token bucket rate limiter with injectable clock for testing."""
    def __init__(
        self,
        rpm: int,
        time_func: Callable[[], float] = None,
        sleep_func: Callable[[float], None] = None,
    ):
        self.interval = 60.0 / rpm
        self.last_call = 0.0
        self._time = time_func or time.time
        self._sleep = sleep_func or time.sleep

    def wait(self):
        now = self._time()
        elapsed = now - self.last_call
        if elapsed < self.interval:
            self._sleep(self.interval - elapsed)
        self.last_call = self._time()
```

### Per-Item Result Structure

Each item in `batch()` results includes:

```python
{
    "item": {...},           # Original input item (unchanged)
    "call_id": "uuid",       # UUIDv4 string, unique per LLM invocation
    "status": "success|failed",
    "result": {...},         # LLM output (if success), None if failed
    "error": "message",      # Error details (if failed), None if success
    "tokens": {"input": int, "output": int, "total": int},
    "model": "gpt-4o-mini",
    "duration_ms": 1234,
}
```

**Contract requirements:**

- `call_id` MUST be a UUIDv4 string unique per LLM invocation within a batch. Used for logging and idempotency, not security.
- `tokens` and `total_tokens` MUST use shape: `{"input": int, "output": int, "total": int}`. If model doesn't provide token counts, values MUST be `None` (not omitted).
- `results` array MUST be ordered exactly as filtered input sequence, one entry per item, regardless of success/failure.
- When `continue_on_error=False`, batch stops at first hard failure but returns results for all processed items (with `failed >= 1`).

**Edge case behaviors:**

- **Empty after filtering**: If date filtering removes all items, `batch()` MUST succeed and return:
  ```python
  {"count": 0, "succeeded": 0, "failed": 0, "results": [], "written": None, "total_tokens": {"input": 0, "output": 0, "total": 0}}
  ```

- **output=None**:
  - `prompt()` and `prompt_with_context()`: Do not write to disk; return `written=None`
  - `batch()`: Skip disk write; return `written=None`

- **rate_limit_rpm=None**: No rate limiting applied. No throttling, no default RPM, no sleep calls.

- **Batch output format**: MUST be written as a JSON array (not JSONL, not Markdown). Array ordering MUST match processed item order.

- **continue_on_error defaults**:
  - `continue_on_error=None` AND `accumulate=False` → default to `True`
  - `continue_on_error=None` AND `accumulate=True` → default to `False` (fail fast)
  - Explicit user value ALWAYS overrides default logic

This enables:
- Post-hoc debugging of specific failures
- Token cost accounting
- Idempotency checks via call_id
- Retry of only failed items
- Deterministic replay and downstream merging

### Operational Notes

**Packaging vs Runtime**:
- `llm` is an **optional PyPI dependency** - `pip install life-cli` works without it
- `llm` is **operationally required** in production environments running generate jobs
- Enforce at deployment/bootstrap, not inside job functions
- CI must test both paths: with and without llm installed

**Job Bundle Policy**:
- Jobs that call `life_jobs.generate.*` MUST NOT be included in default job bundles for environments without the `llm` extra installed
- Include a health-check job to verify llm availability explicitly:

```yaml
jobs:
  llm_healthcheck:
    description: "Verify llm library is available and configured"
    steps:
      - name: ping
        call: life_jobs.generate.prompt
        args:
          prompt: "Respond with exactly: OK"
          model: gpt-4o-mini
```

**Accumulation Mode Behavior**:
When `accumulate=True`, failures break the chain because each result feeds into the next prompt.
- If `continue_on_error` not explicitly passed and `accumulate=True`: automatically set to `False` (fail fast)
- If `continue_on_error` explicitly passed: honor that value (user knows what they're doing)

**Rate Limiter Testability**:
The `RateLimiter` implementation MUST accept injectable `time_func` and `sleep_func` parameters so tests can verify behavior without wall-clock sleeps. Tests should use a fake clock and assert call counts / simulated sleep durations.

## Models & Tools

**Tools:** bash, pytest, ruff

**Models:** (to be filled by defaults)

## Repository

**Branch:** `feat/llm-processing`

**Merge Strategy:** squash
