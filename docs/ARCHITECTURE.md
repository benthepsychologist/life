# Life-CLI Architecture

## Overview

life-cli implements a strict three-layer architecture for personal and clinical automation:

```
┌─────────────────────────────────────────────────────────────┐
│  VERBS (Shell Layer)                                        │
│  Human-facing commands: life today | life email | life run  │
│  - Argument parsing (typer decorators)                      │
│  - run_job() invocation                                     │
│  - Human-readable output formatting                         │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ run_job("domain.action", variables={...})
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  JOBS (Declarative Layer)                                   │
│  YAML definitions: src/life/jobs/*.yaml                     │
│  - Wires verbs to processors                                │
│  - Defines multi-step workflows                             │
│  - Variable substitution                                    │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ call: life_jobs.domain.function
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  PROCESSORS (Engine Layer)                                  │
│  Python modules: src/life_jobs/*.py                         │
│  - Pure functions with __io__ metadata                      │
│  - All business logic lives here                            │
│  - Returns JSON-serializable dicts                          │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  EXTERNAL SYSTEMS                                           │
│  Dataverse | Microsoft Graph | llm library | File I/O       │
└─────────────────────────────────────────────────────────────┘
```

---

## Architecture Rules (Non-Negotiable)

### 1. Verbs MUST call Jobs, not processors directly

Verbs always route through the job runner:

```python
# CORRECT - verb calls run_job()
result = run_job("email.send", variables={"to": email, "subject": subj, ...})

# WRONG - verb calls processor directly
result = life_jobs.email.send(to=email, subject=subj, ...)
```

Verbs never shell out to `life run` as a subprocess.

### 2. Single Job Location

All jobs live in one place: `src/life/jobs/*.yaml`

There is no user job directory, no overrides, no merge semantics. Users modify jobs directly in the package.

### 3. Python-Only Orchestration

Inside life-cli, always call the Python job runner directly:

```python
from life.job_runner import run_job

result = run_job(
    "today.create_note",
    jobs_dir=_get_jobs_dir(),
    event_log=_get_event_log(config),
    variables={"date": date_str, ...},
)
```

Never use subprocesses to call `life run` internally.

### 4. Verbs Contain NO Business Logic

Verbs may contain **at most**:
- Argument parsing (typer decorators)
- `run_job()` invocation
- Human-readable output formatting

Any conditional branching based on business rules → processor.

### 5. Processor Contract

Every processor module (`life_jobs/*.py`) must:

1. **Declare I/O** via `__io__` metadata dict
2. **Entrypoints are pure functions** (helper classes allowed, but job-callable entrypoints are functions only)
3. **No side effects on import**
4. **No module-level state**
5. **Return only JSON-serializable dicts**
6. **Never print** (CLI handles output)
7. **Use Python libraries, not subprocess** for external calls

### 6. Job Naming Convention

Jobs use **dotted namespaces**: `<domain>.<action>`

```
email.send
email.send_templated
email.batch_send
today.create_note
today.prompt_llm
dataverse.query_contacts
writeback.plan
writeback.apply
```

**Enforcement:** Job runner validates job names match regex `^\w+\.\w+$` or rejects with error.

---

## The `__io__` Metadata Declaration

Every processor module must declare its I/O contract:

```python
__io__ = {
    "reads": ["template_path", "recipients_file"],
    "writes": ["daily_dir/{date}.md"],
    "external": ["msgraph.send_mail", "llm.prompt"]
}
```

This enables:
- Static analysis and auditing
- LLM-safe code generation
- Caching and idempotency checks
- Side effect tracing

---

## Directory Structure

```
src/
├── life/                      # CLI package
│   ├── cli.py                 # Main entry point
│   ├── job_runner.py          # Job execution engine
│   ├── commands/              # VERBS - thin wrappers
│   │   ├── today.py           # life today
│   │   ├── email.py           # life email
│   │   ├── run.py             # life run (plumbing)
│   │   ├── jobs.py            # life jobs (plumbing)
│   │   ├── config.py          # life config (utility)
│   │   └── _archived/         # Dead code, not imported
│   └── jobs/                  # JOBS - YAML definitions
│       ├── today.yaml
│       ├── email.yaml
│       ├── dataverse.yaml
│       ├── graph.yaml
│       ├── writeback.yaml
│       ├── generate.yaml
│       └── workflows.yaml
│
└── life_jobs/                 # PROCESSORS - Python modules
    ├── today.py               # Daily note operations
    ├── email.py               # Email sending
    ├── dataverse.py           # Dataverse CRUD
    ├── graph.py               # MS Graph API
    ├── writeback.py           # Markdown → Dataverse sync
    └── generate.py            # LLM prompt processing
```

---

## Execution Flow

### Example: `life today create`

```
┌──────────────────────────────────────────────────────────────┐
│ User runs: life today create 2025-01-15                      │
└──────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│ VERB: src/life/commands/today.py                             │
│                                                              │
│ def create_cmd(ctx, date):                                   │
│     result = run_job(                                        │
│         "today.create_note",                                 │
│         variables={                                          │
│             "date": "2025-01-15",                             │
│             "template_path": "/path/to/template.md",         │
│             "daily_dir": "/path/to/notes/daily",             │
│         },                                                   │
│     )                                                        │
│     # Format output for human                                │
└──────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│ JOB: src/life/jobs/today.yaml                                │
│                                                              │
│ jobs:                                                        │
│   today.create_note:                                         │
│     steps:                                                   │
│       - name: create                                         │
│         call: life_jobs.today.create_note                    │
│         args:                                                │
│           date: "{date}"                                     │
│           template_path: "{template_path}"                   │
│           daily_dir: "{daily_dir}"                           │
└──────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│ PROCESSOR: src/life_jobs/today.py                            │
│                                                              │
│ __io__ = {                                                   │
│     "reads": ["template_path"],                              │
│     "writes": ["daily_dir/{date}.md"],                       │
│     "external": []                                           │
│ }                                                            │
│                                                              │
│ def create_note(date, template_path, daily_dir):             │
│     # Read template, create note file                        │
│     return {"path": str(note_path), "created": True}         │
└──────────────────────────────────────────────────────────────┘
```

---

## CLI Commands

### Plumbing Commands (Automation)

| Command | Purpose |
|---------|---------|
| `life run <job>` | Execute any job by name |
| `life jobs list` | List all available jobs |
| `life jobs show <job>` | Show job definition |
| `life config` | Manage configuration |

### Human Verbs (Daily Use)

| Command | Purpose |
|---------|---------|
| `life today` | Create today's daily note |
| `life today create [DATE]` | Create note for specific date |
| `life today prompt "question"` | Ask LLM about today's note |
| `life email send` | Send single email |
| `life email batch` | Send templated emails to list |

---

## Processor Modules

| Module | Functions | Purpose |
|--------|-----------|---------|
| `life_jobs.today` | `create_note`, `prompt_llm` | Daily note operations |
| `life_jobs.email` | `send`, `send_templated`, `batch_send` | Email via MS Graph |
| `life_jobs.dataverse` | `query`, `get_single`, `create`, `update`, `delete` | Dataverse CRUD |
| `life_jobs.graph` | `get_messages`, `send_mail`, `get_calendar_events`, `get_files`, `me` | MS Graph API |
| `life_jobs.writeback` | `plan_writeback`, `apply_writeback` | Markdown → Dataverse sync |
| `life_jobs.generate` | `prompt`, `prompt_with_context`, `batch` | LLM prompt processing |

---

## Variable Substitution

Job variables follow these rules:

1. All variables are strings (converted at runtime if needed)
2. Every `{var}` in job YAML must resolve or the job fails
3. No nested rendering (no `{foo{bar}}`)
4. Variables come from: `run_job(..., variables={...})` only

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `typer` | CLI framework |
| `pyyaml` | YAML parsing |
| `morch` | MS Graph and Dataverse client |
| `jinja2` | Template rendering |
| `llm` | LLM prompt execution |

---

## Future Directions

### User-Defined Jobs (`~/.life/jobs/`)

The current architecture enforces a single job location (`src/life/jobs/`) for simplicity and predictability. However, as harmonizers and helpers mature, we may want to support user-defined jobs outside the repository:

- **`~/.life/jobs/`** - Personal job definitions
- **Job discovery** - Merge user jobs with package jobs
- **Override semantics** - User jobs can shadow package jobs
- **Validation** - Same dotted namespace rules apply

This would enable:
- Personal automation without forking the repo
- Sharing job libraries across machines
- Organization-specific job collections

Implementation would require:
- Multi-path job loading in `job_runner.py`
- Clear precedence rules (user > package)
- Documentation for job authoring

### Additional Future Work

- **Verb generation** - Auto-generate verbs from job definitions
- **Job dependencies** - DAG-based job orchestration
- **Caching** - Memoize processor calls based on `__io__` declarations
- **Dry-run propagation** - Pass dry_run flag through entire job chain

---

## Summary

- **Verbs** are thin CLI wrappers that call `run_job()`
- **Jobs** are YAML definitions that wire verbs to processors
- **Processors** are Python functions with `__io__` metadata
- All jobs use dotted namespace convention (`domain.action`)
- No subprocess orchestration - everything is Python function calls
- Business logic lives in processors, never in verbs
