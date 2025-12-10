"""Writeback operations for syncing markdown changes back to Dataverse.

Implementation rules enforced here (Rule 8):
- Never print
- Never read global config or environment (except Path.expanduser)
- Always return simple dicts
- Side effects: file IO, morch API calls, state updates only

Writeback flow:
1. plan_writeback() - Scan vault for changed files, produce plan JSON
2. apply_writeback() - Load plan and PATCH changes to Dataverse

Frontmatter requirements:
- entity: Dataverse entity name (e.g., "cre92_clientsessions")
- record_id: Dataverse record GUID
- projected_at: ISO timestamp of when file was last projected
- editable_fields: dict mapping Dataverse field → frontmatter key or "body"

Change detection:
- file_mtime > projected_at + EPSILON (2 seconds)

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

# I/O declaration for static analysis and auditing
__io__ = {
    "reads": ["vault_root/**/*.md", "plan_path"],
    "writes": ["plan_path"],
    "external": ["dataverse.patch"],
}

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from morch import DataverseClient

# Epsilon for time comparison (covers filesystem resolution + processing latency)
EPSILON = 2.0


def _parse_frontmatter(file_path: Path) -> tuple[dict[str, Any] | None, str]:
    """Parse YAML frontmatter from a markdown file.

    Args:
        file_path: Path to the markdown file

    Returns:
        Tuple of (frontmatter dict or None, body content)
    """
    content = file_path.read_text()

    if not content.startswith("---"):
        return None, content

    # Find closing delimiter
    end_idx = content.find("\n---", 3)
    if end_idx == -1:
        return None, content

    frontmatter_yaml = content[4:end_idx]  # Skip opening "---\n"
    body = content[end_idx + 4:].lstrip("\n")  # Skip closing "---\n"

    try:
        frontmatter = yaml.safe_load(frontmatter_yaml)
        if not isinstance(frontmatter, dict):
            return None, content
        return frontmatter, body
    except yaml.YAMLError:
        return None, content


def _is_file_changed(file_path: Path, projected_at_str: str) -> bool:
    """Check if file has been modified since projection.

    Args:
        file_path: Path to the file
        projected_at_str: ISO timestamp string from frontmatter

    Returns:
        True if file_mtime > projected_at + EPSILON
    """
    projected_at_dt = datetime.fromisoformat(projected_at_str)
    projected_at_ts = projected_at_dt.timestamp()
    file_mtime = os.path.getmtime(file_path)

    return file_mtime > projected_at_ts + EPSILON


def _build_patch(
    frontmatter: dict[str, Any],
    body: str,
    editable_fields: dict[str, str],
) -> dict[str, Any]:
    """Build Dataverse patch payload from frontmatter and body.

    Args:
        frontmatter: Parsed frontmatter dict
        body: Markdown body content
        editable_fields: Mapping of Dataverse field → source key
            Source key can be a frontmatter key or "body" for markdown content

    Returns:
        Dict of Dataverse fields to update
    """
    patch = {}
    for dv_field, source_key in editable_fields.items():
        if source_key == "body":
            patch[dv_field] = body
        elif source_key in frontmatter:
            value = frontmatter[source_key]
            if value is not None:
                patch[dv_field] = value

    return patch


def plan_writeback(
    vault_root: str,
    plan_path: str,
    glob_pattern: str = "**/*.md",
    db_path: str | None = None,  # Reserved for future baseline validation
) -> dict[str, Any]:
    """Scan vault and build writeback plan for changed files.

    Args:
        vault_root: Root directory to scan (e.g., "~/clinical-vault/views")
        plan_path: Path to write the plan JSON (e.g., "~/.life/writeback/plan.json")
        glob_pattern: Glob pattern for files to scan (default: "**/*.md")
        db_path: Optional SQLite path for baseline validation (not yet implemented)

    Returns:
        Summary dict with files_scanned, files_changed, files_skipped, errors, plan_path
    """
    vault_root_path = Path(vault_root).expanduser()
    plan_path_expanded = Path(plan_path).expanduser()

    files_scanned = 0
    files_changed = 0
    files_skipped = 0
    errors: list[dict[str, str]] = []
    operations: list[dict[str, Any]] = []

    # Required frontmatter keys for writeback
    required_keys = {"entity", "record_id", "projected_at", "editable_fields"}

    for file_path in vault_root_path.glob(glob_pattern):
        if not file_path.is_file():
            continue

        files_scanned += 1

        # Parse frontmatter
        frontmatter, body = _parse_frontmatter(file_path)

        if frontmatter is None:
            files_skipped += 1
            continue

        # Check required keys
        missing_keys = required_keys - set(frontmatter.keys())
        if missing_keys:
            files_skipped += 1
            errors.append({
                "path": str(file_path.relative_to(vault_root_path)),
                "reason": f"Missing required keys: {', '.join(sorted(missing_keys))}",
            })
            continue

        # Validate editable_fields is a dict
        editable_fields = frontmatter.get("editable_fields")
        if not isinstance(editable_fields, dict) or not editable_fields:
            files_skipped += 1
            errors.append({
                "path": str(file_path.relative_to(vault_root_path)),
                "reason": "editable_fields must be a non-empty dict",
            })
            continue

        # Check if file is changed
        try:
            if not _is_file_changed(file_path, frontmatter["projected_at"]):
                # Not changed, skip silently
                continue
        except (ValueError, TypeError) as e:
            files_skipped += 1
            errors.append({
                "path": str(file_path.relative_to(vault_root_path)),
                "reason": f"Invalid projected_at timestamp: {e}",
            })
            continue

        # Build patch payload
        patch = _build_patch(frontmatter, body, editable_fields)

        if not patch:
            # No fields to update (all source keys missing/None)
            continue

        files_changed += 1
        operations.append({
            "entity": frontmatter["entity"],
            "id": frontmatter["record_id"],
            "source_path": str(file_path.relative_to(vault_root_path)),
            "patch": patch,
        })

    # Write plan file
    plan = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "vault_root": str(vault_root_path),
        "operations": operations,
    }

    plan_path_expanded.parent.mkdir(parents=True, exist_ok=True)
    plan_path_expanded.write_text(json.dumps(plan, indent=2, default=str))

    return {
        "files_scanned": files_scanned,
        "files_changed": files_changed,
        "files_skipped": files_skipped,
        "errors": errors,
        "plan_path": str(plan_path_expanded),
    }


def apply_writeback(
    account: str,
    plan_path: str = "~/.life/writeback/plan.json",
) -> dict[str, Any]:
    """Apply writeback plan to Dataverse.

    Args:
        account: authctl account name for Dataverse authentication
        plan_path: Path to the plan JSON file

    Returns:
        Summary dict with operations, succeeded, failed, errors
    """
    plan_path_expanded = Path(plan_path).expanduser()

    # Load plan
    plan = json.loads(plan_path_expanded.read_text())

    # Validate version
    if plan.get("version") != 1:
        raise ValueError(f"Unsupported plan version: {plan.get('version')}")

    operations = plan.get("operations", [])

    if not operations:
        return {
            "operations": 0,
            "succeeded": 0,
            "failed": 0,
            "errors": [],
        }

    # Create client once for all operations
    client = DataverseClient.from_authctl(account)

    succeeded = 0
    failed = 0
    errors: list[dict[str, str]] = []

    for op in operations:
        try:
            client.patch(op["entity"], op["id"], op["patch"])
            succeeded += 1
        except Exception as e:
            failed += 1
            errors.append({
                "id": op["id"],
                "source_path": op.get("source_path", "unknown"),
                "reason": str(e),
            })

    return {
        "operations": len(operations),
        "succeeded": succeeded,
        "failed": failed,
        "errors": errors,
    }
