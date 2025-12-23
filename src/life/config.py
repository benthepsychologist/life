"""
Configuration loader for Life-CLI.

Loads and validates YAML configuration files.

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to config file. If None, uses ~/.life/config.yml

    Returns:
        Dictionary containing configuration

    Raises:
        FileNotFoundError: If config file not found
        yaml.YAMLError: If config file is invalid YAML
    """
    # Determine config file path
    if config_path:
        path = Path(config_path).expanduser()
    else:
        # Use user config only
        path = Path.home() / ".life" / "config.yml"

        if not path.exists():
            raise FileNotFoundError(
                f"No config file found at {path}\n"
                "Create ~/.life/config.yml or use --config to specify a custom location."
            )

    # Load YAML
    try:
        with open(path, "r") as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Error parsing config file {path}: {e}")

    if config is None:
        config = {}

    # Expand workspace path if present
    if "workspace" in config:
        config["workspace"] = str(Path(config["workspace"]).expanduser())

    # Validate configuration
    from life.validation import validate_config
    issues = validate_config(config)
    if issues:
        logger.warning("Configuration validation warnings:")
        for issue in issues:
            logger.warning(f"  - {issue}")

    return config


def get_workspace(config: Dict[str, Any]) -> Path:
    """
    Get workspace path from config, with fallback to current directory.

    Args:
        config: Configuration dictionary

    Returns:
        Path object for workspace directory
    """
    workspace = config.get("workspace", ".")
    return Path(workspace).expanduser().resolve()
