# Copyright 2025 Ben Mensi
# SPDX-License-Identifier: Apache-2.0

"""Minimal event client for Life-CLI script logging."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class EventClient:
    """Simple JSONL event logger."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_event(
        self,
        event_type: str,
        correlation_id: str,
        status: str,
        payload: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Log an event to the JSONL file."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "correlation_id": correlation_id,
            "status": status,
        }
        if payload:
            event["payload"] = payload
        if error_message:
            event["error_message"] = error_message

        with open(self.log_path, "a") as f:
            f.write(json.dumps(event) + "\n")
