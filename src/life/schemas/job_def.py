# Copyright 2025 Ben Mensi
# SPDX-License-Identifier: Apache-2.0

"""Job definition and instance schemas for Life CLI.

Follows lorchestra pattern:
- JobDef (YAML) → compile → JobInstance (JSON) → execute → RunRecord
- @ctx.*, @payload.*, @self.* resolved at compile time
- @run.* resolved at execute time
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class StepInstance:
    """A compiled step ready for execution.

    All @ctx.*, @payload.*, @self.* refs are resolved.
    Only @run.* refs may remain for runtime resolution.
    """
    step_id: str
    op: str  # e.g., "lorchestra.run"
    params: Dict[str, Any] = field(default_factory=dict)
    timeout_s: int = 300
    continue_on_error: bool = False


@dataclass
class JobInstance:
    """A compiled job ready for execution.

    Produced by compiler from JobDef YAML + ctx + payload.
    All compile-time refs resolved, @run.* preserved for runtime.
    """
    job_id: str
    job_version: str
    compiled_at: datetime
    steps: Tuple[StepInstance, ...]


@dataclass
class StepOutcome:
    """Result of executing a single step."""
    step_id: str
    status: str  # "completed", "failed", "skipped"
    output: Any = None
    error: Optional[str] = None


@dataclass
class RunRecord:
    """Result of executing a job."""
    run_id: str
    job_id: str
    success: bool
    started_at: datetime
    completed_at: Optional[datetime] = None
    outcomes: List[StepOutcome] = field(default_factory=list)
