# Copyright 2025 Ben Mensi
# SPDX-License-Identifier: Apache-2.0

"""
Configuration validation for Life-CLI.

Validates YAML configuration structure and provides helpful error messages.
"""

import logging
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)

# Valid top-level keys in config
VALID_TOP_LEVEL_KEYS = {"workspace", "sync", "merge", "process", "status", "today"}

# Required fields per task type
TASK_REQUIRED_FIELDS = {
    "sync": {"command"},  # Either command or commands, validated separately
    "merge": {"command"},
    "process": {"command"},
    "status": {"command"},
}

# Optional but recognized fields
TASK_OPTIONAL_FIELDS = {
    "description",
    "output",
    "commands",
    "incremental_field",
    "incremental_format",
    "state_file",
    "id_field",
    "date_range",
    "variables",
    "append_template",
    "mode",
}


def validate_config(config: Dict[str, Any]) -> List[str]:
    """
    Validate configuration structure and return list of warnings/errors.

    Args:
        config: Configuration dictionary loaded from YAML

    Returns:
        List of warning/error messages (empty if valid)
    """
    issues = []

    # Check for unknown top-level keys
    unknown_keys = set(config.keys()) - VALID_TOP_LEVEL_KEYS
    if unknown_keys:
        issues.append(
            f"Unknown top-level config keys: {', '.join(sorted(unknown_keys))}. "
            f"Valid keys are: {', '.join(sorted(VALID_TOP_LEVEL_KEYS))}"
        )

    # Validate each task category
    for category in ["sync", "merge", "process", "status"]:
        if category not in config:
            continue

        category_config = config[category]
        if not isinstance(category_config, dict):
            type_name = type(category_config).__name__
            issues.append(f"'{category}' must be a dictionary, got {type_name}")
            continue

        # Validate tasks in category
        for task_name, task_config in category_config.items():
            if not isinstance(task_config, dict):
                issues.append(
                    f"{category}.{task_name}: Task config must be a dictionary, "
                    f"got {type(task_config).__name__}"
                )
                continue

            # For merge, tasks might be nested (category > task)
            if category == "merge" and all(isinstance(v, dict) for v in task_config.values()):
                # This is a nested merge category, validate each subtask
                for subtask_name, subtask_config in task_config.items():
                    full_name = f"{category}.{task_name}.{subtask_name}"
                    task_issues = _validate_task(full_name, subtask_config, category)
                    issues.extend(task_issues)
            else:
                # Regular task
                task_issues = _validate_task(f"{category}.{task_name}", task_config, category)
                issues.extend(task_issues)

    return issues


def _validate_task(task_path: str, task_config: Dict[str, Any], category: str) -> List[str]:
    """
    Validate a single task configuration.

    Args:
        task_path: Dotted path to task (e.g. "sync.contacts")
        task_config: Task configuration dictionary
        category: Task category (sync, merge, process, status)

    Returns:
        List of validation issues for this task
    """
    issues = []

    # Check for command or commands field
    has_command = "command" in task_config
    has_commands = "commands" in task_config

    if not has_command and not has_commands:
        issues.append(f"{task_path}: Missing required field 'command' or 'commands'")
    elif has_command and has_commands:
        issues.append(f"{task_path}: Cannot have both 'command' and 'commands' fields")

    # Validate commands is a list if present
    if has_commands and not isinstance(task_config["commands"], list):
        issues.append(
            f"{task_path}: 'commands' must be a list, got {type(task_config['commands']).__name__}"
        )

    # Check for incremental sync configuration consistency
    incremental_field = task_config.get("incremental_field")
    state_file = task_config.get("state_file")

    if incremental_field and not state_file:
        issues.append(
            f"{task_path}: 'incremental_field' requires 'state_file' to be set"
        )
    if state_file and not incremental_field:
        issues.append(
            f"{task_path}: 'state_file' requires 'incremental_field' to be set"
        )

    # Check for unknown fields (potential typos)
    known_fields = TASK_REQUIRED_FIELDS.get(category, set()) | TASK_OPTIONAL_FIELDS
    unknown_fields = set(task_config.keys()) - known_fields
    if unknown_fields:
        logger.debug(
            f"{task_path}: Unrecognized fields: {', '.join(sorted(unknown_fields))}. "
            "These will be ignored unless added to 'variables' dictionary."
        )

    return issues


def suggest_fix(typo: str, valid_options: Set[str]) -> str:
    """
    Suggest a correction for a typo based on Levenshtein distance.

    Args:
        typo: The incorrect string
        valid_options: Set of valid options

    Returns:
        Suggested correction or empty string if no close match
    """
    # Simple distance calculation (Levenshtein would be better)
    def distance(s1: str, s2: str) -> int:
        if len(s1) > len(s2):
            s1, s2 = s2, s1
        distances = range(len(s1) + 1)
        for i2, c2 in enumerate(s2):
            distances_ = [i2 + 1]
            for i1, c1 in enumerate(s1):
                if c1 == c2:
                    distances_.append(distances[i1])
                else:
                    distances_.append(1 + min((distances[i1], distances[i1 + 1], distances_[-1])))
            distances = distances_
        return distances[-1]

    best_match = None
    best_distance = float("inf")

    for option in valid_options:
        dist = distance(typo.lower(), option.lower())
        if dist < best_distance and dist <= 2:  # Max distance of 2 for suggestions
            best_distance = dist
            best_match = option

    return best_match or ""
