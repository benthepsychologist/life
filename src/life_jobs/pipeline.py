"""Pipeline operations via lorchestra library import.

Implementation rules enforced here (Rule 8):
- Never print
- Never read global config or environment (except Path.expanduser)
- Always return simple dicts
- Side effects: file IO, lorchestra execute() calls only

Transport: lorchestra.execute() direct import
Auth: None (lorchestra handles its own auth)

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from lorchestra import ExecutionResult, execute

# I/O declaration for static analysis and auditing
__io__ = {
    "reads": ["filesystem.vault"],
    "writes": ["filesystem.vault"],
    "external": ["lorchestra.execute"],
}


def _to_bool(value) -> bool:
    """Convert value to boolean, handling string 'true'/'false' from job runner."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    return bool(value)


def run_lorchestra(
    job_id: str,
    dry_run: bool = False,
    verbose: bool = False,
    smoke_namespace: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a lorchestra composite job via direct library import.

    External: lorchestra.execute

    Args:
        job_id: Lorchestra job ID (e.g., "pipeline.ingest")
        dry_run: If True, runs in dry-run mode (accepts string "true"/"false")
        verbose: If True, enables verbose output (accepts string "true"/"false")
        smoke_namespace: If set, routes BQ writes to smoke test namespace

    Returns:
        {job_id, success, run_id, duration_ms, rows_read, rows_written,
         error_message, failed_steps}
    """
    # Convert string values from job runner to booleans
    dry_run = _to_bool(dry_run)
    verbose = _to_bool(verbose)

    # Normalize smoke_namespace (job runner may pass empty string for unset)
    if smoke_namespace == "":
        smoke_namespace = None

    start_time = time.time()

    try:
        # Build envelope for lorchestra.execute()
        envelope: Dict[str, Any] = {
            "job_id": job_id,
            "ctx": {"source": "life-cli"},
        }

        if smoke_namespace:
            envelope["smoke_namespace"] = smoke_namespace

        # Execute via lorchestra library
        result: ExecutionResult = execute(envelope)

        duration_ms = int((time.time() - start_time) * 1000)

        # Build error information from failed steps
        error_message = None
        failed_steps_info: List[Dict[str, Any]] = []
        if not result.success:
            for step in result.failed_steps:
                step_info = {"step_id": step.step_id}
                if step.error:
                    # step.error is a dict with type and message
                    if isinstance(step.error, dict):
                        step_info["error"] = step.error.get("message", str(step.error))
                    else:
                        step_info["error"] = str(step.error)
                failed_steps_info.append(step_info)

            # Build summary error message
            if failed_steps_info:
                first_failure = failed_steps_info[0]
                error_message = f"Step '{first_failure['step_id']}' failed"
                if "error" in first_failure:
                    error_message = f"{error_message}: {first_failure['error']}"

        return {
            "job_id": job_id,
            "success": result.success,
            "run_id": result.run_id,
            "duration_ms": duration_ms,
            "rows_read": result.rows_read,
            "rows_written": result.rows_written,
            "error_message": error_message,
            "failed_steps": failed_steps_info,
        }

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        return {
            "job_id": job_id,
            "success": False,
            "run_id": None,
            "duration_ms": duration_ms,
            "rows_read": 0,
            "rows_written": 0,
            "error_message": f"Failed to execute lorchestra: {e}",
            "failed_steps": [],
        }


def clear_views_directory(
    vault_path: str,
    dry_run: bool = False,
) -> List[str]:
    """Delete all files in {vault_path}/views/ only.

    Writes: filesystem.vault (deletes files)

    Args:
        vault_path: Path to the vault directory (~ will be expanded)
        dry_run: If True, logs what would be deleted without deleting

    Returns:
        List of deleted (or would-be-deleted) file paths
    """
    vault = Path(vault_path).expanduser()
    views_dir = vault / "views"

    if not views_dir.exists():
        return []

    deleted: List[str] = []

    # Delete all files and subdirectories in views/
    for item in views_dir.iterdir():
        item_path = str(item)
        deleted.append(item_path)

        if not dry_run:
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)

    return deleted


def get_vault_statistics(vault_path: str) -> Dict[str, int]:
    """Count files in vault views directory by type.

    Reads: filesystem.vault

    Counts are based on files under {vault_path}/views/, not the entire vault.
    File types are determined by directory name (e.g., views/clients/, views/sessions/).

    Args:
        vault_path: Path to the vault directory (~ will be expanded)

    Returns:
        {clients, sessions, transcripts, notes, summaries, reports}
    """
    vault = Path(vault_path).expanduser()
    views_dir = vault / "views"

    stats = {
        "clients": 0,
        "sessions": 0,
        "transcripts": 0,
        "notes": 0,
        "summaries": 0,
        "reports": 0,
    }

    if not views_dir.exists():
        return stats

    # Count files in each known subdirectory
    for category in stats.keys():
        category_dir = views_dir / category
        if category_dir.exists() and category_dir.is_dir():
            # Count only files, not subdirectories
            stats[category] = sum(1 for f in category_dir.iterdir() if f.is_file())

    return stats
