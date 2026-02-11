# Copyright 2025 Ben Mensi
# SPDX-License-Identifier: Apache-2.0

"""
Compiler - Transform JobDef YAML + context into JobInstance.

Resolves compile-time references:
- @ctx.* from context dict
- @payload.* from payload dict
- @self.* from entire JobDef YAML dict

Preserves @run.* for runtime resolution by executor.

Supports dynamic keys: @self.tables.@payload.target.dataset
- First resolves @payload.target → "clients"
- Then resolves @self.tables.clients.dataset
"""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from life.schemas import JobInstance, StepInstance


# Job definitions directory
JOBS_DIR = Path(__file__).parent / "jobs" / "definitions"


class CompileError(Exception):
    """Raised when compilation fails."""
    pass


def _utcnow() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


def load_job_yaml(job_id: str) -> Dict[str, Any]:
    """Load a job definition YAML by ID."""
    yaml_path = JOBS_DIR / f"{job_id}.yaml"
    if not yaml_path.exists():
        raise CompileError(f"Job not found: {job_id}")
    return yaml.safe_load(yaml_path.read_text())


def compile_job(
    job_def: Dict[str, Any],
    ctx: Optional[Dict[str, Any]] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> JobInstance:
    """
    Compile JobDef YAML → JobInstance.

    Args:
        job_def: The entire YAML dict (available via @self.*)
        ctx: Context dict (available via @ctx.*)
        payload: Payload dict (available via @payload.*)

    Returns:
        JobInstance ready for execution
    """
    ctx = ctx or {}
    payload = payload or {}

    # Merge defaults into payload
    defaults = job_def.get("defaults", {})
    merged_payload = {**defaults, **payload}

    compiled_steps = []
    for step_data in job_def.get("steps", []):
        resolved_params = _resolve_value(
            step_data.get("params", {}),
            ctx=ctx,
            payload=merged_payload,
            self_data=job_def,
        )
        compiled_steps.append(StepInstance(
            step_id=step_data["step_id"],
            op=step_data["op"],
            params=resolved_params,
            timeout_s=step_data.get("timeout_s", 300),
            continue_on_error=step_data.get("continue_on_error", False),
        ))

    return JobInstance(
        job_id=job_def["job_id"],
        job_version=job_def.get("version", "1.0"),
        compiled_at=_utcnow(),
        steps=tuple(compiled_steps),
    )


def _resolve_value(
    value: Any,
    ctx: Dict[str, Any],
    payload: Dict[str, Any],
    self_data: Dict[str, Any],
) -> Any:
    """
    Recursively resolve references in a value.

    Resolves @ctx.*, @payload.*, @self.* references.
    Preserves @run.* for runtime resolution.
    Supports dynamic keys like @self.tables.@payload.target.dataset
    """
    if isinstance(value, str):
        if value.startswith("@run."):
            # Preserve for runtime
            return value
        if value.startswith("@"):
            return _resolve_reference(value, ctx, payload, self_data)
        return value
    elif isinstance(value, dict):
        return {k: _resolve_value(v, ctx, payload, self_data) for k, v in value.items()}
    elif isinstance(value, list):
        return [_resolve_value(v, ctx, payload, self_data) for v in value]
    else:
        return value


def _resolve_reference(
    ref: str,
    ctx: Dict[str, Any],
    payload: Dict[str, Any],
    self_data: Dict[str, Any],
) -> Any:
    """
    Resolve a reference string with dynamic key support.

    Examples:
        @ctx.dry_run → ctx["dry_run"]
        @payload.target → payload["target"]
        @self.tables.clients.dataset → self_data["tables"]["clients"]["dataset"]
        @self.tables.@payload.target.dataset → first resolve @payload.target, then navigate

    Dynamic key: when a path segment starts with @, resolve it first.
    """
    # First, expand any embedded dynamic keys in the path
    # "@self.tables.@payload.target.dataset" → "@self.tables.clients.dataset"
    expanded_ref = _expand_dynamic_keys(ref, ctx, payload, self_data)

    # Now resolve the expanded reference
    return _navigate_reference(expanded_ref, ctx, payload, self_data)


def _expand_dynamic_keys(
    ref: str,
    ctx: Dict[str, Any],
    payload: Dict[str, Any],
    self_data: Dict[str, Any],
) -> str:
    """
    Expand dynamic keys in a reference path.

    "@self.tables.@payload.target.dataset"
    → Split into segments, resolve @payload.target → "clients"
    → "@self.tables.clients.dataset"
    """
    # Pattern to find embedded refs like .@payload.xxx. or .@ctx.xxx.
    # We need to find @payload.xxx or @ctx.xxx that appear as path segments
    pattern = re.compile(r'\.@(ctx|payload)\.([a-zA-Z_][a-zA-Z0-9_]*)')

    def replace_dynamic_key(match):
        namespace = match.group(1)
        key = match.group(2)
        if namespace == "ctx":
            value = ctx.get(key)
        else:  # payload
            value = payload.get(key)

        if value is None:
            raise CompileError(f"Dynamic key not found: @{namespace}.{key}")
        if not isinstance(value, (str, int)):
            raise CompileError(f"Dynamic key must be string or int: @{namespace}.{key}")
        return f".{value}"

    return pattern.sub(replace_dynamic_key, ref)


def _navigate_reference(
    ref: str,
    ctx: Dict[str, Any],
    payload: Dict[str, Any],
    self_data: Dict[str, Any],
) -> Any:
    """
    Navigate a reference path to get the value.

    @ctx.key.subkey → ctx["key"]["subkey"]
    @payload.key → payload["key"]
    @self.tables.clients.dataset → self_data["tables"]["clients"]["dataset"]
    """
    # Parse the reference
    if not ref.startswith("@"):
        raise CompileError(f"Invalid reference: {ref}")

    # Split: "@self.tables.clients" → ["@self", "tables", "clients"]
    parts = ref.split(".")
    namespace_part = parts[0]  # "@self", "@ctx", "@payload"
    path_parts = parts[1:]

    # Select source dict
    if namespace_part == "@ctx":
        source = ctx
    elif namespace_part == "@payload":
        source = payload
    elif namespace_part == "@self":
        source = self_data
    else:
        raise CompileError(f"Unknown namespace: {namespace_part}")

    # Navigate path
    value = source
    for part in path_parts:
        if isinstance(value, dict):
            if part not in value:
                # For @ctx and @payload, missing keys return None (optional)
                # For @self, missing keys are an error (must exist in YAML)
                if namespace_part in ("@ctx", "@payload"):
                    return None
                raise CompileError(f"Path not found: {ref} (missing '{part}')")
            value = value[part]
        elif isinstance(value, list):
            try:
                idx = int(part)
                value = value[idx]
            except (ValueError, IndexError):
                raise CompileError(f"Invalid list index in {ref}: {part}")
        else:
            raise CompileError(f"Cannot navigate into {type(value).__name__} at '{part}' in {ref}")

    return value
