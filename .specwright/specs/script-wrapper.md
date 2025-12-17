---
version: "0.1"
tier: C
title: Quarantined Script Runner
owner: benthepsychologist
goal: Governed bash wrapper for temporary workflow scripts with TTL-based hard block
labels: [orchestration, scripts, governance]
project_slug: life
spec_version: 1.0.0
created: 2025-12-17T20:34:45.952842+00:00
updated: 2025-12-17T20:34:45.952842+00:00
orchestrator_contract: "standard"
repo:
  working_branch: "feat/script-wrapper"
---

# Quarantined Script Runner

## Objective

> Add `life script <path>` command that wraps temporary bash scripts in TTL enforcement, event emission, and basic safety constraints. Scripts are explicitly temporary—promotion means writing a real spec, not running a command.

This is the **implementation spec** for the life repo. The governance constraints are defined in `patterns::pattern/quarantined-script-runner@0.1.0`.

## Acceptance Criteria

- [ ] `life script <name>` finds and executes `<name>.sh` from search path
- [ ] Blocks execution if `<name>.meta.yaml` missing
- [ ] Emits `script.started`, `script.completed`, `script.failed` via standard event emitter
- [ ] Warns at 1×TTL, requires confirmation at 2×TTL, HARD BLOCKS at 3×TTL
- [ ] `--yes` bypasses Level 2 confirmation (not sufficient at Level 3)
- [ ] `--force` bypasses Level 3 hard block, logs `script.override.forced` event
- [ ] Non-TTY mode: Level 2+ scripts fail unless `--yes` or `--force`
- [ ] Name validation: `[a-z0-9-]+` only, no path traversal
- [ ] Runner enforces `set -euo pipefail` or validates scripts start with it
- [ ] CI green (lint + unit)
- [ ] 80% test coverage for script runner

## Context

### Background

We have ad-hoc bash scripts for one-off workflows that bypass governance. They accumulate, break silently, and never get cleaned up. This creates two problems:

1. **No visibility**: Scripts run without events, so we can't trace failures
2. **No TTL**: Scripts stick around forever, becoming undocumented dependencies

The solution is NOT to make scripts first-class. Scripts are temporary glue. The wrapper enforces that temporariness while providing basic observability.

### Governance References

- **Pattern**: `patterns::pattern/quarantined-script-runner@0.1.0`
- **Policy**: `policies::policy/script-hygiene@0.1.0`

### Constraints

- Scripts are glue-only: orchestrate, validate, invoke. No data processing.
- Scripts are not registered capabilities—they don't appear in `life list`
- No automatic promotion command. Promotion = write a spec + build properly.
- Metadata file required; no metadata = no execution.
- Execution is subprocess-based; scripts never run in-process.

### Non-Goals

- Script discovery or cataloging (scripts are hidden; `--list` is debugging aid only)
- Script versioning (scripts are too temporary to version)
- Script dependencies (scripts call existing jobs; they don't have their own deps)
- Promotion automation (promotion means writing a proper spec)

## Design

### Script Search Paths

Search order (first match wins):

1. `$LIFE_SCRIPTS_DIR` (if set)
2. `~/.life/scripts/` (user-local, default)
3. `./scripts/` (repo-local, rare + deliberate)

Metadata travels with script in the same directory.

**Rationale**: Scripts are usually personal/temporary. Repo-scoped scripts should be rare—if you're committing it, you should probably write a proper job.

### Script State Store

Location: `~/.life/state/scripts/<name>.json`

```json
{
  "first_seen": "2025-12-17T20:34:45Z",
  "last_run": "2025-12-18T14:22:00Z",
  "run_count": 7,
  "force_count": 2
}
```

TTL escalation uses `max(created_at, first_seen)` to prevent gaming by editing `created_at`.

### Script Metadata Schema

Each script `<name>.sh` requires `<name>.meta.yaml` in the same directory:

```yaml
name: backfill-december
description: "One-time backfill for December data migration"
owner: "@benthepsychologist"  # github handle or email
created_at: 2025-12-17
ttl_days: 30
calls:
  - job/ingest-source
  - job/validate-schema
promotion_target: job/backfill-pipeline
```

Required fields:
- `name`: Script identifier, must match filename, `[a-z0-9-]+` only
- `description`: What this script does (REQUIRED, no silent mystery scripts)
- `owner`: Github handle (@user) or email; no garbage values
- `created_at`: When the script was created (ISO date YYYY-MM-DD)
- `ttl_days`: How long until warnings start
- `promotion_target`: Where this script goes when you write a real spec (e.g., `job/backfill-pipeline`, `workflow/monthly-sync`)

Optional fields:
- `calls`: Jobs/commands this script invokes (documents dependencies, enables future enforcement)
- `description`: What this script does

### Name Validation

Script names must be:
- Lowercase alphanumeric with hyphens only: `[a-z0-9-]+`
- No path separators (`/`, `\`)
- No dots (`.`) except the `.sh` extension
- No `..` or path traversal attempts

Validation happens before any filesystem access.

### TTL Escalation

| Age | Behavior |
|-----|----------|
| < 1×TTL | Normal execution |
| 1×TTL – 2×TTL | Warning: "Script is stale. Consider writing a proper spec." |
| 2×TTL – 3×TTL | Level 2: Confirmation required (if TTY). `--yes` bypasses. |
| > 3×TTL | Level 3: **HARD BLOCK**. `--yes` NOT sufficient. Only `--force` bypasses. |

**Non-interactive mode** (stdin not a TTY):
- Level 2 (2×TTL+): fails unless `--yes` or `--force`
- Level 3 (3×TTL+): fails unless `--force` (--yes not sufficient)
- No prompts; exit non-zero with clear message

**Bypass semantics**:
- `--yes`: "I acknowledge the risk" (Level 2 confirmation bypass)
- `--force`: "I accept the debt" (Level 3 block bypass, audited)

### Execution Model

Scripts run as **subprocess**, never imported/sourced into the life process:

```python
subprocess.run(
    ["bash", "-c", f"set -euo pipefail; source {script_path}", "--", *args],
    env={**os.environ, "LIFE_CORRELATION_ID": correlation_id},
    cwd=script_dir,
    check=True
)
```

- **Strict mode enforced**: `set -euo pipefail` prevents silent failures
- Controlled environment: inherit env, add correlation ID
- Working directory: script's own directory
- No shell expansion of args by life; bash handles it
- Stdout/stderr passed through

### Event Emission

Events go through Life's standard event emitter (same as `life run`), using the `orchestrator_contract: standard` envelope.

```yaml
# On start
event_type: script.started
payload:
  script: backfill-december
  script_path: ~/.life/scripts/backfill-december.sh
  script_dir_scope: user  # one of: env, user, repo
  args_hash: sha256(args)
  args_redacted: ["--source", "--dry-run"]  # flags only, no values
  correlation_id: uuid
  owner: "@benthepsychologist"
  age_days: 45
  tier: stale
  promotion_target: job/backfill-pipeline

# On success
event_type: script.completed
payload:
  script: backfill-december
  correlation_id: uuid
  duration_ms: 1234
  exit_code: 0

# On failure
event_type: script.failed
payload:
  script: backfill-december
  correlation_id: uuid
  exit_code: 1
  stderr_tail: "last 10 lines..."

# On force override
event_type: script.override.forced
payload:
  script: backfill-december
  correlation_id: uuid
  age_days: 95
  forced_by: $USER
  reason: "force"  # or "yes"
```

### CLI Interface

```bash
# Run a script (searches path)
life script backfill-december --source=prod

# Force past TTL block
life script backfill-december --force

# Acknowledge overdue risk (less aggressive than --force)
life script backfill-december --yes

# Show script metadata and TTL status (debugging aid)
life script backfill-december --info

# List scripts in search path (debugging aid, not supported UX)
life script --list
```

**Flags consumed by wrapper** (not passed to script):
- `--force`: bypass all TTL checks
- `--yes`: acknowledge overdue, bypass confirmation
- `--info`: show metadata, don't run
- `--list`: list available scripts

Everything else passes through to the bash script.

### File Structure

User-local (default):
```
~/.life/
├── scripts/
│   ├── backfill-december.sh
│   ├── backfill-december.meta.yaml
│   ├── cleanup-orphans.sh
│   └── cleanup-orphans.meta.yaml
└── state/
    └── scripts/
        ├── backfill-december.json
        └── cleanup-orphans.json
```

Repo-local (rare):
```
./scripts/
├── README.md  # "Scripts are temporary. See CONTRIBUTING.md."
├── setup-local-env.sh
└── setup-local-env.meta.yaml
```

## Plan

### Step 1: Script Metadata + Validation [G1: Foundation]

**Role:** agentic

**Prompt:**

Create `src/life/scripts/metadata.py` with:
- `ScriptMetadata` dataclass matching the schema above
- `load_metadata(name: str, search_paths: list) -> tuple[Path, ScriptMetadata]`
- `validate_name(name: str)` that enforces `[a-z0-9-]+`, rejects traversal
- `validate_metadata()` that checks required fields including `promotion_target`

Create `src/life/scripts/state.py` with:
- `ScriptState` dataclass (first_seen, last_run, run_count, force_count)
- `load_state(name: str) -> ScriptState` from `~/.life/state/scripts/<name>.json`
- `save_state(name: str, state: ScriptState)`
- `calculate_tier(metadata, state) -> fresh | stale | overdue | blocked`

**Allowed Paths:** `src/life/scripts/**`, `tests/scripts/**`

**Forbidden Paths:** `.git/**`, `*.lock`, `src/life/core/**`

**Verification:**
```bash
ruff check src/life/scripts/
pytest tests/scripts/test_metadata.py tests/scripts/test_state.py -v
```

---

### Step 2: Script Runner [G2: Execution]

**Role:** agentic

**Prompt:**

Create `src/life/scripts/runner.py` with:
- `run_script(name: str, args: list, force: bool, yes: bool)` main entry
- Search path resolution: `$LIFE_SCRIPTS_DIR` → `~/.life/scripts/` → `./scripts/`
- TTL tier check with appropriate warn/confirm/block behavior
- Non-TTY detection: if overdue and not TTY, require `--yes` or `--force`
- Subprocess execution with controlled env (add `LIFE_CORRELATION_ID`)
- Event emission through standard emitter (script.started/completed/failed)
- State update after run (first_seen, last_run, run_count)
- Force/yes override logging (script.override.forced)

**Allowed Paths:** `src/life/scripts/**`, `tests/scripts/**`

**Forbidden Paths:** `.git/**`, `*.lock`, `src/life/core/**`

**Verification:**
```bash
ruff check src/life/scripts/
pytest tests/scripts/test_runner.py -v
```

---

### Step 3: CLI Integration [G3: Interface]

**Role:** agentic

**Prompt:**

Add `script` command to CLI:
- `life script <name> [args]` - run a script
- `life script <name> --force` - bypass all TTL checks
- `life script <name> --yes` - acknowledge overdue risk
- `life script <name> --info` - show metadata and TTL status
- `life script --list` - list scripts in search path (debugging aid)

Ensure wrapper flags are consumed, not passed to script.

**Allowed Paths:** `src/life/cli/**`, `tests/cli/**`

**Forbidden Paths:** `.git/**`, `*.lock`, `src/life/core/**`

**Verification:**
```bash
ruff check src/life/cli/
pytest tests/cli/test_script_command.py -v
life script --help
```

---

### Step 4: Directory Bootstrap + Docs [G4: Setup]

**Role:** agentic

**Prompt:**

- Create `~/.life/scripts/` and `~/.life/state/scripts/` on first use if missing
- Create `scripts/README.md` in repo with "scripts are temporary" message
- Add script-related docs to CONTRIBUTING.md or create docs/scripts.md

**Allowed Paths:** `scripts/**`, `docs/**`

**Forbidden Paths:** `.git/**`, `*.lock`, `src/life/core/**`

**Verification:**
```bash
cat scripts/README.md
```

## Models & Tools

**Tools:** bash, pytest, ruff, typer (CLI framework)

**Models:** claude-sonnet-4-20250514

## Repository

**Branch:** `feat/script-wrapper`

**Merge Strategy:** squash

## References

- Pattern: `~/.local/gov-pattern-registry/patterns/incubator-script/`
- Policy: `~/.local/gov-pattern-registry/policies/script-hygiene/`