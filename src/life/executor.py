# Copyright 2025 Ben Mensi
# SPDX-License-Identifier: Apache-2.0

"""
Executor - Execute compiled JobInstance.

Resolves @run.* references at runtime from previous step outputs.
Dispatches ops (currently only lorchestra.run).
Produces RunRecord with step outcomes.
"""

import csv
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import lorchestra
from lorchestra import execute as lorchestra_execute
from lorchestra.pipeline import load_pipeline, run_pipeline as lorchestra_run_pipeline

from life.schemas import JobInstance, StepInstance, StepOutcome, RunRecord


# Lorchestra's job definitions directory
LORCHESTRA_JOBS_DIR = Path(lorchestra.__file__).parent / "jobs" / "definitions"

# Set default storacle namespace if not already set
if "STORACLE_NAMESPACE_SALT" not in os.environ:
    os.environ["STORACLE_NAMESPACE_SALT"] = "storacle-dev"


def _utcnow() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


# =============================================================================
# @run.* Resolution
# =============================================================================

# Pattern for @run.* references: @run.step_id.path.to.value
# Supports array indexing: @run.step_id.items[0].field
RUN_REF_PATTERN = re.compile(r"@run\.([a-zA-Z_][a-zA-Z0-9_.\[\]]*)")


def _resolve_run_refs(value: Any, step_outputs: Dict[str, Any]) -> Any:
    """
    Resolve @run.* references using previous step outputs.

    @run.step_id.path → step_outputs["step_id"]["path"]
    @run.step_id.items[0].field → step_outputs["step_id"]["items"][0]["field"]
    """
    if isinstance(value, str):
        if value.startswith("@run."):
            match = RUN_REF_PATTERN.match(value)
            if match:
                path = match.group(1)
                parts = path.split(".")
                step_id = parts[0]

                if step_id not in step_outputs:
                    raise ValueError(f"@run reference to unknown step: {step_id}")

                result = step_outputs[step_id]
                for part in parts[1:]:
                    # Handle array indexing: items[0]
                    array_match = re.match(r"(\w+)\[(\d+)\]", part)
                    if array_match:
                        key, idx = array_match.groups()
                        if isinstance(result, dict) and key in result:
                            result = result[key]
                        else:
                            raise ValueError(f"@run path not found: {value} (missing '{key}')")
                        if isinstance(result, list) and int(idx) < len(result):
                            result = result[int(idx)]
                        else:
                            raise ValueError(f"@run index out of bounds: {value}")
                    elif isinstance(result, dict) and part in result:
                        result = result[part]
                    else:
                        raise ValueError(f"@run path not found: {value} (missing '{part}')")
                return result
        return value
    elif isinstance(value, dict):
        return {k: _resolve_run_refs(v, step_outputs) for k, v in value.items()}
    elif isinstance(value, list):
        return [_resolve_run_refs(v, step_outputs) for v in value]
    else:
        return value


# =============================================================================
# Op Dispatch
# =============================================================================

def _dispatch_op(step: StepInstance, resolved_params: Dict[str, Any], ctx: Dict[str, Any]) -> StepOutcome:
    """Dispatch a step's op to the appropriate handler."""
    if step.op == "lorchestra.run":
        return _handle_lorchestra_run(step.step_id, resolved_params, ctx)
    elif step.op == "file.read":
        return _handle_file_read(step.step_id, resolved_params, ctx)
    else:
        return StepOutcome(
            step_id=step.step_id,
            status="failed",
            error=f"Unknown op: {step.op}",
        )


def _handle_file_read(step_id: str, params: Dict[str, Any], ctx: Dict[str, Any]) -> StepOutcome:
    """
    Handle the file.read op - read a file and return its content.

    Note: file.read always executes (even in dry_run mode) because it's a local
    operation and subsequent steps need the content for @run.* resolution.
    """
    try:
        file_path = params.get("path")
        if not file_path:
            return StepOutcome(
                step_id=step_id,
                status="failed",
                error="file.read requires 'path' parameter",
            )

        path = Path(file_path).expanduser()
        if not path.is_absolute():
            return StepOutcome(
                step_id=step_id,
                status="failed",
                error=f"file.read requires absolute path, got: {file_path}",
            )

        if not path.exists():
            return StepOutcome(
                step_id=step_id,
                status="failed",
                error=f"File not found: {path}",
            )

        content = path.read_text()
        return StepOutcome(
            step_id=step_id,
            status="completed",
            output={"content": content, "path": str(path)},
        )
    except Exception as e:
        return StepOutcome(
            step_id=step_id,
            status="failed",
            error=str(e),
        )


def _handle_lorchestra_run(step_id: str, params: Dict[str, Any], ctx: Dict[str, Any]) -> StepOutcome:
    """Handle the lorchestra.run op."""
    try:
        if "pipeline_id" in params:
            # Run a pipeline
            pipeline_id = params["pipeline_id"]
            smoke_namespace = params.get("smoke_namespace")
            dry_run = ctx.get("dry_run", False)

            if dry_run:
                return StepOutcome(
                    step_id=step_id,
                    status="completed",
                    output={"dry_run": True, "pipeline_id": pipeline_id},
                )

            spec = load_pipeline(pipeline_id, LORCHESTRA_JOBS_DIR)
            result = lorchestra_run_pipeline(spec, smoke_namespace=smoke_namespace, definitions_dir=LORCHESTRA_JOBS_DIR)
            return StepOutcome(
                step_id=step_id,
                status="completed" if result.success else "failed",
                output=_result_to_dict(result),
            )
        else:
            # Run a job
            job_id = params.get("job_id")
            job_payload = params.get("payload", {})
            dry_run = ctx.get("dry_run", False)

            if dry_run:
                return StepOutcome(
                    step_id=step_id,
                    status="completed",
                    output={"dry_run": True, "job_id": job_id, "payload": job_payload},
                )

            envelope = {
                "job_id": job_id,
                "payload": job_payload,
                "ctx": {"source": "life-cli"},
                "definitions_dir": LORCHESTRA_JOBS_DIR,
            }

            result = lorchestra_execute(envelope)
            return StepOutcome(
                step_id=step_id,
                status="completed" if result.success else "failed",
                output=_result_to_dict(result),
            )
    except Exception as e:
        return StepOutcome(
            step_id=step_id,
            status="failed",
            error=str(e),
        )


def _result_to_dict(result: Any) -> Dict[str, Any]:
    """Convert a lorchestra result to a dict for step output."""
    output = {}
    if hasattr(result, "run_id"):
        output["run_id"] = result.run_id
    if hasattr(result, "success"):
        output["success"] = result.success
    if hasattr(result, "attempt"):
        # Try to extract rows from peek jobs
        try:
            outcome = result.attempt.get_outcome("read")
            if outcome and outcome.output_ref:
                output_path = outcome.output_ref.replace("file://", "")
                with open(output_path) as f:
                    data = json.load(f)
                output["items"] = data.get("items", [])
        except Exception:
            pass
    return output


# =============================================================================
# Job Execution
# =============================================================================

def execute(instance: JobInstance, ctx: Optional[Dict[str, Any]] = None) -> RunRecord:
    """
    Execute a compiled JobInstance.

    Resolves @run.* references at runtime.
    Dispatches each step's op.
    Returns RunRecord with outcomes.
    """
    ctx = ctx or {}
    run_id = str(uuid.uuid4())
    started_at = _utcnow()
    step_outputs: Dict[str, Any] = {}
    outcomes: List[StepOutcome] = []
    success = True

    for step in instance.steps:
        # Resolve @run.* refs from previous outputs
        try:
            resolved_params = _resolve_run_refs(step.params, step_outputs)
        except ValueError as e:
            outcome = StepOutcome(
                step_id=step.step_id,
                status="failed",
                error=str(e),
            )
            outcomes.append(outcome)
            if not step.continue_on_error:
                success = False
                break
            continue

        # Dispatch the op
        outcome = _dispatch_op(step, resolved_params, ctx)
        outcomes.append(outcome)

        # Store output for @run.* resolution by later steps
        if outcome.output is not None:
            step_outputs[step.step_id] = outcome.output

        # Check for failure
        if outcome.status == "failed" and not step.continue_on_error:
            success = False
            break

    return RunRecord(
        run_id=run_id,
        job_id=instance.job_id,
        success=success,
        started_at=started_at,
        completed_at=_utcnow(),
        outcomes=outcomes,
    )


# =============================================================================
# Output Rendering
# =============================================================================

def render_run_record(record: RunRecord, format_type: str = "table") -> None:
    """Render a RunRecord to stdout."""
    if not record.success:
        print(f"Job {record.job_id} FAILED", file=sys.stderr)
        for outcome in record.outcomes:
            if outcome.status == "failed":
                print(f"  Step '{outcome.step_id}': {outcome.error}", file=sys.stderr)
        sys.exit(1)

    # Check if any outcome has items (peek job)
    for outcome in record.outcomes:
        if outcome.output and isinstance(outcome.output, dict):
            items = outcome.output.get("items")
            if items is not None:
                _render_rows(items, format_type)
                return

    # Otherwise render status
    _render_status(record)


def _render_rows(rows: List[Dict], format_type: str) -> None:
    """Render rows in the specified format."""
    if format_type == "json":
        for row in rows:
            print(json.dumps(row))
    elif format_type == "csv":
        if rows:
            writer = csv.DictWriter(sys.stdout, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    else:
        _render_table(rows)


def _render_table(rows: List[Dict]) -> None:
    """Render rows as a simple table."""
    if not rows:
        print("(no rows)")
        return
    keys = list(rows[0].keys())
    widths = {k: max(len(str(k)), max(len(str(r.get(k, ""))) for r in rows)) for k in keys}
    header = " | ".join(str(k).ljust(widths[k]) for k in keys)
    print(header)
    print("-" * len(header))
    for row in rows:
        print(" | ".join(str(row.get(k, "")).ljust(widths[k]) for k in keys))


def _render_status(record: RunRecord) -> None:
    """Render run record as status."""
    print(f"Job: {record.job_id}")
    print(f"Run ID: {record.run_id}")
    print(f"Status: {'ok' if record.success else 'FAILED'}")
    print(f"Steps: {len(record.outcomes)}")
