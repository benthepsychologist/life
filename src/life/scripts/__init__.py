"""Quarantined script runner for temporary workflow scripts.

Scripts are temporary glue code with TTL enforcement and event emission.
They are not first-class capabilities - promotion means writing a real spec.

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

from life.scripts.metadata import (
    ScriptMetadata,
    ScriptValidationError,
    load_metadata,
    validate_name,
)
from life.scripts.runner import (
    ScriptBlockedError,
    ScriptExecutionError,
    get_script_info,
    get_search_paths,
    list_scripts,
    run_script,
)
from life.scripts.state import (
    ScriptState,
    ScriptTier,
    calculate_tier,
    load_state,
    save_state,
)

__all__ = [
    "ScriptMetadata",
    "load_metadata",
    "validate_name",
    "ScriptValidationError",
    "ScriptState",
    "ScriptTier",
    "load_state",
    "save_state",
    "calculate_tier",
    "run_script",
    "get_script_info",
    "list_scripts",
    "get_search_paths",
    "ScriptBlockedError",
    "ScriptExecutionError",
]
