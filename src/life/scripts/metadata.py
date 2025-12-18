"""Script metadata loading and validation.

Handles script name validation and metadata file parsing.

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Optional, Tuple

import yaml


class ScriptValidationError(Exception):
    """Raised when script validation fails."""

    pass


# Script name pattern: lowercase alphanumeric with hyphens only
NAME_PATTERN = re.compile(r"^[a-z0-9-]+$")


@dataclass
class ScriptMetadata:
    """Script metadata from <name>.meta.yaml file.

    Required fields:
    - name: Script identifier, must match filename
    - description: What this script does
    - owner: Github handle (@user) or email
    - created_at: When the script was created (YYYY-MM-DD)
    - ttl_days: How long until warnings start
    - promotion_target: Where this script goes when promoted

    Optional fields:
    - calls: Jobs/commands this script invokes
    """

    name: str
    description: str
    owner: str
    created_at: date
    ttl_days: int
    promotion_target: str
    calls: Optional[List[str]] = None

    def validate(self) -> None:
        """Validate metadata fields.

        Raises:
            ScriptValidationError: If validation fails.
        """
        # Name must match pattern
        validate_name(self.name)

        # Description is required and must be non-empty
        if not self.description or not self.description.strip():
            raise ScriptValidationError("description is required and cannot be empty")

        # Owner must be a github handle (@user) or email
        if not self.owner:
            raise ScriptValidationError("owner is required")
        if not (
            self.owner.startswith("@")
            or ("@" in self.owner and "." in self.owner.split("@")[-1])
        ):
            raise ScriptValidationError(
                f"owner must be a github handle (@user) or email, got: {self.owner}"
            )

        # TTL must be positive
        if self.ttl_days <= 0:
            raise ScriptValidationError(f"ttl_days must be positive, got: {self.ttl_days}")

        # Promotion target must be non-empty
        if not self.promotion_target or not self.promotion_target.strip():
            raise ScriptValidationError(
                "promotion_target is required (e.g., job/backfill-pipeline)"
            )


def validate_name(name: str) -> None:
    """Validate script name.

    Script names must be:
    - Lowercase alphanumeric with hyphens only: [a-z0-9-]+
    - No path separators (/, \\)
    - No dots (.)
    - No .. or path traversal attempts

    Args:
        name: Script name to validate.

    Raises:
        ScriptValidationError: If name is invalid.
    """
    if not name:
        raise ScriptValidationError("script name cannot be empty")

    # Check for path traversal attempts
    if ".." in name:
        raise ScriptValidationError(f"path traversal not allowed in script name: {name}")

    # Check for path separators
    if "/" in name or "\\" in name:
        raise ScriptValidationError(f"path separators not allowed in script name: {name}")

    # Check for dots (except we already checked ..)
    if "." in name:
        raise ScriptValidationError(f"dots not allowed in script name: {name}")

    # Check pattern match
    if not NAME_PATTERN.match(name):
        raise ScriptValidationError(
            f"script name must be lowercase alphanumeric with hyphens only "
            f"([a-z0-9-]+), got: {name}"
        )


def load_metadata(
    name: str, search_paths: List[Path]
) -> Tuple[Path, ScriptMetadata]:
    """Load script metadata from search paths.

    Searches for <name>.meta.yaml in the provided paths.

    Args:
        name: Script name (without .sh extension).
        search_paths: List of directories to search.

    Returns:
        Tuple of (script_path, metadata).

    Raises:
        ScriptValidationError: If name is invalid or metadata not found/invalid.
    """
    # Validate name before any filesystem access
    validate_name(name)

    meta_filename = f"{name}.meta.yaml"
    script_filename = f"{name}.sh"

    for search_path in search_paths:
        search_path = Path(search_path).expanduser()
        if not search_path.exists():
            continue

        meta_path = search_path / meta_filename
        script_path = search_path / script_filename

        if meta_path.exists():
            # Found metadata - script must also exist
            if not script_path.exists():
                raise ScriptValidationError(
                    f"metadata found at {meta_path} but script {script_path} not found"
                )

            # Parse metadata
            try:
                with open(meta_path) as f:
                    data = yaml.safe_load(f)
            except yaml.YAMLError as e:
                raise ScriptValidationError(f"invalid YAML in {meta_path}: {e}")

            if not isinstance(data, dict):
                raise ScriptValidationError(
                    f"metadata file {meta_path} must contain a YAML mapping"
                )

            # Extract and validate required fields
            try:
                # Parse created_at as date
                created_at_raw = data.get("created_at")
                if created_at_raw is None:
                    raise ScriptValidationError("created_at is required")

                if isinstance(created_at_raw, date):
                    created_at = created_at_raw
                elif isinstance(created_at_raw, str):
                    created_at = date.fromisoformat(created_at_raw)
                else:
                    raise ScriptValidationError(
                        f"created_at must be a date (YYYY-MM-DD), got: {created_at_raw}"
                    )

                metadata = ScriptMetadata(
                    name=data.get("name", ""),
                    description=data.get("description", ""),
                    owner=data.get("owner", ""),
                    created_at=created_at,
                    ttl_days=data.get("ttl_days", 0),
                    promotion_target=data.get("promotion_target", ""),
                    calls=data.get("calls"),
                )
            except (TypeError, ValueError) as e:
                raise ScriptValidationError(f"invalid metadata in {meta_path}: {e}")

            # Validate the metadata
            metadata.validate()

            # Name in metadata must match filename
            if metadata.name != name:
                raise ScriptValidationError(
                    f"metadata name '{metadata.name}' does not match filename '{name}'"
                )

            return script_path, metadata

    # No metadata found
    searched = ", ".join(str(p) for p in search_paths)
    raise ScriptValidationError(
        f"no metadata file found for script '{name}'. "
        f"Searched: {searched}. "
        f"Scripts require a {meta_filename} file."
    )
