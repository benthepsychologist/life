---
version: "0.1"
tier: C
title: "life Job Runner: morch Integration"
owner: benthepsychologist
goal: Transform life into a job runner for arbitrary Python functions, using morch for Microsoft API operations
labels: [cli, job-runner, morch, dataverse, graph, python]
project_slug: life-job-runner
spec_version: 1.0.0
created: 2025-12-09T10:00:00+00:00
updated: 2025-12-09T11:00:00+00:00
orchestrator_contract: "standard"
repo:
  path: /workspace/life
  working_branch: "main"
---

# life Job Runner: morch Integration

## Objective

> Evolve life into a lightweight job runner for arbitrary Python functions, using `morch` for Microsoft Graph and Dataverse operations. Jobs are YAML-defined sequences of `call: module.function` steps, not type-specific processors.

## Acceptance Criteria

- [ ] `life run <job_id>` command executes jobs from YAML definitions
- [ ] `life jobs list` shows available jobs with descriptions
- [ ] `life jobs show <job_id>` displays job definition
- [ ] Jobs are sequences of steps, each step calls a Python function via `call:`
- [ ] `life_jobs.dataverse` module with morch-based helper functions
- [ ] `life_jobs.graph` module with morch-based helper functions
- [ ] `shell` step type for legacy subprocess commands (transitional only)
- [ ] Event logging to local JSONL file with correlation IDs
- [ ] `--dry-run` mode shows what would execute
- [ ] Backwards compatible with existing `life sync/merge/process` commands
- [ ] Tests for job runner and life_jobs modules

## Context

### Background

life currently orchestrates external CLI tools via subprocess:

```yaml
sync:
  contacts:
    command: "dv query contacts --select firstname,lastname {extra_args}"
    output: ~/data/contacts.json
```

This works but has limitations:
1. **Subprocess overhead** - Each call spawns a new process
2. **No shared auth** - Each tool manages its own tokens
3. **Limited error handling** - Only exit codes, no structured errors
4. **No tracing** - Can't correlate operations across tools

Meanwhile, `morch` now provides clean Python clients for Dataverse and Graph APIs.

### Key Design Principle: Function Calls, Not Processors

Instead of a lorchestra-style `job_type` + `ProcessorRegistry` pattern (which is engine-heavy), life uses a simpler model:

**Jobs = ordered steps, each step = Python function call**

```yaml
jobs:
  sync_contacts:
    description: "Sync contacts from Dataverse"
    steps:
      - name: fetch
        call: life_jobs.dataverse.query
        args:
          account: lifeos
          entity: contacts
          output: ~/data/contacts.json
```

The job runner simply:
1. Loads the YAML job definition
2. For each step, resolves `call` to a Python function via `importlib`
3. Invokes the function with `args`

This gives us:
- **Arbitrary composition** - Multiple steps per job, any Python function
- **No registry/protocol overhead** - Just `importlib` + function calls
- **Easy to extend** - Add new capabilities by writing functions, not processors
- **YAML-friendly** - Easy to hand-edit, supports comments

### Constraints

- Must remain backwards compatible with existing YAML-based workflows
- New job runner is additive (`life run`) alongside existing commands
- Keep dependencies minimal (add `morch`, keep everything else)
- YAML for job definitions (not JSON - this is a personal tool)
- No scheduling - still on-demand execution
- Local event logging (JSONL file)
- `shell` steps are transitional only - new jobs should use Python functions

### Implementation Rules

These rules constrain implementation to avoid over-engineering and surface errors early:

1. **YAML errors must surface immediately**
   - Do NOT silently ignore YAML parse errors in `load_jobs`
   - Raise a clear exception, or collect errors and expose via `life jobs list --errors`
   - If any `jobs/*.yaml` fails to parse, surface that clearly

2. **No printing from `job_runner` core**
   - `job_runner.run_job` must be pure in terms of I/O: no `print`, no `stdin`
   - All printing/UX goes in the Typer command (`life.commands.run`)
   - `run_job` only returns structured data and writes to the event log

3. **Restrict `call:` resolution to allowlist**
   - `resolve_callable` must only import from `life_jobs.*` (or explicit allowlist)
   - If `call` doesn't start with `life_jobs.`, reject it immediately
   - This prevents arbitrary code execution footguns

4. **Detect unsubstituted variables**
   - After `_substitute_variables`, check for remaining `{var}` patterns
   - If a placeholder remains and `var` isn't in `variables`, raise or warn
   - Do NOT silently leave unsubstituted placeholders in args

5. **Paths come from config/CLI, not hardcoded**
   - `run_job` accepts `jobs_dir` and `event_log` as parameters (already does)
   - CLI is responsible for reading config and passing paths to runner
   - Defaults are fallbacks only when config is missing

6. **Stable return shape from `run_job`**
   - Always return `{"run_id": str, "status": str, "steps": list}`
   - Each step in `steps` has consistent shape regardless of dry_run
   - Don't mix top-level keys; everything else goes inside step results

7. **Tiny, fixed event type set**
   - Only these event types: `job.started`, `step.completed`, `job.completed`, `job.failed`
   - No taxonomy explosion; don't invent new event types during implementation
   - Append-only JSONL, no rotation, no truncation

8. **`life_jobs.*` modules are pure-ish**
   - Never print
   - Never read global config or environment directly (except `Path.expanduser`)
   - Always return simple dicts (no custom classes)
   - Side effects limited to: file IO, morch API calls, state updates

9. **Shell module stays minimal and ugly**
   - `life_jobs.shell` exists only for migration/legacy paths
   - Don't build helpers or abstractions around it
   - No new jobs should use shell unless the tool is genuinely external
   - Keep it uncomfortable to discourage new shell-based jobs

## Design

### Package Structure

```
src/life/
├── cli.py                      # Existing CLI (add run, jobs commands)
├── config.py                   # Existing config loader
├── state.py                    # Existing state manager
├── runner.py                   # Existing subprocess runner
├── job_runner.py               # NEW: Step-based job execution
├── event_client.py             # NEW: JSONL event logging
└── commands/
    ├── sync.py                 # Existing (unchanged)
    ├── run.py                  # NEW: job runner command
    └── jobs.py                 # NEW: job listing/inspection

src/life_jobs/                  # NEW: Job step functions
├── __init__.py
├── dataverse.py                # Dataverse operations via morch
├── graph.py                    # Graph API operations via morch
└── shell.py                    # Legacy subprocess wrapper

~/.life/
├── jobs/                       # Job definitions (YAML)
│   ├── dataverse.yaml          # Dataverse-related jobs
│   ├── graph.yaml              # Graph-related jobs
│   └── workflows.yaml          # Multi-step workflows
└── events.jsonl                # Event log
```

### CLI Commands

```bash
# New job runner commands
life run <job_id>                    # Run a job by ID
life run <job_id> --dry-run          # Preview without execution
life run <job_id> --verbose          # Show detailed output
life jobs list                       # List all available jobs
life jobs show <job_id>              # Show job definition

# Existing commands (unchanged)
life sync <task>                     # Legacy subprocess-based sync
life merge <category> <task>         # Legacy merge
life process <task>                  # Legacy process
life status <task>                   # Legacy status
life today                           # Daily notes
```

### Job Definition Format (YAML)

Jobs are defined in YAML files under `~/.life/jobs/`. Each file can contain multiple jobs.

#### Single-Step Job

```yaml
# ~/.life/jobs/dataverse.yaml
jobs:
  query_contacts:
    description: "Query active contacts from Dataverse"
    steps:
      - name: query
        call: life_jobs.dataverse.query
        args:
          account: lifeos
          entity: contacts
          select: [firstname, lastname, emailaddress1, modifiedon]
          filter: "statecode eq 0"
          orderby: "modifiedon desc"
          top: 100
          output: ~/data/contacts.json
```

#### Multi-Step Job

```yaml
# ~/.life/jobs/workflows.yaml
jobs:
  session_summary:
    description: "Generate and send session summary"
    steps:
      - name: fetch-session
        call: life_jobs.dataverse.query
        args:
          account: lifeos
          entity: ben_sessions
          filter: "ben_clientemail eq '{client_email}'"
          output: ~/tmp/session.json

      - name: generate-pdf
        call: life_jobs.documents.generate_pdf
        args:
          template: session_summary
          input: ~/tmp/session.json
          output: ~/tmp/summary.pdf

      - name: send-email
        call: life_jobs.graph.send_mail
        args:
          account: drben
          to: "{client_email}"
          subject: "Session Summary - {date}"
          body_file: ~/tmp/summary.html
          attachments: [~/tmp/summary.pdf]

      - name: upload-to-drive
        call: life_jobs.gdrive.upload
        args:
          file: ~/tmp/summary.pdf
          folder_id: "{client_folder_id}"
```

#### Incremental Sync Job

```yaml
jobs:
  sync_contacts:
    description: "Incrementally sync contacts"
    steps:
      - name: sync
        call: life_jobs.dataverse.sync
        args:
          account: lifeos
          entity: contacts
          select: [contactid, firstname, lastname, emailaddress1, modifiedon]
          filter: "statecode eq 0"
          output: ~/data/contacts.json
          incremental_field: modifiedon
          state_key: sync_contacts
```

#### Graph API Job

```yaml
# ~/.life/jobs/graph.yaml
jobs:
  fetch_recent_mail:
    description: "Fetch recent emails"
    steps:
      - name: fetch
        call: life_jobs.graph.get_messages
        args:
          account: personal
          top: 50
          select: [id, subject, from, receivedDateTime]
          output: ~/data/emails.json

  send_test_email:
    description: "Send a test email"
    steps:
      - name: send
        call: life_jobs.graph.send_mail
        args:
          account: drben
          to: [test@example.com]
          subject: "Test from life"
          body: "This is a test email sent via life run."
```

#### Shell Job (Transitional)

```yaml
jobs:
  run_legacy_script:
    description: "Run a legacy shell command (transitional)"
    steps:
      - name: run
        call: life_jobs.shell.run
        args:
          command: "python ~/scripts/process_data.py --input {input} --output {output}"
          variables:
            input: ~/data/raw.json
            output: ~/data/processed.json
          timeout: 300
```

### Core Components

#### Job Runner (job_runner.py)

```python
"""Step-based job runner.

Implementation rules enforced here:
- No print statements (CLI handles --verbose output)
- YAML errors surface immediately (no silent continue)
- call: restricted to life_jobs.* allowlist
- Unsubstituted {var} placeholders raise errors
"""
import importlib
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from life.event_client import EventClient


# Allowlist for call: resolution (Rule 3)
ALLOWED_CALL_PREFIXES = ("life_jobs.",)


class JobLoadError(Exception):
    """Raised when job YAML files fail to load."""
    def __init__(self, errors: list[tuple[Path, str]]):
        self.errors = errors
        msg = "Failed to load job files:\n" + "\n".join(
            f"  - {path}: {err}" for path, err in errors
        )
        super().__init__(msg)


class CallNotAllowedError(ValueError):
    """Raised when call: path is not in allowlist."""
    pass


class UnsubstitutedVariableError(ValueError):
    """Raised when {var} placeholders remain after substitution."""
    pass


def resolve_callable(call_path: str):
    """Resolve 'module.submodule.function' to a callable.

    Only allows imports from ALLOWED_CALL_PREFIXES (Rule 3).
    """
    if not any(call_path.startswith(prefix) for prefix in ALLOWED_CALL_PREFIXES):
        raise CallNotAllowedError(
            f"call: '{call_path}' not allowed. Must start with one of: {ALLOWED_CALL_PREFIXES}"
        )
    module_path, func_name = call_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, func_name)


def load_jobs(jobs_dir: Path) -> dict[str, dict]:
    """Load all jobs from YAML files in jobs_dir.

    Raises JobLoadError if any YAML file fails to parse (Rule 1).
    """
    all_jobs = {}
    errors = []

    for yaml_file in sorted(jobs_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(yaml_file.read_text()) or {}
            jobs = data.get("jobs", {})
            all_jobs.update(jobs)
        except yaml.YAMLError as e:
            errors.append((yaml_file, str(e)))

    if errors:
        raise JobLoadError(errors)

    return all_jobs


def list_jobs(jobs_dir: Path) -> list[dict]:
    """List all available jobs."""
    jobs = load_jobs(jobs_dir)
    return [
        {"job_id": job_id, "description": spec.get("description", "")}
        for job_id, spec in sorted(jobs.items())
    ]


def run_job(
    job_id: str,
    *,
    dry_run: bool = False,
    jobs_dir: Path,
    event_log: Path,
    variables: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run a job by ID.

    Returns stable shape (Rule 6): {"run_id": str, "status": str, "steps": list}
    No print statements (Rule 2) - CLI handles verbose output.
    """
    # Generate run ID
    run_id = f"{job_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"

    # Load job
    jobs = load_jobs(jobs_dir)
    if job_id not in jobs:
        raise KeyError(f"Job not found: {job_id}. Available: {list(jobs.keys())}")

    job_spec = jobs[job_id]
    steps = job_spec.get("steps", [])

    # Event logging
    event_client = EventClient(event_log)
    event_client.log_event("job.started", run_id, "success", {"job_id": job_id, "dry_run": dry_run})

    results = []
    try:
        for step in steps:
            step_name = step.get("name", "unnamed")
            call_path = step["call"]
            args = step.get("args", {})

            # Substitute variables in args, then check for unsubstituted (Rule 4)
            if variables:
                args = _substitute_variables(args, variables)
            _check_unsubstituted(args, step_name)

            if dry_run:
                results.append({
                    "step": step_name,
                    "call": call_path,
                    "args": args,
                    "status": "skipped",
                    "dry_run": True,
                })
                continue

            # Resolve and call function (validates allowlist via Rule 3)
            func = resolve_callable(call_path)
            result = func(**args)

            results.append({
                "step": step_name,
                "call": call_path,
                "status": "success",
                "result": result,
            })

            event_client.log_event(
                "step.completed", run_id, "success",
                {"step": step_name, "call": call_path}
            )

        event_client.log_event("job.completed", run_id, "success", {"job_id": job_id})
        return {"run_id": run_id, "status": "success", "steps": results}

    except Exception as e:
        event_client.log_event("job.failed", run_id, "failed", {"job_id": job_id}, str(e))
        raise


# Regex to find {placeholder} patterns
_PLACEHOLDER_RE = re.compile(r"\{([^}]+)\}")


def _substitute_variables(obj: Any, variables: dict[str, str]) -> Any:
    """Recursively substitute {var} patterns in strings."""
    if isinstance(obj, str):
        for key, value in variables.items():
            obj = obj.replace(f"{{{key}}}", value)
        return obj
    elif isinstance(obj, dict):
        return {k: _substitute_variables(v, variables) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_substitute_variables(item, variables) for item in obj]
    return obj


def _check_unsubstituted(obj: Any, step_name: str) -> None:
    """Check for remaining {var} placeholders and raise if found (Rule 4).

    Known limitation: If literal {} are needed in arguments (e.g., OData filters),
    introduce an escape convention (e.g., {{literal}}) or per-step `allow_unsubstituted: true`.
    Not implemented yet - just document when needed.
    """
    unsubstituted = set()
    _collect_unsubstituted(obj, unsubstituted)
    if unsubstituted:
        raise UnsubstitutedVariableError(
            f"Step '{step_name}' has unsubstituted variables: {sorted(unsubstituted)}"
        )


def _collect_unsubstituted(obj: Any, found: set[str]) -> None:
    """Recursively collect unsubstituted {var} names."""
    if isinstance(obj, str):
        for match in _PLACEHOLDER_RE.finditer(obj):
            found.add(match.group(1))
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_unsubstituted(v, found)
    elif isinstance(obj, list):
        for item in obj:
            _collect_unsubstituted(item, found)
```

#### Event Client (event_client.py)

```python
"""Local JSONL event logging.

Implementation rules enforced here (Rule 7):
- Fixed event types only: job.started, step.completed, job.completed, job.failed
- Append-only JSONL, no rotation, no truncation
- No taxonomy explosion
"""
import json
from datetime import datetime, timezone
from pathlib import Path


# Fixed set of allowed event types (Rule 7)
ALLOWED_EVENT_TYPES = frozenset({
    "job.started",
    "step.completed",
    "job.completed",
    "job.failed",
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
        payload: dict | None = None,
        error_message: str | None = None,
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
```

#### Dataverse Functions (life_jobs/dataverse.py)

```python
"""Dataverse operations via morch.

Implementation rules enforced here (Rule 8):
- Never print
- Never read global config or environment (except Path.expanduser)
- Always return simple dicts
- Side effects: file IO, morch API calls, state updates only
"""
import json
from pathlib import Path
from typing import Any

from morch import DataverseClient

from life.state import StateManager

# Note: StateManager currently hardcodes ~/.life/state.json.
# If this ever needs to move, we'll pass the path from config.


def query(
    account: str,
    entity: str,
    output: str,
    select: list[str] | None = None,
    filter: str | None = None,
    orderby: str | None = None,
    top: int | None = None,
    expand: str | None = None,
) -> dict[str, Any]:
    """Query Dataverse and write results to output file."""
    client = DataverseClient.from_authctl(account)

    records = client.query(
        entity,
        select=select,
        filter=filter,
        orderby=orderby,
        top=top,
        expand=expand,
    )

    output_path = Path(output).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(records, indent=2, default=str))

    return {"records": len(records), "output": str(output_path)}


def sync(
    account: str,
    entity: str,
    output: str,
    select: list[str] | None = None,
    filter: str | None = None,
    incremental_field: str = "modifiedon",
    state_key: str | None = None,
) -> dict[str, Any]:
    """Incrementally sync from Dataverse with state tracking."""
    state_manager = StateManager(Path("~/.life/state.json").expanduser())
    key = state_key or f"sync_{entity}"
    last_value = state_manager.get_last_sync(key, incremental_field)

    # Build incremental filter
    if last_value:
        inc_filter = f"{incremental_field} gt {last_value}"
        full_filter = f"({filter}) and ({inc_filter})" if filter else inc_filter
    else:
        full_filter = filter

    client = DataverseClient.from_authctl(account)
    records = client.query(
        entity,
        select=select,
        filter=full_filter,
        orderby=f"{incremental_field} asc",
    )

    # Write output (append mode for sync)
    output_path = Path(output).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    existing = []
    if output_path.exists():
        existing = json.loads(output_path.read_text())

    existing.extend(records)
    output_path.write_text(json.dumps(existing, indent=2, default=str))

    # Update state
    if records:
        max_value = max(r.get(incremental_field, "") for r in records)
        state_manager.update_last_sync(key, incremental_field, max_value)

    return {"records": len(records), "total": len(existing), "output": str(output_path)}


def get_single(
    account: str,
    entity: str,
    record_id: str,
    select: list[str] | None = None,
) -> dict[str, Any]:
    """Fetch a single record by ID."""
    client = DataverseClient.from_authctl(account)
    return client.query_single(entity, record_id, select=select)
```

#### Graph Functions (life_jobs/graph.py)

```python
"""Graph API operations via morch.

Implementation rules enforced here (Rule 8):
- Never print
- Never read global config or environment (except Path.expanduser)
- Always return simple dicts
- Side effects: file IO, morch API calls only
"""
import json
from pathlib import Path
from typing import Any

from morch import GraphClient


def get_messages(
    account: str,
    output: str,
    top: int = 50,
    select: list[str] | None = None,
    filter: str | None = None,
) -> dict[str, Any]:
    """Fetch messages from Graph API."""
    client = GraphClient.from_authctl(account, scopes=["Mail.Read"])

    params = {"$top": str(top)}
    if select:
        params["$select"] = ",".join(select)
    if filter:
        params["$filter"] = filter

    messages = client.get_all("/me/messages", params=params)

    output_path = Path(output).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(messages, indent=2, default=str))

    return {"messages": len(messages), "output": str(output_path)}


def send_mail(
    account: str,
    to: list[str],
    subject: str,
    body: str | None = None,
    body_file: str | None = None,
    is_html: bool = False,
    attachments: list[str] | None = None,
) -> dict[str, Any]:
    """Send an email via Graph API."""
    client = GraphClient.from_authctl(account, scopes=["Mail.Send"])

    # Build body
    if body_file:
        body = Path(body_file).expanduser().read_text()

    message = {
        "subject": subject,
        "body": {
            "contentType": "HTML" if is_html else "Text",
            "content": body,
        },
        "toRecipients": [{"emailAddress": {"address": addr}} for addr in to],
    }

    # Attachments explicitly out of scope for now

    client.post("/me/sendMail", {"message": message})
    return {"sent": True, "to": to, "subject": subject}


def me(account: str) -> dict[str, Any]:
    """Get current user profile."""
    client = GraphClient.from_authctl(account, scopes=["User.Read"])
    return client.me()
```

#### Shell Functions (life_jobs/shell.py)

```python
"""Legacy shell command execution (transitional only).

WARNING: This module exists only for migration from subprocess-based workflows.
New jobs should use Python functions instead of shell commands.

Implementation rules enforced here (Rule 9):
- Minimal and ugly on purpose
- No helpers or abstractions
- Discourage new shell-based jobs
- Keep it uncomfortable
"""
import subprocess
from pathlib import Path
from typing import Any


def run(
    command: str,
    variables: dict[str, str] | None = None,
    timeout: int = 300,
    check: bool = True,
    cwd: str | None = None,
) -> dict[str, Any]:
    """Execute a shell command (transitional - prefer Python functions)."""
    # Substitute variables
    if variables:
        for key, value in variables.items():
            command = command.replace(f"{{{key}}}", str(Path(value).expanduser()))

    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=check,
        cwd=Path(cwd).expanduser() if cwd else None,
    )

    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
```

### Configuration

Add to `~/.life/config.yml`:

```yaml
# Existing config...
workspace: ~/data

# Job runner config
jobs:
  dir: ~/.life/jobs
  event_log: ~/.life/events.jsonl
```

## Plan

### Step 1: Core Job Runner

**Files to create:**
- `src/life/job_runner.py` - Step-based job execution with `importlib`
- `src/life/event_client.py` - JSONL event logging
- `tests/test_job_runner.py`

### Step 2: CLI Commands

**Files to create/modify:**
- `src/life/commands/run.py` - `life run` command
- `src/life/commands/jobs.py` - `life jobs list/show` commands
- `src/life/cli.py` - Register new commands
- `tests/test_commands_run.py`

**Important:** CLI must catch `JobLoadError` and display per-file errors cleanly to stderr (not Python tracebacks). Optional `life jobs list --errors` for full details.

### Step 3: life_jobs Module

**Files to create:**
- `src/life_jobs/__init__.py`
- `src/life_jobs/dataverse.py` - query, sync, get_single
- `src/life_jobs/graph.py` - get_messages, send_mail, me
- `src/life_jobs/shell.py` - run (transitional)
- `tests/test_life_jobs_dataverse.py`
- `tests/test_life_jobs_graph.py`

**Dependencies:**
- Add `morch` to pyproject.toml

### Step 4: Example Jobs & Documentation

**Files to create:**
- `~/.life/jobs/examples.yaml` (or in repo as examples)
- Update `README.md` with job runner docs
- Update `docs/ARCHITECTURE.md`

## Dependencies

```toml
# pyproject.toml additions
[project]
dependencies = [
    "typer>=0.9.0",
    "pyyaml>=6.0",
    "morch",  # NEW
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "ruff>=0.1.0",
    "responses>=0.24.0",
]
```

## Migration Path

1. **Phase 1**: Add job runner alongside existing commands (non-breaking)
2. **Phase 2**: Convert existing YAML tasks to job definitions with `call:` steps
3. **Phase 3**: Retire subprocess-based `dv`, `msg` CLI tools

Existing workflows continue to work via `life sync/merge/process`. New workflows use `life run <job_id>`.

## Non-Goals

- **No ProcessorRegistry** - Just `importlib` + function calls
- **No job_type dispatch** - Steps call functions directly
- **No scheduling** - Use cron, systemd timers, or editor integration
- **No web UI** - CLI-first by design
- **No JSON job definitions** - YAML only (this is a personal tool)
