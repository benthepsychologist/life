"""LLM prompt processing via the llm library.

Implementation rules enforced here (Rule 8):
- Never print
- Never read global config or environment (except Path.expanduser)
- Always return simple dicts
- Side effects: file IO, LLM API calls only

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# Import guard: llm is an optional dependency
_LLM_AVAILABLE = False
try:
    import llm as _llm

    _LLM_AVAILABLE = True
except ImportError:
    _llm = None


def _require_llm() -> None:
    """Raise clear error if llm library not installed."""
    if not _LLM_AVAILABLE:
        raise ImportError(
            "llm library not installed. Install with: pip install 'life-cli[llm]'"
        )


def _expand_path(path: str) -> Path:
    """Expand ~ in paths."""
    return Path(path).expanduser()


def _resolve_template(template: str) -> str:
    """Resolve inline text or file path to template content.

    If template looks like a path (starts with ~ or /) and the file exists,
    read its contents. Otherwise, return the template as-is.
    """
    if template.startswith(("~", "/")):
        path = _expand_path(template)
        if path.exists() and path.is_file():
            return path.read_text()
    return template


def _smart_order_files(files: List[Path]) -> List[Path]:
    """Order context files intelligently.

    Order:
    1. baseline.json first
    2. Files matching session*delta*
    3. Files containing 'metrics'
    4. All remaining files alphabetically
    """
    baseline = []
    session_delta = []
    metrics = []
    rest = []

    for f in files:
        name = f.name.lower()
        stem = f.stem.lower()
        if name == "baseline.json":
            baseline.append(f)
        elif re.match(r"session.*delta", stem):
            session_delta.append(f)
        elif "metrics" in stem:
            metrics.append(f)
        else:
            rest.append(f)

    # Sort each group alphabetically, then concatenate
    return (
        sorted(baseline)
        + sorted(session_delta)
        + sorted(metrics)
        + sorted(rest)
    )


def _assemble_context(prompt_text: str, files: List[Path]) -> str:
    """Build markdown-formatted context from files.

    Each file becomes a markdown section with its content in a code block.
    JSON files are pretty-printed.
    """
    blocks = ["# CONTEXT\n"]
    for f in files:
        content = f.read_text()
        title = f.stem.replace("_", " ").title()
        if f.suffix == ".json":
            try:
                data = json.loads(content)
                pretty = json.dumps(data, indent=2)
                blocks.append(f"## {title}\n\n```json\n{pretty}\n```\n")
            except json.JSONDecodeError:
                blocks.append(f"## {title}\n\n{content}\n")
        else:
            blocks.append(f"## {title}\n\n{content}\n")
    return f"{prompt_text.strip()}\n\n---\n\n" + "\n".join(blocks)


def _is_retryable(error: Exception) -> bool:
    """Determine if error is transient and worth retrying."""
    error_str = str(error).lower()
    retryable_patterns = [
        "rate limit",
        "429",
        "timeout",
        "503",
        "502",
        "connection",
        "temporarily unavailable",
    ]
    return any(p in error_str for p in retryable_patterns)


def _retry_with_backoff(
    func: Callable[[], Any],
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    sleep_func: Optional[Callable[[float], None]] = None,
) -> Any:
    """Execute function with retry on transient errors."""
    _sleep = sleep_func or time.sleep
    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            last_error = e
            if not _is_retryable(e) or attempt == max_retries:
                raise
            sleep_time = delay * (backoff**attempt)
            _sleep(sleep_time)

    raise last_error  # Should never reach here, but satisfies type checker


class RateLimiter:
    """Token bucket rate limiter with injectable clock for testing."""

    def __init__(
        self,
        rpm: int,
        time_func: Optional[Callable[[], float]] = None,
        sleep_func: Optional[Callable[[float], None]] = None,
    ):
        self.interval = 60.0 / rpm
        self.last_call = 0.0
        self._time = time_func or time.time
        self._sleep = sleep_func or time.sleep

    def wait(self) -> None:
        """Block until rate limit allows next call."""
        now = self._time()
        elapsed = now - self.last_call
        if elapsed < self.interval:
            self._sleep(self.interval - elapsed)
        self.last_call = self._time()


def _extract_tokens(response: Any) -> Dict[str, Optional[int]]:
    """Extract token usage from llm response.

    Returns dict with input, output, total keys. Values are None if unavailable.
    """
    try:
        # llm library stores token info in response object
        input_tokens = getattr(response, "input_tokens", None)
        output_tokens = getattr(response, "output_tokens", None)

        if input_tokens is not None and output_tokens is not None:
            total = input_tokens + output_tokens
        elif input_tokens is not None or output_tokens is not None:
            total = (input_tokens or 0) + (output_tokens or 0)
        else:
            total = None

        return {
            "input": input_tokens,
            "output": output_tokens,
            "total": total,
        }
    except Exception:
        return {"input": None, "output": None, "total": None}


def prompt(
    prompt: str,
    *,
    system: Optional[str] = None,
    model: Optional[str] = None,
    output: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a single LLM prompt.

    Args:
        prompt: The prompt text (inline string or path to file via expanduser)
        system: Optional system prompt for context
        model: Model identifier (default: gpt-4o-mini)
        output: Optional path to write response (expanduser applied)

    Returns:
        Dict with keys: output, model, tokens, written
    """
    _require_llm()

    model_name = model or "gpt-4o-mini"
    llm_model = _llm.get_model(model_name)

    prompt_text = _resolve_template(prompt)
    response = llm_model.prompt(prompt_text, system=system)
    response_text = response.text()

    tokens = _extract_tokens(response)

    result: Dict[str, Any] = {
        "output": response_text,
        "model": model_name,
        "tokens": tokens,
        "written": None,
    }

    if output:
        output_path = _expand_path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(response_text)
        result["written"] = str(output_path)

    return result


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

    Context files are assembled as markdown blocks:
    - Each file becomes: "## {filename}\n```json\n{content}\n```"
    - smart_order: baseline.json first, then session*delta, then metrics, then rest

    Args:
        prompt: The prompt text
        context_files: List of file paths to include as context
        system: Optional system prompt
        model: Model identifier (default: gpt-4o-mini)
        output: Optional path to write response
        smart_order: Whether to reorder context files intelligently

    Returns:
        Dict with keys: output, model, context_files, tokens, written
    """
    _require_llm()

    model_name = model or "gpt-4o-mini"
    llm_model = _llm.get_model(model_name)

    prompt_text = _resolve_template(prompt)

    # Resolve and optionally order context files
    resolved_files = [_expand_path(f) for f in context_files]
    if smart_order:
        resolved_files = _smart_order_files(resolved_files)

    assembled_prompt = _assemble_context(prompt_text, resolved_files)

    response = llm_model.prompt(assembled_prompt, system=system)
    response_text = response.text()

    tokens = _extract_tokens(response)

    result: Dict[str, Any] = {
        "output": response_text,
        "model": model_name,
        "context_files": [str(f) for f in resolved_files],
        "tokens": tokens,
        "written": None,
    }

    if output:
        output_path = _expand_path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(response_text)
        result["written"] = str(output_path)

    return result


def batch(
    items_file: str,
    prompt: str,
    output: Optional[str] = None,
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
    rate_limit_rpm: Optional[int] = None,
    continue_on_error: Optional[bool] = None,
    # Testing hooks
    _time_func: Optional[Callable[[], float]] = None,
    _sleep_func: Optional[Callable[[float], None]] = None,
) -> Dict[str, Any]:
    """Process JSON array through LLM, optionally accumulating results.

    Args:
        items_file: Path to JSON array file
        prompt: Template prompt (can include {item} placeholder for JSON item)
        output: Path to write results JSON array
        context_files: Additional context files for each prompt
        system: System prompt
        model: Model identifier
        accumulate: If True, pass previous results to subsequent prompts
        date_key: Field name for date filtering
        start_date: Filter items >= this date (ISO format)
        end_date: Filter items <= this date (ISO format)
        max_retries: Max retry attempts on transient failures
        retry_delay: Initial delay between retries (seconds)
        retry_backoff: Backoff multiplier for retries
        rate_limit_rpm: Requests per minute limit (None = no limit)
        continue_on_error: Continue on failures. Default depends on accumulate mode.
        _time_func: Injectable time function for testing
        _sleep_func: Injectable sleep function for testing

    Returns:
        Dict with keys: count, succeeded, failed, results, written, total_tokens
    """
    _require_llm()

    model_name = model or "gpt-4o-mini"
    llm_model = _llm.get_model(model_name)

    # Resolve continue_on_error default
    if continue_on_error is None:
        # In accumulation mode, fail fast by default
        effective_continue_on_error = not accumulate
    else:
        effective_continue_on_error = continue_on_error

    # Load and filter items
    items_path = _expand_path(items_file)
    items: List[Dict[str, Any]] = json.loads(items_path.read_text())

    filtered_items = []
    for item in items:
        item_date = item.get(date_key)
        if item_date:
            if start_date and item_date < start_date:
                continue
            if end_date and item_date > end_date:
                continue
        filtered_items.append(item)

    # Handle empty case
    if not filtered_items:
        return {
            "count": 0,
            "succeeded": 0,
            "failed": 0,
            "results": [],
            "written": None,
            "total_tokens": {"input": 0, "output": 0, "total": 0},
        }

    # Setup rate limiter if needed
    rate_limiter: Optional[RateLimiter] = None
    if rate_limit_rpm is not None:
        rate_limiter = RateLimiter(
            rate_limit_rpm, time_func=_time_func, sleep_func=_sleep_func
        )

    # Resolve context files once
    resolved_context: List[Path] = []
    if context_files:
        resolved_context = [_expand_path(f) for f in context_files]

    prompt_template = _resolve_template(prompt)

    results: List[Dict[str, Any]] = []
    accumulated_results: List[str] = []
    total_tokens = {"input": 0, "output": 0, "total": 0}
    succeeded = 0
    failed = 0

    _time = _time_func or time.time

    for item in filtered_items:
        call_id = str(uuid.uuid4())
        start_time = _time()

        # Apply rate limiting
        if rate_limiter:
            rate_limiter.wait()

        # Build prompt for this item
        item_json = json.dumps(item, indent=2)

        # Handle accumulation: include previous results in prompt
        if accumulate and accumulated_results:
            accumulated_context = "\n\n## Previous Results\n\n" + "\n\n---\n\n".join(
                accumulated_results
            )
            full_prompt = (
                f"{prompt_template}\n\n## Current Item\n\n```json\n{item_json}\n```"
                f"{accumulated_context}"
            )
        else:
            full_prompt = f"{prompt_template}\n\n## Item\n\n```json\n{item_json}\n```"

        # Add context files if present
        if resolved_context:
            full_prompt = _assemble_context(full_prompt, resolved_context)

        result_entry: Dict[str, Any] = {
            "item": item,
            "call_id": call_id,
            "status": "failed",
            "result": None,
            "error": None,
            "tokens": {"input": None, "output": None, "total": None},
            "model": model_name,
            "duration_ms": 0,
        }

        try:

            def make_call() -> Any:
                return llm_model.prompt(full_prompt, system=system)

            response = _retry_with_backoff(
                make_call,
                max_retries=max_retries,
                delay=retry_delay,
                backoff=retry_backoff,
                sleep_func=_sleep_func,
            )

            response_text = response.text()
            tokens = _extract_tokens(response)

            end_time = _time()
            duration_ms = int((end_time - start_time) * 1000)

            result_entry.update(
                {
                    "status": "success",
                    "result": response_text,
                    "tokens": tokens,
                    "duration_ms": duration_ms,
                }
            )

            # Aggregate tokens
            if tokens["input"] is not None:
                total_tokens["input"] += tokens["input"]
            if tokens["output"] is not None:
                total_tokens["output"] += tokens["output"]
            if tokens["total"] is not None:
                total_tokens["total"] += tokens["total"]

            succeeded += 1

            # Track for accumulation
            if accumulate:
                accumulated_results.append(response_text)

        except Exception as e:
            end_time = _time()
            duration_ms = int((end_time - start_time) * 1000)

            result_entry.update(
                {
                    "status": "failed",
                    "error": str(e),
                    "duration_ms": duration_ms,
                }
            )
            failed += 1

            if not effective_continue_on_error:
                results.append(result_entry)
                break

        results.append(result_entry)

    # Build final result
    batch_result: Dict[str, Any] = {
        "count": len(filtered_items),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
        "written": None,
        "total_tokens": total_tokens,
    }

    # Write output if specified
    if output:
        output_path = _expand_path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(results, indent=2))
        batch_result["written"] = str(output_path)

    return batch_result
