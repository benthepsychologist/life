# Copyright 2025 Ben Mensi
# SPDX-License-Identifier: Apache-2.0

"""
Executor for Life-CLI.

Wraps lorchestra pipelines and jobs.
"""

import csv
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import lorchestra
from lorchestra import execute
from lorchestra.pipeline import load_pipeline, run_pipeline as lorchestra_run_pipeline

# Lorchestra's job definitions directory
LORCHESTRA_JOBS_DIR = Path(lorchestra.__file__).parent / "jobs" / "definitions"

# Set default storacle namespace if not already set
if "STORACLE_NAMESPACE_SALT" not in os.environ:
    os.environ["STORACLE_NAMESPACE_SALT"] = "storacle-dev"


def render_status(result: Any) -> None:
    """Render pipeline/job result as status. Exits with code 1 on failure."""
    success = getattr(result, "success", True)
    print(f"Status: {'ok' if success else 'FAILED'}")
    if hasattr(result, "run_id"):
        print(f"Run ID: {result.run_id}")
    if hasattr(result, "rows_read"):
        print(f"Rows read: {result.rows_read}")
    if hasattr(result, "rows_written"):
        print(f"Rows written: {result.rows_written}")
    if hasattr(result, "failed_jobs") and result.failed_jobs:
        print("Failed jobs:")
        for job in result.failed_jobs:
            print(f"  - {job}")
    if not success:
        sys.exit(1)


def render_rows(result: Any, format_type: str) -> None:
    """Render result rows."""
    rows = []

    # Try to get rows from step output file (lorchestra stores outputs in files)
    if hasattr(result, "attempt"):
        outcome = result.attempt.get_outcome("read")
        if outcome and outcome.output_ref:
            import json as _json
            output_path = outcome.output_ref.replace("file://", "")
            try:
                with open(output_path) as f:
                    output = _json.load(f)
                rows = output.get("items", [])
            except (FileNotFoundError, _json.JSONDecodeError):
                pass

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


def _render_table(rows: list) -> None:
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


def run_pipeline(target: str, smoke_namespace: Optional[str] = None, verbose: bool = False) -> None:
    """Run a lorchestra pipeline."""
    pipeline_map = {
        "ingest": "pipeline.ingest",
        "canonize": "pipeline.canonize",
        "formation": "pipeline.formation",
        "project": "pipeline.project",
        "views": "pipeline.views",
        "run-all": "pipeline.daily_all",
    }
    pipeline_id = pipeline_map.get(target)
    if not pipeline_id:
        print(f"Unknown pipeline: {target}", file=sys.stderr)
        sys.exit(1)

    if verbose:
        print(f"Executing pipeline: {pipeline_id}")

    # Load and run the pipeline
    spec = load_pipeline(pipeline_id, LORCHESTRA_JOBS_DIR)
    result = lorchestra_run_pipeline(spec, smoke_namespace=smoke_namespace, definitions_dir=LORCHESTRA_JOBS_DIR)
    render_status(result)


def run_peek(target: str, id: Optional[str] = None, limit: int = 20, format: str = "table", verbose: bool = False) -> None:
    """Run a peek job."""
    job_map = {
        "clients": "peek.clients",
        "sessions": "peek.sessions",
        "form-responses": "peek.form_responses",
        "raw-objects": "peek.raw_objects",
        "canonical-objects": "peek.canonical_objects",
        "measurement-events": "peek.measurement_events",
        "observations": "peek.observations",
    }
    job_id = job_map.get(target)
    if not job_id:
        print(f"Unknown table: {target}", file=sys.stderr)
        sys.exit(1)

    if verbose:
        print(f"Executing: {job_id}")

    # Build envelope for peek job
    filters = [{"column": "id", "op": "=", "value": id}] if id else []
    payload: Dict[str, Any] = {
        "limit": limit,
        "filters": filters,
        "order_by": None,
    }

    envelope = {
        "job_id": job_id,
        "payload": payload,
        "ctx": {"source": "life-cli"},
        "definitions_dir": LORCHESTRA_JOBS_DIR,
    }

    result = execute(envelope)
    render_rows(result, format)
