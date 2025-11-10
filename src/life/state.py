"""
State management for Life-CLI.

Tracks incremental sync state (high-water marks, last sync times) across runs.

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


class StateManager:
    """
    Manages persistent state for incremental syncs.

    State is stored in a JSON file with structure:
    {
        "task_name": {
            "field_name": "2025-11-10T10:30:00Z",
            "last_run": "2025-11-10T10:35:00Z"
        }
    }
    """

    def __init__(self, state_file: Path):
        """
        Initialize state manager.

        Args:
            state_file: Path to JSON state file
        """
        self.state_file = Path(state_file).expanduser()
        self.logger = logging.getLogger(__name__)
        self.state = self._load()

    def _load(self) -> Dict[str, Any]:
        """Load state from JSON file."""
        if not self.state_file.exists():
            self.logger.debug(f"State file not found, creating: {self.state_file}")
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            return {}

        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)
            self.logger.debug(f"Loaded state from: {self.state_file}")
            return state
        except json.JSONDecodeError as e:
            self.logger.warning(f"Invalid state file {self.state_file}: {e}")
            return {}

    def _save(self):
        """Save state to JSON file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2)
        self.logger.debug(f"Saved state to: {self.state_file}")

    def get_high_water_mark(self, task_name: str, field: str) -> Optional[str]:
        """
        Get the high-water mark for a task's incremental field.

        Args:
            task_name: Name of the sync task
            field: Field name (e.g., "modified_on", "created_at")

        Returns:
            High-water mark value (e.g., "2025-11-10T10:30:00Z") or None if never synced
        """
        task_state = self.state.get(task_name, {})
        return task_state.get(field)

    def set_high_water_mark(self, task_name: str, field: str, value: str):
        """
        Set the high-water mark for a task's incremental field.

        Args:
            task_name: Name of the sync task
            field: Field name (e.g., "modified_on")
            value: New high-water mark value
        """
        if task_name not in self.state:
            self.state[task_name] = {}

        self.state[task_name][field] = value
        self.state[task_name]["last_run"] = datetime.utcnow().isoformat() + "Z"
        self._save()
        self.logger.debug(f"Updated {task_name}.{field} = {value}")

    def get_last_run(self, task_name: str) -> Optional[str]:
        """
        Get the timestamp of the last run for a task.

        Args:
            task_name: Name of the sync task

        Returns:
            ISO 8601 timestamp or None if never run
        """
        task_state = self.state.get(task_name, {})
        return task_state.get("last_run")

    def clear_task(self, task_name: str):
        """
        Clear all state for a task (useful for full refresh).

        Args:
            task_name: Name of the sync task
        """
        if task_name in self.state:
            del self.state[task_name]
            self._save()
            self.logger.info(f"Cleared state for task: {task_name}")

    def get_all_state(self) -> Dict[str, Any]:
        """Get complete state dict (for debugging)."""
        return self.state.copy()
