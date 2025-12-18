"""Local JSONL event logging.

Implementation rules enforced here (Rule 7):
- Fixed event types only: job.started, step.completed, job.completed, job.failed
- Append-only JSONL, no rotation, no truncation
- No taxonomy explosion

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Fixed set of allowed event types (Rule 7)
ALLOWED_EVENT_TYPES = frozenset({
    "job.started",
    "step.completed",
    "job.completed",
    "job.failed",
    # Script events (quarantined script runner)
    "script.started",
    "script.completed",
    "script.failed",
    "script.override.forced",
})


class EventClient:
    """Append-only JSONL event log."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_event(
        self,
        event_type: str,
        correlation_id: str,
        status: str,
        payload: Optional[dict] = None,
        error_message: Optional[str] = None,
    ) -> None:
        if event_type not in ALLOWED_EVENT_TYPES:
            raise ValueError(
                f"Unknown event_type '{event_type}'. Allowed: {sorted(ALLOWED_EVENT_TYPES)}"
            )

        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "correlation_id": correlation_id,
            "status": status,
            "payload": payload or {},
        }
        if error_message:
            event["error_message"] = error_message

        with self.log_path.open("a") as f:
            f.write(json.dumps(event) + "\n")
