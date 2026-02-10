# Life Command Audit

This document categorizes all life CLI commands by their integration pattern,
dependencies, and e006 disposition.

---

## Integration Pattern Summary

| Pattern | Description | Commands |
|---------|-------------|----------|
| **local job_runner** | Uses `run_job()` to call `life_jobs.*` processors | today, email, run, jobs, pipeline |
| **stub** | CLI preserved, bodies raise NotImplementedError | pm, work |
| **local-only** | Uses only local Python modules (no external services) | config, script |

---

## Command Details

### 1. `life today`

**Pattern:** local job_runner

**Source:** `src/life/commands/today.py`

**Subcommands:**
- `create [DATE]` — Create daily note for a specific date
- `prompt "question"` — Ask LLM about today's note

**Dependencies:**
- `life.job_runner.run_job()` — Executes jobs from `src/life/jobs/today.yaml`
- `life_jobs.today` — Processor module for daily note operations

**Integration Detail:**
Thin verb wrapper that calls `run_job("today.create_note", ...)` or `run_job("today.prompt_llm", ...)`.
Follows architecture rules exactly: argument parsing → run_job() → output formatting.

**e006 Disposition:** stays local (no changes needed)

---

### 2. `life email`

**Pattern:** local job_runner

**Source:** `src/life/commands/email.py`

**Subcommands:**
- `send TO` — Send email to one recipient
- `batch TEMPLATE RECIPIENTS` — Send templated emails to multiple recipients

**Dependencies:**
- `life.job_runner.run_job()` — Executes jobs from `src/life/jobs/email.yaml`
- `life_jobs.email` — Processor module for email operations (uses MS Graph or Gmail)

**Integration Detail:**
Thin verb wrapper that calls `run_job("email.send", ...)`, `run_job("email.send_templated", ...)`,
or `run_job("email.batch_send", ...)`. Template path resolution happens in the command layer
before passing to run_job().

**e006 Disposition:** stays local (no changes needed)

---

### 3. `life run`

**Pattern:** local job_runner

**Source:** `src/life/commands/run.py`

**Subcommands:**
- `JOB_ID [--var KEY=VALUE]` — Execute any job by name

**Dependencies:**
- `life.job_runner.run_job()` — Executes any job from `src/life/jobs/*.yaml`
- `life_jobs.*` — Any processor module referenced by the job

**Integration Detail:**
The plumbing command that exposes the job runner directly. All jobs pass through
this or equivalent `run_job()` calls. Uses `rich` for table formatting of query results.

**e006 Disposition:** stays local (no changes needed)

---

### 4. `life jobs`

**Pattern:** local job_runner

**Source:** `src/life/commands/jobs.py`

**Subcommands:**
- `list [--errors]` — List all available jobs
- `show JOB_ID` — Show job definition

**Dependencies:**
- `life.job_runner.list_jobs()` — Lists jobs from `src/life/jobs/*.yaml`
- `life.job_runner.get_job()` — Retrieves single job definition

**Integration Detail:**
Inspection commands that read job definitions without executing them.
Uses `yaml.dump()` for job display formatting.

**e006 Disposition:** stays local (no changes needed)

---

### 5. `life pipeline`

**Pattern:** local job_runner → lorchestra-library

**Source:** `src/life/commands/pipeline.py`

**Subcommands:**
- `ingest` — Run ingestion pipeline
- `canonize` — Run canonization pipeline
- `formation` — Run formation pipeline
- `project [--full-refresh]` — Run local projection pipeline
- `views` — Create BigQuery projection views
- `run-all` — Run full daily pipeline

**Dependencies:**
- `life.job_runner.run_job()` — Executes jobs from `src/life/jobs/pipeline.yaml`
- `life_jobs.pipeline` — Processor module that calls `lorchestra.execute()` via library import
- `lorchestra` (library) — Direct Python import for pipeline orchestration

**Integration Detail:**
Two-layer indirection: command → run_job() → `life_jobs.pipeline.run_lorchestra()` →
`lorchestra.execute(envelope)`. The processor explicitly declares
`__io__ = {"external": ["lorchestra.execute"]}`.

Returns structured `ExecutionResult` with `run_id`, `rows_read`, `rows_written`,
and step-level failure details via `failed_steps`.

Also imports `clear_views_directory` and `get_vault_statistics` directly from
`life_jobs.pipeline` for the `--full-refresh` flag on `project`.

**e006 Disposition:** ✅ completed (library import via `from lorchestra import execute`)

---

### 6. `life pm`

**Pattern:** stub (pending lorchestra integration)

**Source:** `src/life/commands/pm.py`

**Subcommands:**
- `exec OP [--payload-json | --payload] [--actor]` — Execute a PM operation

**Dependencies:**
- `typer` — CLI framework (argument parsing and help text preserved)

**Integration Detail:**
Stubbed in e006-03. CLI interface preserved (help text, argument parsing) but
command body raises `NotImplementedError("PM commands pending lorchestra integration — see e006-03")`.
Future pattern: `execute({"job_id": "pm.work_item.create", "payload": {...}})`.

**e006 Disposition:** ✅ completed (stubbed — workman/storacle imports removed)

---

### 7. `life work`

**Pattern:** stub (pending lorchestra integration)

**Source:** `src/life/commands/work.py`

**Subcommands:**
- `create TITLE [--project] [--kind] [--description]` — Create a new work item
- `complete WORK_ITEM_ID` — Mark a work item as complete
- `move WORK_ITEM_ID --to-project` — Move a work item to a different project

**Dependencies:**
- `typer` — CLI framework (argument parsing and help text preserved)

**Integration Detail:**
Stubbed in e006-03. CLI interface preserved (help text, argument parsing, kind validation)
but command bodies raise `NotImplementedError("PM commands pending lorchestra integration — see e006-03")`.
Future pattern: `execute({"job_id": "pm.work_item.create", "payload": {...}})`.

**e006 Disposition:** ✅ completed (stubbed — workman/storacle imports removed)

---

### 8. `life script`

**Pattern:** local-only

**Source:** `src/life/commands/script.py`

**Subcommands:**
- `run NAME [ARGS] [--force] [--yes]` — Run a quarantined script
- `info NAME` — Show metadata and TTL status for a script
- `list` — List all available scripts

**Dependencies:**
- `life.scripts.*` — Local Python modules for script metadata, state, and runner
- Bash scripts in search paths (`$LIFE_SCRIPTS_DIR`, `~/.life/scripts/`, `./scripts/`)

**Integration Detail:**
Completely local implementation with no external service calls. Scripts are
temporary glue code with TTL enforcement — they require metadata files and are
subject to age-based warnings and blocks. The runner executes bash scripts
via subprocess.

**e006 Disposition:** stays local (no changes needed)

---

### 9. `life config`

**Pattern:** local-only

**Source:** `src/life/commands/config.py`

**Subcommands:**
- `validate` — Validate configuration structure and tool availability
- `check` — Quick check if all referenced tools are installed
- `list` — List all configured tasks with tool information
- `tools` — List all registered tools in the tool registry

**Dependencies:**
- `life.config_manager` — full_validation, get_task_summary, validate_tools
- `life.registry` — is_tool_installed, list_tools

**Integration Detail:**
Configuration inspection and validation. All operations are read-only checks
against local config and tool registry. No external service calls.

**e006 Disposition:** stays local (no changes needed)

---

## e006 Disposition Summary

| Disposition | Commands | Description |
|-------------|----------|-------------|
| **stays local** | today, email, run, jobs, config, script | Uses local job_runner or local-only Python modules |
| **✅ library import (spec 02)** | pipeline | Uses `from lorchestra import execute` (completed) |
| **✅ stub (spec 03)** | pm, work | Workman/storacle imports removed, bodies raise NotImplementedError (completed) |

---

## Architectural Notes

### Three Integration Patterns Identified

1. **local job_runner** — The primary pattern documented in ARCHITECTURE.md.
   Commands call `run_job()` which loads YAML job definitions and dispatches
   to `life_jobs.*` processor modules. The job runner enforces the allowlist,
   variable substitution, and event logging.

2. **stub** — The PM commands (`pm`, `work`) are stubbed pending lorchestra
   integration (e006-03). CLI interface preserved but bodies raise NotImplementedError.
   Future pattern: `execute({"job_id": "pm.*", "payload": {...}})`.

3. **local-only** — Commands like `config` and `script` use only local Python
   modules with no external service calls (beyond subprocess for bash scripts).

### lorchestra-library (Pipeline)

The `pipeline` command is unique: it uses the job runner, but the processor
(`life_jobs.pipeline.run_lorchestra`) calls `lorchestra.execute()` via direct
library import. This returns structured `ExecutionResult` with `run_id`,
`rows_read`, `rows_written`, and step-level failure details via `failed_steps`.

The processor passes an envelope containing `job_id`, `ctx` (with `source: "life-cli"`),
and optionally `smoke_namespace` for routing BigQuery writes to test namespaces.
