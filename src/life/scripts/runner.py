"""Script runner with TTL enforcement and event emission.

Executes quarantined bash scripts with governance controls.

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

import hashlib
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from life.event_client import EventClient
from life.scripts.metadata import ScriptValidationError, load_metadata
from life.scripts.state import (
    ScriptTier,
    calculate_tier,
    get_age_days,
    load_state,
    save_state,
)


class ScriptExecutionError(Exception):
    """Raised when script execution fails."""

    pass


class ScriptBlockedError(Exception):
    """Raised when script is blocked by TTL."""

    pass


def get_search_paths() -> List[Path]:
    """Get script search paths in priority order.

    Order:
    1. $LIFE_SCRIPTS_DIR (if set)
    2. ~/.life/scripts/ (user-local, default)
    3. ./scripts/ (repo-local, rare)

    Returns:
        List of paths to search for scripts.
    """
    paths = []

    # 1. Environment variable override
    env_dir = os.environ.get("LIFE_SCRIPTS_DIR")
    if env_dir:
        paths.append(Path(env_dir))

    # 2. User-local default
    paths.append(Path("~/.life/scripts").expanduser())

    # 3. Repo-local (rare)
    paths.append(Path("./scripts"))

    return paths


def _get_dir_scope(script_path: Path) -> str:
    """Determine the scope of a script based on its location.

    Returns:
        One of: "env", "user", "repo"
    """
    env_dir = os.environ.get("LIFE_SCRIPTS_DIR")
    if env_dir and script_path.is_relative_to(Path(env_dir)):
        return "env"
    user_dir = Path("~/.life/scripts").expanduser()
    if script_path.is_relative_to(user_dir):
        return "user"
    return "repo"


def _hash_args(args: List[str]) -> str:
    """Create a SHA256 hash of the arguments."""
    return hashlib.sha256(" ".join(args).encode()).hexdigest()


def _redact_args(args: List[str]) -> List[str]:
    """Extract flag names only, redacting values.

    Example: ["--source", "secret", "--dry-run"] -> ["--source", "--dry-run"]
    """
    redacted = []
    for arg in args:
        if arg.startswith("-"):
            # Split on = for --key=value format
            redacted.append(arg.split("=")[0])
    return redacted


def _get_event_client() -> EventClient:
    """Get the event client for logging."""
    log_path = Path("~/.life/events.jsonl").expanduser()
    return EventClient(log_path)


def _check_tty() -> bool:
    """Check if stdin is a TTY."""
    return sys.stdin.isatty()


def _prompt_confirmation(message: str) -> bool:
    """Prompt user for yes/no confirmation.

    Args:
        message: Message to display.

    Returns:
        True if user confirms, False otherwise.
    """
    try:
        response = input(f"{message} [y/N]: ")
        return response.lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def run_script(
    name: str,
    args: Optional[List[str]] = None,
    force: bool = False,
    yes: bool = False,
) -> int:
    """Run a quarantined script with TTL enforcement.

    Args:
        name: Script name (without .sh extension).
        args: Arguments to pass to the script.
        force: Bypass all TTL checks (Level 3 block override).
        yes: Acknowledge overdue risk (Level 2 confirmation bypass).

    Returns:
        Exit code from the script.

    Raises:
        ScriptValidationError: If script or metadata is invalid.
        ScriptBlockedError: If script is blocked and --force not provided.
        ScriptExecutionError: If script execution fails.
    """
    args = args or []
    correlation_id = str(uuid.uuid4())
    event_client = _get_event_client()
    is_tty = _check_tty()

    # Load script and metadata
    search_paths = get_search_paths()
    script_path, metadata = load_metadata(name, search_paths)

    # Load state
    state = load_state(name)

    # Calculate age and tier
    tier = calculate_tier(metadata, state)
    age_days = get_age_days(metadata, state)

    # Emit started event
    event_client.log_event(
        event_type="script.started",
        correlation_id=correlation_id,
        status="running",
        payload={
            "script": name,
            "script_path": str(script_path),
            "script_dir_scope": _get_dir_scope(script_path),
            "args_hash": _hash_args(args),
            "args_redacted": _redact_args(args),
            "owner": metadata.owner,
            "age_days": age_days,
            "tier": tier.value,
            "promotion_target": metadata.promotion_target,
        },
    )

    # TTL enforcement
    override_reason = None
    blocked_days = 3 * metadata.ttl_days
    overdue_days = 2 * metadata.ttl_days
    stale_days = metadata.ttl_days
    try:
        if tier == ScriptTier.BLOCKED:
            if force:
                override_reason = "force"
                print(
                    f"WARNING: Script '{name}' is {age_days} days old "
                    f"(blocked at {blocked_days} days). Proceeding with --force."
                )
            elif yes:
                # --yes is NOT sufficient for Level 3
                raise ScriptBlockedError(
                    f"Script '{name}' is {age_days} days old "
                    f"(blocked at {blocked_days} days). "
                    f"--yes is not sufficient for blocked scripts. Use --force to override."
                )
            else:
                raise ScriptBlockedError(
                    f"Script '{name}' is {age_days} days old "
                    f"(blocked at {blocked_days} days). "
                    f"Use --force to override. "
                    f"Consider promoting to: {metadata.promotion_target}"
                )

        elif tier == ScriptTier.OVERDUE:
            if force or yes:
                override_reason = "force" if force else "yes"
                flag = "--force" if force else "--yes"
                print(
                    f"WARNING: Script '{name}' is {age_days} days old "
                    f"(overdue at {overdue_days} days). Proceeding with {flag}."
                )
            elif not is_tty:
                raise ScriptBlockedError(
                    f"Script '{name}' is {age_days} days old "
                    f"(overdue at {overdue_days} days). "
                    f"Non-interactive mode requires --yes or --force."
                )
            else:
                print(
                    f"WARNING: Script '{name}' is {age_days} days old "
                    f"(overdue at {overdue_days} days)."
                )
                print(f"Consider promoting to: {metadata.promotion_target}")
                if not _prompt_confirmation("Continue anyway?"):
                    raise ScriptBlockedError("User declined to run overdue script.")

        elif tier == ScriptTier.STALE:
            print(
                f"Note: Script '{name}' is {age_days} days old "
                f"(stale at {stale_days} days). "
                f"Consider promoting to: {metadata.promotion_target}"
            )

        # Log override if applicable
        if override_reason:
            state.force_count += 1
            event_client.log_event(
                event_type="script.override.forced",
                correlation_id=correlation_id,
                status="overridden",
                payload={
                    "script": name,
                    "age_days": age_days,
                    "forced_by": os.environ.get("USER", "unknown"),
                    "reason": override_reason,
                },
            )

        # Execute script
        start_time = datetime.now(timezone.utc)

        # Build controlled environment
        env = os.environ.copy()
        env["LIFE_CORRELATION_ID"] = correlation_id

        # Run script with strict mode enforced
        # Use bash -c with explicit set -euo pipefail then source the script
        result = subprocess.run(
            ["bash", "-c", f"set -euo pipefail; source {script_path}", "--", *args],
            env=env,
            cwd=script_path.parent,
            capture_output=True,
            text=True,
        )

        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

        # Pass through output
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)

        # Update state
        now = datetime.now(timezone.utc).isoformat()
        if not state.first_seen:
            state.first_seen = now
        state.last_run = now
        state.run_count += 1
        save_state(name, state)

        if result.returncode == 0:
            event_client.log_event(
                event_type="script.completed",
                correlation_id=correlation_id,
                status="succeeded",
                payload={
                    "script": name,
                    "duration_ms": duration_ms,
                    "exit_code": 0,
                },
            )
        else:
            # Get last 10 lines of stderr
            stderr_lines = result.stderr.strip().split("\n") if result.stderr else []
            stderr_tail = "\n".join(stderr_lines[-10:])

            event_client.log_event(
                event_type="script.failed",
                correlation_id=correlation_id,
                status="failed",
                payload={
                    "script": name,
                    "exit_code": result.returncode,
                    "stderr_tail": stderr_tail,
                },
                error_message=f"Script exited with code {result.returncode}",
            )

        return result.returncode

    except ScriptBlockedError:
        # Log the block and re-raise
        event_client.log_event(
            event_type="script.failed",
            correlation_id=correlation_id,
            status="blocked",
            payload={
                "script": name,
                "age_days": age_days,
                "tier": tier.value,
            },
            error_message=f"Script blocked due to TTL tier: {tier.value}",
        )
        raise


def get_script_info(name: str) -> dict:
    """Get information about a script.

    Args:
        name: Script name.

    Returns:
        Dictionary with script metadata, state, and tier information.
    """
    search_paths = get_search_paths()
    script_path, metadata = load_metadata(name, search_paths)
    state = load_state(name)
    tier = calculate_tier(metadata, state)
    age_days = get_age_days(metadata, state)

    return {
        "name": name,
        "script_path": str(script_path),
        "description": metadata.description,
        "owner": metadata.owner,
        "created_at": str(metadata.created_at),
        "ttl_days": metadata.ttl_days,
        "promotion_target": metadata.promotion_target,
        "calls": metadata.calls,
        "age_days": age_days,
        "tier": tier.value,
        "run_count": state.run_count,
        "force_count": state.force_count,
        "first_seen": state.first_seen,
        "last_run": state.last_run,
    }


def list_scripts() -> List[dict]:
    """List all available scripts in search paths.

    Returns:
        List of script info dictionaries.
    """
    scripts = []
    search_paths = get_search_paths()

    for search_path in search_paths:
        search_path = Path(search_path).expanduser()
        if not search_path.exists():
            continue

        for meta_file in search_path.glob("*.meta.yaml"):
            name = meta_file.stem.replace(".meta", "")
            try:
                info = get_script_info(name)
                scripts.append(info)
            except ScriptValidationError:
                # Skip invalid scripts
                continue

    return scripts
