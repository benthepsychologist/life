"""Step-based job runner.

Implementation rules enforced here:
- No print statements (CLI handles --verbose output)
- YAML errors surface immediately (no silent continue)
- call: restricted to life_jobs.* allowlist
- Unsubstituted {var} placeholders raise errors

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

import importlib
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import yaml

from life.event_client import EventClient

# Allowlist for call: resolution (Rule 3)
ALLOWED_CALL_PREFIXES = ("life_jobs.",)

# Job name must be dotted namespace: <domain>.<action>
JOB_NAME_PATTERN = re.compile(r"^\w+\.\w+$")


class JobLoadError(Exception):
    """Raised when job YAML files fail to load."""

    def __init__(self, errors: List[Tuple[Path, str]]):
        self.errors = errors
        msg = "Failed to load job files:\n" + "\n".join(
            f"  - {path}: {err}" for path, err in errors
        )
        super().__init__(msg)


class CallNotAllowedError(ValueError):
    """Raised when call: path is not in allowlist."""

    pass


class UnsubstitutedVariableError(ValueError):
    """Raised when {var} placeholders remain after substitution."""

    pass


class InvalidJobNameError(ValueError):
    """Raised when job name doesn't match dotted namespace convention."""

    pass


def validate_job_name(job_id: str) -> None:
    """Validate job name matches dotted namespace convention.

    Jobs must use format: <domain>.<action> (e.g., email.send, today.create_note)
    """
    if not JOB_NAME_PATTERN.match(job_id):
        raise InvalidJobNameError(
            f"Invalid job name '{job_id}'. "
            f"Jobs must use dotted namespace: <domain>.<action> (e.g., email.send)"
        )


def resolve_callable(call_path: str) -> Callable:
    """Resolve 'module.submodule.function' to a callable.

    Only allows imports from ALLOWED_CALL_PREFIXES (Rule 3).
    """
    if not any(call_path.startswith(prefix) for prefix in ALLOWED_CALL_PREFIXES):
        raise CallNotAllowedError(
            f"call: '{call_path}' not allowed. Must start with one of: {ALLOWED_CALL_PREFIXES}"
        )
    module_path, func_name = call_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, func_name)


def load_jobs(jobs_dir: Path) -> Dict[str, Dict]:
    """Load all jobs from YAML files in jobs_dir.

    Raises JobLoadError if any YAML file fails to parse (Rule 1).
    """
    all_jobs: Dict[str, Dict] = {}
    errors: List[Tuple[Path, str]] = []

    if not jobs_dir.exists():
        return all_jobs

    for yaml_file in sorted(jobs_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(yaml_file.read_text()) or {}
            jobs = data.get("jobs", {})
            all_jobs.update(jobs)
        except yaml.YAMLError as e:
            errors.append((yaml_file, str(e)))

    if errors:
        raise JobLoadError(errors)

    return all_jobs


def get_job(job_id: str, jobs_dir: Path) -> Dict:
    """Get a single job definition by ID.

    Raises InvalidJobNameError if name doesn't match dotted namespace.
    Raises KeyError if job not found.
    """
    validate_job_name(job_id)
    jobs = load_jobs(jobs_dir)
    if job_id not in jobs:
        raise KeyError(f"Job not found: {job_id}. Available: {list(jobs.keys())}")
    return jobs[job_id]


def list_jobs(jobs_dir: Path) -> List[Dict[str, str]]:
    """List all available jobs."""
    jobs = load_jobs(jobs_dir)
    return [
        {"job_id": job_id, "description": spec.get("description", "")}
        for job_id, spec in sorted(jobs.items())
    ]


def run_job(
    job_id: str,
    *,
    dry_run: bool = False,
    jobs_dir: Path,
    event_log: Path,
    variables: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Run a job by ID.

    Returns stable shape (Rule 6): {"run_id": str, "status": str, "steps": list}
    No print statements (Rule 2) - CLI handles verbose output.
    """
    # Validate job name format
    validate_job_name(job_id)

    # Generate run ID
    run_id = (
        f"{job_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-"
        f"{uuid.uuid4().hex[:8]}"
    )

    # Load job
    jobs = load_jobs(jobs_dir)
    if job_id not in jobs:
        raise KeyError(f"Job not found: {job_id}. Available: {list(jobs.keys())}")

    job_spec = jobs[job_id]
    steps = job_spec.get("steps", [])

    # Event logging
    event_client = EventClient(event_log)
    event_client.log_event(
        "job.started", run_id, "success", {"job_id": job_id, "dry_run": dry_run}
    )

    results: List[Dict[str, Any]] = []
    try:
        for step in steps:
            step_name = step.get("name", "unnamed")
            call_path = step["call"]
            args = step.get("args", {})

            # Substitute variables in args, then check for unsubstituted (Rule 4)
            if variables:
                args = _substitute_variables(args, variables)
            _check_unsubstituted(args, step_name)

            if dry_run:
                results.append(
                    {
                        "step": step_name,
                        "call": call_path,
                        "args": args,
                        "status": "skipped",
                        "dry_run": True,
                    }
                )
                continue

            # Resolve and call function (validates allowlist via Rule 3)
            func = resolve_callable(call_path)
            result = func(**args)

            results.append(
                {
                    "step": step_name,
                    "call": call_path,
                    "status": "success",
                    "result": result,
                }
            )

            event_client.log_event(
                "step.completed",
                run_id,
                "success",
                {"step": step_name, "call": call_path},
            )

        event_client.log_event("job.completed", run_id, "success", {"job_id": job_id})
        return {"run_id": run_id, "status": "success", "steps": results}

    except Exception as e:
        event_client.log_event(
            "job.failed", run_id, "failed", {"job_id": job_id}, str(e)
        )
        raise


# Regex to find {placeholder} patterns
_PLACEHOLDER_RE = re.compile(r"\{([^}]+)\}")


def _substitute_variables(obj: Any, variables: Dict[str, str]) -> Any:
    """Recursively substitute {var} patterns in strings."""
    if isinstance(obj, str):
        for key, value in variables.items():
            obj = obj.replace(f"{{{key}}}", value)
        return obj
    elif isinstance(obj, dict):
        return {k: _substitute_variables(v, variables) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_substitute_variables(item, variables) for item in obj]
    return obj


def _check_unsubstituted(obj: Any, step_name: str) -> None:
    """Check for remaining {var} placeholders and raise if found (Rule 4).

    Known limitation: If literal {} are needed in arguments (e.g., OData filters),
    introduce an escape convention (e.g., {{literal}}) or per-step `allow_unsubstituted: true`.
    Not implemented yet - just document when needed.
    """
    unsubstituted: set = set()
    _collect_unsubstituted(obj, unsubstituted)
    if unsubstituted:
        raise UnsubstitutedVariableError(
            f"Step '{step_name}' has unsubstituted variables: {sorted(unsubstituted)}"
        )


def _collect_unsubstituted(obj: Any, found: set) -> None:
    """Recursively collect unsubstituted {var} names."""
    if isinstance(obj, str):
        for match in _PLACEHOLDER_RE.finditer(obj):
            found.add(match.group(1))
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_unsubstituted(v, found)
    elif isinstance(obj, list):
        for item in obj:
            _collect_unsubstituted(item, found)
