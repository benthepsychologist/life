---
id: e006-05-life-gutting
title: "Life Gutting — YAML Job Definitions, Delete Everything Else"
tier: A
owner: benthepsychologist
goal: "Gut life to ~130 lines Python + YAML job defs wrapping lorchestra jobs"
status: refined
branch: feat/life-gutting
repo:
  name: life
  url: /workspace/life
created: 2026-02-10T18:00:00Z
updated: 2026-02-10T18:00:00Z
---

# e006-05-life-gutting: Life Gutting — YAML Job Definitions

**Epic:** e006-life-thinning
**Branch:** `feat/life-gutting`
**Tier:** A

## Objective

Gut life from 3500+ lines to ~130 lines Python + ~15 YAML files.

Life becomes a pure CLI that:
1. Loads YAML job definitions
2. Builds lorchestra envelopes from CLI args
3. Calls `lorchestra.execute()`
4. Renders output

No business logic. No migration to lorchestra. Just DELETE.

## Problem

Life has accumulated significant complexity with 3500+ lines across multiple modules:
- `src/life_jobs/` directory with 1921 lines of processor implementations
- Complex job runner with event logging, variable substitution, and call resolution
- Multiple integration patterns (subprocess, direct imports, job runners)
- Significant maintenance burden for a simple CLI orchestrator

The architecture post-e005b provides a clean lorchestra library API that eliminates the need for most of life's complexity.

## Current Capabilities

Based on exploration of life.build.yaml and the current architecture:

- **CLI Commands**: Pipeline (ingest, canonize, etc.), peek, email, today, PM/work, config, script
- **Job Runner**: Complex dispatcher with variable substitution, event logging, call allowlists
- **Processors**: 7 modules in `life_jobs/` handling different domains
- **Integration Patterns**: subprocess calls to lorchestra, direct workman/storacle imports
- **Line Count**: ~3500 lines across 20+ files with significant architectural complexity

## Proposed build_delta

```yaml
target: "projects/life/life.build.yaml"
adds:
  layout:
    - path: "src/life/executor.py"
      module: executor
      role: "Main orchestration brain (~80 lines)"
    - path: "src/life/jobs/definitions/pipeline.ingest.yaml"
    - path: "src/life/jobs/definitions/pipeline.canonize.yaml"
    - path: "src/life/jobs/definitions/pipeline.formation.yaml"
    - path: "src/life/jobs/definitions/pipeline.project.yaml"
    - path: "src/life/jobs/definitions/pipeline.views.yaml"
    - path: "src/life/jobs/definitions/pipeline.run_all.yaml"
    - path: "src/life/jobs/definitions/peek.clients.yaml"
    - path: "src/life/jobs/definitions/peek.sessions.yaml"
    - path: "src/life/jobs/definitions/peek.form_responses.yaml"
    - path: "src/life/jobs/definitions/peek.raw_objects.yaml"
    - path: "src/life/jobs/definitions/peek.canonical_objects.yaml"
    - path: "src/life/jobs/definitions/peek.measurement_events.yaml"
    - path: "src/life/jobs/definitions/peek.observations.yaml"
  modules:
    - name: executor
      kind: module
      provides:
        - "load_job_defs()"
        - "build_envelope(job_def, cli_args)"
        - "render(result, output_spec, format)"
        - "run(job_id, **cli_args)"
      depends_on: []
  kernel_surfaces:
    - name: yaml_job_definition
      entrypoints:
        - "Dynamic CLI registration from YAML files"
modifies:
  modules:
    - name: cli
      changes: "Rewrite to ~50 lines with dynamic command registration from YAML"
  layout:
    - path: "src/life/cli.py"
      changes: "Complete rewrite for YAML-driven dynamic registration"
removes:
  layout:
    - path: "src/life_jobs/"
      reason: "Delete entire processor directory (1921 lines)"
    - path: "src/life/job_runner.py"
      reason: "Replace with simple executor.py"
    - path: "src/life/event_client.py"
      reason: "No longer needed with simplified architecture"
    - path: "src/life/runner.py"
      reason: "Functionality moved to executor.py"
    - path: "src/life/validation.py"
      reason: "Validation moved to lorchestra"
    - path: "src/life/date_utils.py"
      reason: "Utilities no longer needed"
    - path: "src/life/registry.py"
      reason: "No service registry needed"
    - path: "src/life/state.py"
      reason: "State management moved to lorchestra"
    - path: "src/life/config_manager.py"
      reason: "Simplified to basic config.py only"
    - path: "src/life/commands/email.py"
      reason: "Email functionality deleted"
    - path: "src/life/commands/today.py"
      reason: "Today functionality deleted"
    - path: "src/life/commands/run.py"
      reason: "Generic job runner deleted"
    - path: "src/life/commands/jobs.py"
      reason: "Job listing deleted"
    - path: "src/life/commands/pm.py"
      reason: "PM commands deleted"
    - path: "src/life/commands/work.py"
      reason: "Work commands deleted"
    - path: "src/life/commands/pipeline.py"
      reason: "Pipeline commands now YAML-driven"
  modules:
    - name: job_runner
      reason: "Replaced by simple executor pattern"
    - name: event_client
      reason: "Event logging moved to lorchestra"
    - name: processors
      reason: "All business logic moved to lorchestra"
    - name: verbs
      reason: "Commands now dynamically generated from YAML"
```

## Acceptance Criteria

- [ ] `life pipeline ingest --dry-run` works
- [ ] `life pipeline canonize` works
- [ ] `life peek clients --limit 5` returns rows
- [ ] `life peek sessions --format json` outputs JSONL
- [ ] `life config validate` still works
- [ ] `life script list` still works
- [ ] No business logic in life — only YAML + executor
- [ ] Line count: ~130 lines Python (excluding config.py and script.py)

## Constraints

- NO migration to lorchestra — just DELETE legacy code
- YAML job defs wrap EXISTING lorchestra jobs (pipeline.*, peek.*)
- Keep config.py and script.py as-is
- Dynamic CLI registration from YAML (no Python per-command)

## Phases

### Phase 1: Create executor.py

**Objective**: Create the main orchestration brain (~80 lines)

**Files to Touch**:
- `src/life/executor.py` (create)

**Implementation Notes**:

The entire brain of life (~80 lines):

```python
# src/life/executor.py
from lorchestra import execute
import json, csv, sys
from pathlib import Path
import yaml

def load_job_defs():
    """Load all YAML job definitions."""
    jobs_dir = Path(__file__).parent / "jobs" / "definitions"
    for f in jobs_dir.glob("*.yaml"):
        yield yaml.safe_load(f.read_text())

def build_envelope(job_def, cli_args):
    """Build lorchestra envelope from job def + CLI args."""
    payload = {}
    filters = []

    for arg_name, arg_spec in job_def.get("cli", {}).get("args", {}).items():
        value = cli_args.get(arg_name)
        if value is None:
            continue
        if arg_spec.get("output_only"):
            continue
        if arg_spec.get("maps_to") == "filters":
            filters.append({
                "column": arg_spec["filter_column"],
                "op": arg_spec.get("filter_op", "="),
                "value": value
            })
        else:
            payload[arg_spec.get("maps_to", arg_name)] = value

    if filters:
        payload["filters"] = filters

    return {"job_id": job_def["wraps"], "payload": payload}

def render(result, output_spec, format):
    """Render result based on output spec."""
    if output_spec.get("type") == "rows":
        rows = result.step_outputs.get("read", {}).get("items", [])
        if format == "json":
            for row in rows:
                print(json.dumps(row))
        elif format == "csv":
            if rows:
                writer = csv.DictWriter(sys.stdout, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
        else:  # table
            # Simple table output using rich or plain text
            ...
    else:  # status
        print(f"Status: {'✓' if result.success else '✗'}")
        print(f"Run ID: {result.run_id}")
        ...

def run(job_id: str, **cli_args):
    """Main entry: load def, build envelope, execute, render."""
    job_def = next(d for d in load_job_defs() if d["job_id"] == job_id)
    envelope = build_envelope(job_def, cli_args)
    result = execute(envelope)
    render(result, job_def.get("output", {}), cli_args.get("format", "table"))
```

**Verification**:
- `python -c "from life.executor import load_job_defs"` imports without error

### Phase 2: Create YAML Job Definitions

**Objective**: Create 13 YAML job definitions that wrap lorchestra jobs

**Files to Touch**:
- `src/life/jobs/definitions/pipeline.ingest.yaml` (create)
- `src/life/jobs/definitions/pipeline.canonize.yaml` (create)
- `src/life/jobs/definitions/pipeline.formation.yaml` (create)
- `src/life/jobs/definitions/pipeline.project.yaml` (create)
- `src/life/jobs/definitions/pipeline.views.yaml` (create)
- `src/life/jobs/definitions/pipeline.run_all.yaml` (create)
- `src/life/jobs/definitions/peek.clients.yaml` (create)
- `src/life/jobs/definitions/peek.sessions.yaml` (create)
- `src/life/jobs/definitions/peek.form_responses.yaml` (create)
- `src/life/jobs/definitions/peek.raw_objects.yaml` (create)
- `src/life/jobs/definitions/peek.canonical_objects.yaml` (create)
- `src/life/jobs/definitions/peek.measurement_events.yaml` (create)
- `src/life/jobs/definitions/peek.observations.yaml` (create)

**Implementation Notes**:

Example YAML structure for pipeline jobs:

```yaml
# src/life/jobs/definitions/pipeline.ingest.yaml
job_id: pipeline.ingest
wraps: pipeline.ingest
cli:
  group: pipeline
  command: ingest
  args:
    dry_run:
      flag: "--dry-run"
      ctx: true
    smoke_namespace:
      flag: "--smoke-namespace"
      ctx: true
output:
  type: result
  renderer: status
```

Example YAML structure for peek jobs:

```yaml
# src/life/jobs/definitions/peek.clients.yaml
job_id: peek.clients
wraps: peek.clients
cli:
  group: peek
  command: clients
  args:
    id:
      flag: "--id"
      maps_to: filters
      filter_column: id
    since:
      flag: "--since"
      maps_to: filters
      filter_column: created_at
      filter_op: ">="
    limit:
      flag: "--limit"
      maps_to: limit
      default: 20
    format:
      flag: "--format"
      default: table
      output_only: true
output:
  type: rows
  renderer: table
```

**Verification**:
- All YAML files parse without error
- `list(load_job_defs())` returns 13 job definitions

### Phase 3: Rewrite cli.py

**Objective**: Dynamic command registration from YAML (~50 lines)

**Files to Touch**:
- `src/life/cli.py` (rewrite)

**Implementation Notes**:

```python
# src/life/cli.py
import typer
from life.executor import run, load_job_defs

app = typer.Typer()

# Dynamically register commands from YAML
groups = {}
for job_def in load_job_defs():
    cli = job_def.get("cli", {})
    group_name = cli.get("group")
    cmd_name = cli.get("command")

    if group_name not in groups:
        groups[group_name] = typer.Typer()
        app.add_typer(groups[group_name], name=group_name)

    def make_cmd(jd):
        def cmd(**kwargs):
            run(jd["job_id"], **kwargs)
        return cmd

    groups[group_name].command(name=cmd_name)(make_cmd(job_def))

# Keep static commands
from life.commands import config, script
app.add_typer(config.app, name="config")
app.add_typer(script.app, name="script")
```

**Verification**:
- `life --help` shows pipeline, peek, config, script groups
- `life pipeline --help` shows ingest, canonize, etc.
- `life peek --help` shows clients, sessions, etc.

### Phase 4: Delete Dead Code

**Objective**: Remove all legacy code and modules

**Files to Delete**:
- `src/life_jobs/` (entire directory - 1921 lines)
- `src/life/job_runner.py`
- `src/life/event_client.py`
- `src/life/runner.py`
- `src/life/validation.py`
- `src/life/date_utils.py`
- `src/life/registry.py`
- `src/life/state.py`
- `src/life/config_manager.py`
- `src/life/commands/email.py`
- `src/life/commands/today.py`
- `src/life/commands/run.py`
- `src/life/commands/jobs.py`
- `src/life/commands/pm.py`
- `src/life/commands/work.py`
- `src/life/commands/pipeline.py`

**Implementation Notes**:

```bash
# Delete entire processor package
rm -rf src/life_jobs/

# Delete core modules
rm src/life/job_runner.py
rm src/life/event_client.py
rm src/life/runner.py
rm src/life/validation.py
rm src/life/date_utils.py
rm src/life/registry.py
rm src/life/state.py
rm src/life/config_manager.py

# Delete command modules (keep config.py and script.py)
rm src/life/commands/email.py
rm src/life/commands/today.py
rm src/life/commands/run.py
rm src/life/commands/jobs.py
rm src/life/commands/pm.py
rm src/life/commands/work.py
rm src/life/commands/pipeline.py

# Delete old job definitions directory if it exists
rm -rf src/life/jobs/
```

**Verification**:
- `find src/life -name "*.py" | wc -l` returns small number
- `wc -l src/life/*.py src/life/commands/*.py` totals ~200 lines (executor.py + cli.py + config.py + script.py)
- No import errors when running `life --help`

### Phase 5: Test Complete Integration

**Objective**: Verify all acceptance criteria are met

**Verification**:
- `life pipeline ingest --dry-run` executes and shows status
- `life pipeline canonize --dry-run` executes and shows status  
- `life peek clients --limit 5` returns rows (or empty if no data)
- `life peek sessions --format json` outputs JSONL
- `life config validate` still works
- `life script list` still works
- Total Python line count is ~130 lines (excluding config.py and script.py)