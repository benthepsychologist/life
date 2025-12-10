"""
life_jobs - Step functions for the life-cli job runner.

This package contains modules that can be called from job definitions:
- dataverse: Dataverse operations via morch
- graph: Graph API operations via morch
- shell: Legacy subprocess wrapper (transitional)
- generate: LLM prompt processing via the llm library (optional dependency)

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

__version__ = "0.1.0"
