---
version: "0.1"
tier: C
title: Add life pipeline Verbs (lorchestra-first)
owner: benthepsychologist
goal: Add thin CLI verbs that invoke lorchestra composite jobs for daily pipeline operations
labels: [feature, cli, pipeline]
project_slug: life
spec_version: 1.0.0
created: 2025-12-11T00:00:00+00:00
updated: 2025-12-11T00:00:00+00:00
orchestrator_contract: "standard"
repo:
  working_branch: "feat/pipeline-verbs"
---

# Add life pipeline Verbs (lorchestra-first)

## Objective

> Add thin CLI verbs that invoke lorchestra composite jobs for daily pipeline operations.

### Background

The daily data pipeline is currently run via bash scripts in `life-cockpit/scripts/`. These scripts call `lorchestra run <job>` repeatedly with failure tracking.

This spec adds `life pipeline <verb>` commands as a thin UI layer. All pipeline logic stays in lorchestra - life just provides UX conveniences.

### Prerequisites

**BLOCKING**: Lorchestra must have these composite jobs defined before this work begins:

| Lorchestra Job | Replaces Script |
|----------------|-----------------|
| `pipeline.ingest` | `daily_ingest.sh` |
| `pipeline.canonize` | `daily_canonize.sh` |
| `pipeline.formation` | `daily_formation.sh` |
| `pipeline.project` | `daily_local_projection.sh` |
| `pipeline.views` | `create_views.sh` |
| `pipeline.daily_all` | (runs all above in sequence) |

See: `/workspace/lorchestra/.specwright/specs/pipeline-composite-jobs.md` for that work.

---

## Architecture: Three-Layer Call Chain

Each pipeline verb follows this exact call chain:

```
1. User CLI command
   └── life pipeline ingest

2. life verb → life job
   └── run_job("pipeline.ingest", variables={...})

3. life job → lorchestra runner (via pipeline.yaml)
   └── call: life_jobs.pipeline.run_lorchestra
       args:
         job_id: "pipeline.ingest"

4. runner → lorchestra (subprocess, later Python API)
   └── lorchestra run pipeline.ingest

5. lorchestra composite job
   └── (internal DAG of ingest_*, validate_* jobs)
```

**Naming convention:**
- life command names, life job names, and lorchestra job IDs are **congruent by default** for simplicity
- They CAN differ - the mapping is explicit in `pipeline.yaml` via the `job_id` argument
- Example of divergence (not used now, but allowed):
  ```yaml
  pipeline.daily:  # life job name
    steps:
      - call: life_jobs.pipeline.run_lorchestra
        args:
          job_id: "pipeline.daily_all"  # lorchestra job ID (different!)
  ```

**Boundary rules:**
- life contains NO job lists
- life contains NO DAG/batching logic
- life has NO awareness of atomic lorchestra jobs (`ingest_*`, `canonize_*`, etc.)

---

## Acceptance Criteria

**Functional:**
- [ ] `life pipeline ingest` calls `lorchestra run pipeline.ingest`
- [ ] `life pipeline canonize` calls `lorchestra run pipeline.canonize`
- [ ] `life pipeline formation` calls `lorchestra run pipeline.formation`
- [ ] `life pipeline project [--full-refresh]` calls `lorchestra run pipeline.project`
- [ ] `life pipeline views` calls `lorchestra run pipeline.views`
- [ ] `life pipeline run-all` calls `lorchestra run pipeline.daily_all`

**Dry-run (Option B - propagate to lorchestra):**
- [ ] `life --dry-run pipeline ingest` calls `lorchestra run pipeline.ingest --dry-run`
- [ ] Displays lorchestra's dry-run output (showing internal child jobs)

**Verbose:**
- [ ] `life --verbose pipeline ingest` displays lorchestra stdout/stderr in real-time

**Full-refresh:**
- [ ] `--full-refresh` clears `{vault_path}/views/*` only (not entire vault)
- [ ] `vault_path` read from `life.yml` config

**Vault statistics:**
- [ ] After `project` command, print vault statistics (clients, sessions, etc.)
- [ ] Counts are based on files under `{vault_path}/views/`, not the entire vault

**Architecture:**
- [ ] No job lists in life code
- [ ] No batching logic in life code
- [ ] Each verb makes exactly ONE lorchestra call

### Constraints

- life must NOT know internal lorchestra job IDs (only composite job names)
- life must NOT implement batching or DAG logic
- Subprocess adapter for lorchestra is acceptable (until Python API exists)

---

## Configuration

```yaml
# life.yml
pipeline:
  vault_path: ~/clinical-vault  # Path to local vault for projections
```

The verb reads `vault_path` from config, expands `~`, and uses it for:
- `--full-refresh`: clears `{vault_path}/views/*`
- Vault statistics: counts files in `{vault_path}/views/`

---

## Result Schema

`run_lorchestra()` MUST return this structure:

```json
{
  "job_id": "pipeline.ingest",
  "success": false,
  "exit_code": 1,
  "duration_ms": 12345,
  "stdout": "...",
  "stderr": "lorchestra: job failed ...",
  "error_message": "lorchestra exited with code 1"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | str | The lorchestra job that was called |
| `success` | bool | `exit_code == 0` |
| `exit_code` | int | Process exit code |
| `duration_ms` | int | Execution time |
| `stdout` | str | Captured stdout |
| `stderr` | str | Captured stderr |
| `error_message` | str\|None | Human-readable error when `success == False` |

---

## Plan

### Step 1: Create Processor Module [G0: Code Review]

**Prompt:**

Create `src/life_jobs/pipeline.py` with:

1. `run_lorchestra(job_id, dry_run, verbose)` - Execute ONE lorchestra job
   - Command: `lorchestra run <job_id>` (append `--dry-run` if dry_run=True)
   - Returns result per schema above
   - Handles lorchestra not installed gracefully
   - Captures stdout/stderr

2. `clear_views_directory(vault_path, dry_run)` - Delete `{vault_path}/views/*` only
   - Returns list of deleted paths
   - Respects dry-run (logs without deleting)

3. `get_vault_statistics(vault_path)` - Count files in vault
   - Returns: `{clients, sessions, transcripts, notes, summaries, reports}`

4. `__io__` metadata declaration

```python
__io__ = {
    "reads": ["filesystem.vault"],
    "writes": ["filesystem.vault"],
    "external": ["lorchestra.subprocess"]
}

def run_lorchestra(job_id: str, dry_run: bool = False, verbose: bool = False) -> dict:
    """Execute a lorchestra composite job.

    Args:
        job_id: Lorchestra job ID (e.g., "pipeline.ingest")
        dry_run: If True, passes --dry-run to lorchestra
        verbose: If True, streams output in real-time

    Returns:
        {job_id, success, exit_code, duration_ms, stdout, stderr, error_message}
    """
    cmd = ["lorchestra", "run", job_id]
    if dry_run:
        cmd.append("--dry-run")

    # Execute and capture...
```

**Commands:**

```bash
python -c "import sys; sys.path.insert(0, 'src'); from life_jobs import pipeline"
```

**Outputs:**
- `src/life_jobs/pipeline.py` (new)

---

### Step 2: Create Job Definitions [G0: Code Review]

**Prompt:**

Create `src/life/jobs/pipeline.yaml` with one job per phase. Each job is a single `run_lorchestra` call:

```yaml
jobs:
  pipeline.ingest:
    description: "Run ingestion pipeline"
    steps:
      - name: run
        call: life_jobs.pipeline.run_lorchestra
        args:
          job_id: "pipeline.ingest"
          dry_run: "{dry_run}"
          verbose: "{verbose}"

  pipeline.canonize:
    description: "Run canonization pipeline"
    steps:
      - name: run
        call: life_jobs.pipeline.run_lorchestra
        args:
          job_id: "pipeline.canonize"
          dry_run: "{dry_run}"
          verbose: "{verbose}"

  pipeline.formation:
    description: "Run formation pipeline"
    steps:
      - name: run
        call: life_jobs.pipeline.run_lorchestra
        args:
          job_id: "pipeline.formation"
          dry_run: "{dry_run}"
          verbose: "{verbose}"

  pipeline.project:
    description: "Run local projection pipeline"
    steps:
      - name: run
        call: life_jobs.pipeline.run_lorchestra
        args:
          job_id: "pipeline.project"
          dry_run: "{dry_run}"
          verbose: "{verbose}"

  pipeline.views:
    description: "Create BigQuery projection views"
    steps:
      - name: run
        call: life_jobs.pipeline.run_lorchestra
        args:
          job_id: "pipeline.views"
          dry_run: "{dry_run}"
          verbose: "{verbose}"

  pipeline.run_all:
    description: "Run full daily pipeline"
    steps:
      - name: run
        call: life_jobs.pipeline.run_lorchestra
        args:
          job_id: "pipeline.daily_all"
          dry_run: "{dry_run}"
          verbose: "{verbose}"
```

Note: `pipeline.run_all` (life job) maps to `pipeline.daily_all` (lorchestra job) - an example of allowed divergence.

**Commands:**

```bash
python -c "import yaml; yaml.safe_load(open('src/life/jobs/pipeline.yaml'))"
life jobs list | grep pipeline
```

**Outputs:**
- `src/life/jobs/pipeline.yaml` (new)

---

### Step 3: Create Pipeline Verb [G1: Code Review]

**Prompt:**

Create `src/life/commands/pipeline.py` with Typer subcommands.

**Note on `run_job` return shape:** `run_job(...)` returns a dict with:
```json
{
  "job_id": "pipeline.ingest",
  "steps": [
    {"name": "run", "result": <run_lorchestra result dict>}
  ]
}
```
The CLI verbs pass `steps[0]["result"]` to `_print_result`.

```python
import typer
from pathlib import Path
from life.job_runner import run_job
from life_jobs.pipeline import clear_views_directory, get_vault_statistics

app = typer.Typer(help="Daily data pipeline operations")


def _get_vault_path(config: dict) -> Path:
    """Get vault path from config, with ~ expansion."""
    pipeline_config = config.get("pipeline", {})
    vault_path = pipeline_config.get("vault_path", "~/clinical-vault")
    return Path(vault_path).expanduser()


def _print_result(result: dict):
    """Pretty-print pipeline result."""
    status = "✓ success" if result["success"] else "✗ failed"
    typer.secho(f"=== Pipeline: {result['job_id']} ===", bold=True)
    typer.secho(f"Status: {status}", fg="green" if result["success"] else "red")
    typer.echo(f"Duration: {result['duration_ms'] / 1000:.1f}s")

    if not result["success"] and result.get("error_message"):
        typer.secho(f"Error: {result['error_message']}", fg="red")


@app.command()
def ingest(ctx: typer.Context):
    """Run ingestion pipeline."""
    dry_run = ctx.obj.get("dry_run", False)
    verbose = ctx.obj.get("verbose", False)

    result = run_job("pipeline.ingest", variables={
        "dry_run": dry_run,
        "verbose": verbose,
    }, ...)
    _print_result(result["steps"][0]["result"])


@app.command()
def project(ctx: typer.Context, full_refresh: bool = typer.Option(False, help="Clear views before projecting")):
    """Run local projection pipeline."""
    config = ctx.obj.get("config", {})
    vault_path = _get_vault_path(config)
    dry_run = ctx.obj.get("dry_run", False)
    verbose = ctx.obj.get("verbose", False)

    if full_refresh:
        deleted = clear_views_directory(str(vault_path), dry_run=dry_run)
        typer.echo(f"Cleared {len(deleted)} files from {vault_path}/views/")

    result = run_job("pipeline.project", variables={
        "dry_run": dry_run,
        "verbose": verbose,
    }, ...)
    _print_result(result["steps"][0]["result"])

    # Show vault statistics
    stats = get_vault_statistics(str(vault_path))
    typer.echo("\n=== Vault Statistics ===")
    for key, count in stats.items():
        typer.echo(f"{key}: {count}")


# Similar for: canonize, formation, views, run_all
```

**Commands:**

```bash
python -m life pipeline --help
python -m life pipeline ingest --help
python -m life pipeline project --help
```

**Outputs:**
- `src/life/commands/pipeline.py` (new)

---

### Step 4: Register Verb and Test [G1: Integration Test]

**Prompt:**

1. Update `src/life/cli.py` to register pipeline verb:

```python
from life.commands import pipeline
app.add_typer(pipeline.app, name="pipeline")
```

2. Test all subcommands in dry-run mode

**Commands:**

```bash
python -m life --help
python -m life pipeline --help
python -m life --dry-run pipeline ingest
python -m life --dry-run pipeline project --full-refresh
python -m life --dry-run pipeline run-all
```

**Outputs:**
- `src/life/cli.py` (updated)

---

### Step 5: Write Tests [G2: Pre-Release]

**Prompt:**

Create `tests/test_pipeline.py`:

**Processor tests:**
- `test_run_lorchestra_dry_run` - passes `--dry-run` flag to lorchestra
- `test_run_lorchestra_success` - returns correct result schema
- `test_run_lorchestra_failure` - captures exit code and error_message
- `test_run_lorchestra_not_installed` - helpful error when lorchestra missing
- `test_clear_views_directory` - deletes only `{vault_path}/views/*`
- `test_clear_views_directory_dry_run` - logs without deleting
- `test_get_vault_statistics` - counts correctly

**Verb → job_id mapping tests (CRITICAL):**
- `test_ingest_verb_calls_correct_job_id` - asserts `run_lorchestra` called with `job_id="pipeline.ingest"`
- `test_canonize_verb_calls_correct_job_id` - asserts `job_id="pipeline.canonize"`
- `test_formation_verb_calls_correct_job_id` - asserts `job_id="pipeline.formation"`
- `test_project_verb_calls_correct_job_id` - asserts `job_id="pipeline.project"`
- `test_views_verb_calls_correct_job_id` - asserts `job_id="pipeline.views"`
- `test_run_all_verb_calls_correct_job_id` - asserts `job_id="pipeline.daily_all"`

**Integration tests:**
- `test_project_full_refresh` - clears views before running
- `test_project_shows_statistics` - displays vault stats after completion

```python
def test_ingest_verb_calls_correct_job_id(mocker):
    """Ensure life pipeline ingest calls the correct lorchestra job."""
    mock_run = mocker.patch("life_jobs.pipeline.run_lorchestra")
    mock_run.return_value = {"job_id": "pipeline.ingest", "success": True, ...}

    # Invoke verb...

    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["job_id"] == "pipeline.ingest"
```

**Commands:**

```bash
pytest tests/test_pipeline.py -v
pytest tests/test_pipeline.py --cov=src/life/commands/pipeline --cov=src/life_jobs/pipeline --cov-report=term-missing
```

**Outputs:**
- `tests/test_pipeline.py` (new)

---

## Files to Touch

| File | Action |
|------|--------|
| `src/life_jobs/pipeline.py` | CREATE |
| `src/life/jobs/pipeline.yaml` | CREATE |
| `src/life/commands/pipeline.py` | CREATE |
| `src/life/cli.py` | UPDATE |
| `tests/test_pipeline.py` | CREATE |

---

## Documentation Note

**Naming divergence:**

life command names, life job names, and lorchestra job IDs are kept identical for the pipeline verbs by convention, but they are NOT required to match. Any divergence is explicitly encoded in `pipeline.yaml` via the `job_id` argument to `run_lorchestra`.

Current mapping:
| CLI Command | life Job | lorchestra Job |
|-------------|----------|----------------|
| `life pipeline ingest` | `pipeline.ingest` | `pipeline.ingest` |
| `life pipeline canonize` | `pipeline.canonize` | `pipeline.canonize` |
| `life pipeline formation` | `pipeline.formation` | `pipeline.formation` |
| `life pipeline project` | `pipeline.project` | `pipeline.project` |
| `life pipeline views` | `pipeline.views` | `pipeline.views` |
| `life pipeline run-all` | `pipeline.run_all` | `pipeline.daily_all` ← diverges |

---

## Repository

**Branch:** `feat/pipeline-verbs`

**Merge Strategy:** squash
