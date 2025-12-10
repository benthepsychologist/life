---
version: "0.1"
tier: B
title: life-jobs-verbs-refactor
owner: benthepsychologist
goal: Clean up life-cli architecture to match the jobs/verbs/processors model
labels: [architecture, refactor]
project_slug: life-cli
spec_version: 1.0.0
created: 2025-12-10T17:47:00+00:00
updated: 2025-12-10T18:00:00+00:00
orchestrator_contract: "standard"
repo:
  working_branch: "feat/jobs-verbs-refactor"
---

# life-jobs-verbs-refactor

## Objective

Refactor life-cli to cleanly implement the three-layer architecture:

1. **Verbs** (Shell layer) - Human-facing commands that call jobs
2. **Jobs** (YAML) - Declarative step definitions that call processors
3. **Processors** (Engine layer) - Python functions that do the actual work

## Architecture Rules (Non-Negotiable)

### 1. VERBS must call JOBS, not processors directly
- Verbs always route through the job runner (`run_job("<job>", variables)`)
- Verbs never call `life_jobs.*` directly
- Verbs never shell out to `life run` as a subprocess

### 2. No user job locations (current phase)
- All jobs live in one place only: `src/life/jobs/*.yaml`
- There is no `~/.life/jobs`, no overrides, no merge semantics
- User adds or modifies jobs directly in the core job folder
- **Note:** This is a current-phase constraint, not a forever ban. Future multi-tenant or automation use cases may require user-defined jobs.

### 3. No transitional exceptions
- Every command follows verb → job → processor flow
- No "special" commands that bypass the architecture

### 4. Python-only orchestration
- Inside life-cli, always call the Python job runner directly
- Do not use subprocesses to call `life run` internally
- All orchestration stays in-process

### 5. Verbs contain NO business logic
Verbs may contain **at most**:
- Argument parsing (typer decorators)
- `run_job()` invocation
- Human-readable output formatting

Any conditional branching based on business rules → processor.

### 6. Processor contract
Every processor module (`life_jobs/*.py`) must:
- **Entrypoints must be pure functions** (helper classes allowed, but job-callable entrypoints are functions only)
- Have no side effects on import
- Have no module-level state
- Declare I/O via `__io__` metadata dict (see below)
- Return only JSON-serializable dicts
- **Subprocess rule:** Processors may call external tools (e.g., `llm` Python library) but NOT shell out to CLI tools. Use Python libraries instead.

**Required `__io__` declaration per processor module:**
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

### 7. Job naming convention
Jobs use **dotted namespaces**: `<domain>.<action>`

```
email.send
email.send_templated
email.batch_send
today.create_note
today.prompt_llm
dataverse.query
dataverse.update
writeback.plan
writeback.apply
```

NOT: `send_email`, `create_daily_note`, `batch_send_emails`

**Enforcement:** Job runner MUST validate job names match regex `^\w+\.\w+$` or reject with error.

### 8. Variable substitution guarantees
- All job variables are strings (converted at runtime if needed)
- Every `{var}` in job YAML must resolve or the job fails
- No nested rendering (no `{foo{bar}}`)
- Variables come from: `run_job(..., variables={...})` only

---

## Current State (The Mess)

```
src/life_jobs/              # ✓ Processors - Python functions
  ├── dataverse.py
  ├── graph.py
  ├── writeback.py
  ├── shell.py              # ✗ transitional - to be removed
  └── generate.py

src/life/jobs/              # ✓ Jobs - YAML definitions
  ├── dataverse.yaml
  ├── graph.yaml
  ├── writeback.yaml
  ├── workflows.yaml
  └── generate.yaml

~/.life/jobs/               # ✗ DELETE - should not exist
  └── (duplicates of above)

src/life/commands/          # MIXED - needs cleanup
  ├── run.py                # ✓ KEEP - plumbing
  ├── jobs.py               # ✓ KEEP - plumbing
  ├── config.py             # ✓ KEEP - utility
  ├── today.py              # ✗ CONVERT - currently bypasses architecture
  ├── sync.py               # ✗ ARCHIVE - old subprocess model
  ├── merge.py              # ✗ ARCHIVE - old subprocess model
  ├── process.py            # ✗ ARCHIVE - old subprocess model
  ├── status.py             # ✗ ARCHIVE - old subprocess model
  └── init.py               # ✗ ARCHIVE - old subprocess model
```

---

## Target State

```
src/life_jobs/              # Processors - one module per domain
  ├── dataverse.py          # Dataverse CRUD
  ├── graph.py              # MS Graph (calendar, files, raw email)
  ├── email.py              # NEW - templated email, batch send
  ├── writeback.py          # Markdown → Dataverse sync
  └── today.py              # NEW - daily note operations

src/life/jobs/              # Jobs - YAML wiring (ONE location)
  ├── dataverse.yaml
  ├── graph.yaml
  ├── email.yaml            # NEW
  ├── writeback.yaml
  ├── today.yaml            # NEW
  └── workflows.yaml

src/life/commands/          # Verbs - thin wrappers that call run_job()
  ├── run.py                # plumbing: life run <job>
  ├── jobs.py               # plumbing: life jobs list
  ├── config.py             # utility: life config
  ├── email.py              # NEW verb: life email
  ├── today.py              # CONVERTED: calls run_job()
  └── _archived/            # dead code, not imported
      ├── sync.py
      ├── merge.py
      ├── process.py
      ├── status.py
      └── init.py
```

---

## Acceptance Criteria

- [ ] Old subprocess-based commands archived and removed from CLI
- [ ] `~/.life/jobs/` no longer used - job runner reads from `src/life/jobs/` only
- [ ] `today` command converted to verb → job → processor flow
- [ ] `today.prompt_llm` uses `llm` Python library (NOT subprocess)
- [ ] `email` command added following the clean pattern
- [ ] All verbs call `run_job()` directly (Python), never subprocess
- [ ] `life_jobs.shell` removed (no subprocess escape hatch)
- [ ] All jobs use dotted namespace convention (`email.send`, not `send_email`)
- [ ] Job runner validates job names match `^\w+\.\w+$` regex
- [ ] All processor modules have `__io__` metadata dict
- [ ] ARCHITECTURE.md updated to match this spec exactly
- [ ] CI green (lint + tests)

---

## Plan

### Step 1: Archive old commands

**Files:**
- `src/life/commands/sync.py` → `_archived/`
- `src/life/commands/merge.py` → `_archived/`
- `src/life/commands/process.py` → `_archived/`
- `src/life/commands/status.py` → `_archived/`
- `src/life/commands/init.py` → `_archived/`

**Changes to `cli.py`:**
- Remove imports for archived commands
- Remove `app.add_typer()` registrations

---

### Step 2: Fix job runner path and add validator

**File:** `src/life/job_runner.py`

Changes:
- Remove any logic that reads from `~/.life/jobs/`
- Read jobs from package `src/life/jobs/` only
- Use `importlib.resources` or `Path(__file__).parent / "jobs"` to locate
- **Add job name validator:** Reject jobs not matching `^\w+\.\w+$`

```python
import re

JOB_NAME_PATTERN = re.compile(r"^\w+\.\w+$")

def validate_job_name(job_id: str) -> None:
    """Validate job name matches dotted namespace convention."""
    if not JOB_NAME_PATTERN.match(job_id):
        raise ValueError(
            f"Invalid job name '{job_id}'. "
            f"Jobs must use dotted namespace: <domain>.<action> (e.g., email.send)"
        )
```

**File:** `src/life/commands/run.py`

Changes:
- Remove `_get_jobs_dir()` that returns `~/.life/jobs`
- Pass package jobs path to `run_job()`

---

### Step 3: Convert `today` command

**NEW FILE:** `src/life_jobs/today.py`

Processor contract:
- **I/O:** Local filesystem only (daily_dir, template_path)
- **External calls:** `llm` Python library (NOT subprocess)
- **Idempotency:** `create_note` fails if note already exists (no clobber)

```python
__io__ = {
    "reads": ["template_path", "daily_dir/{date}.md", "daily_dir/{prev_dates}.md"],
    "writes": ["daily_dir/{date}.md"],
    "external": ["llm.prompt"]
}

def create_note(date: str, template_path: str, daily_dir: str) -> dict:
    """Create daily note from template.

    Reads: template_path
    Writes: daily_dir/{date}.md
    Idempotency: Fails if note already exists.

    Returns: {path: str, created: bool, error: str|None}
    """

def prompt_llm(note_path: str, question: str, context_days: int = 0) -> dict:
    """Ask LLM about today's note.

    Reads: note_path (and previous N days)
    Writes: Appends to note_path
    External: llm Python library (NOT subprocess)

    Returns: {response: str, appended_to: str, error: str|None}
    """
```

**Dependency:** Add `llm>=0.19` to pyproject.toml dependencies (move from optional to required)

**NEW FILE:** `src/life/jobs/today.yaml`
```yaml
jobs:
  today.create_note:
    description: "Create daily note from template"
    steps:
      - name: create
        call: life_jobs.today.create_note
        args:
          date: "{date}"
          template_path: "{template_path}"
          daily_dir: "{daily_dir}"

  today.prompt_llm:
    description: "Ask LLM about today's note"
    steps:
      - name: prompt
        call: life_jobs.today.prompt_llm
        args:
          note_path: "{note_path}"
          question: "{question}"
          context_days: "{context_days}"
```

**REWRITE:** `src/life/commands/today.py`
- Remove all business logic
- Call `run_job("today.create_note", variables={...})`
- Format output for humans

---

### Step 4: Add email module

**NEW FILE:** `src/life_jobs/email.py`

Processor contract:
- **Transport:** Microsoft Graph API via `morch.GraphClient`
- **Auth:** `authctl` account name passed as `account` parameter
- **Scope:** `Mail.Send` (single mailbox, no send-as/send-on-behalf)
- **Attachments:** Not supported in v1 (future: add `attachments: list[str]` param)
- **Templates:** Jinja2 with YAML frontmatter (subject in frontmatter, body in markdown)

```python
__io__ = {
    "reads": ["template", "recipients_file"],
    "writes": [],
    "external": ["msgraph.send_mail"]
}

def send(account: str, to: list, subject: str, body: str, is_html: bool = False) -> dict:
    """Send single email via MS Graph.

    Reads: None
    External: msgraph.send_mail (Mail.Send scope)

    Returns: {sent: bool, to: list, subject: str}
    """

def send_templated(account: str, to: str, template: str, context: dict = None) -> dict:
    """Render Jinja template and send to one recipient.

    Reads: template file
    External: msgraph.send_mail
    Template format: YAML frontmatter (subject) + Jinja body

    Returns: {sent: bool, to: str, subject: str}
    """

def batch_send(account: str, template: str, recipients_file: str,
               email_field: str = "email", dry_run: bool = False) -> dict:
    """Send templated emails to multiple recipients.

    Reads: template file, recipients_file (JSON)
    External: msgraph.send_mail (per recipient)
    Behavior: Continues on individual failures, reports all errors

    Returns: {sent: int, failed: int, errors: list, dry_run: bool}
    """
```

**NEW FILE:** `src/life/jobs/email.yaml`
```yaml
jobs:
  email.send:
    description: "Send a single email"
    steps:
      - name: send
        call: life_jobs.email.send
        args:
          account: "{account}"
          to: ["{to}"]
          subject: "{subject}"
          body: "{body}"

  email.send_templated:
    description: "Send templated email to one recipient"
    steps:
      - name: send
        call: life_jobs.email.send_templated
        args:
          account: "{account}"
          to: "{to}"
          template: "{template}"

  email.batch_send:
    description: "Send templated emails to list"
    steps:
      - name: batch
        call: life_jobs.email.batch_send
        args:
          account: "{account}"
          template: "{template}"
          recipients_file: "{recipients_file}"
          dry_run: "{dry_run}"
```

**NEW FILE:** `src/life/commands/email.py`
```python
from life.job_runner import run_job

@app.command()
def send(to: str, subject: str = None, body: str = None, template: str = None, ...):
    """Send email to one recipient."""
    if template:
        result = run_job("email.send_templated", variables={...})
    else:
        result = run_job("email.send", variables={...})
    # format output for human

@app.command()
def batch(template: str, recipients: str, dry_run: bool = False, ...):
    """Send templated emails to multiple recipients."""
    result = run_job("email.batch_send", variables={...})
    # format output for human
```

---

### Step 5: Remove transitional code

**DELETE:** `src/life_jobs/shell.py` - No subprocess escape hatch
**DELETE:** `src/life_jobs/generate.py` - If unused
**DELETE:** `src/life/jobs/generate.yaml` - If unused

---

### Step 5b: Rename existing jobs to dotted namespaces

**EDIT:** `src/life/jobs/dataverse.yaml`
- `query_contacts` → `dataverse.query_contacts`
- `get_contact` → `dataverse.get_contact`
- etc.

**EDIT:** `src/life/jobs/graph.yaml`
- `get_messages` → `graph.get_messages`
- `send_mail` → `graph.send_mail`
- etc.

**EDIT:** `src/life/jobs/writeback.yaml`
- `writeback_plan` → `writeback.plan`
- `writeback_apply` → `writeback.apply`

---

### Step 6: Update ARCHITECTURE.md

Rewrite to match this spec:
- Three-layer model explicit (Verbs → Jobs → Processors)
- Verbs call `run_job()` directly (Python, not subprocess)
- Jobs live in `src/life/jobs/` only
- Remove all mention of `~/.life/jobs/`
- Remove all mention of subprocess-based orchestration

---

### Step 7: Validation

```bash
ruff check .
pytest -q
life jobs list                    # shows jobs from src/life/jobs/
life email send --help            # new verb works
life today                        # converted verb works
life run email.send --var account=clinic --var to=test@example.com --var subject=Test --var body=Hello
```

**Verify dotted namespaces:**
```bash
life jobs list | grep -E "^(email|today|dataverse|writeback)\."
# Should show: email.send, email.send_templated, email.batch_send, today.create_note, etc.
```

---

## Files to Touch

| File | Action |
|------|--------|
| `src/life/commands/_archived/` | CREATE directory |
| `src/life/commands/sync.py` | MOVE to `_archived/` |
| `src/life/commands/merge.py` | MOVE to `_archived/` |
| `src/life/commands/process.py` | MOVE to `_archived/` |
| `src/life/commands/status.py` | MOVE to `_archived/` |
| `src/life/commands/init.py` | MOVE to `_archived/` |
| `src/life/cli.py` | EDIT - remove old registrations |
| `src/life/job_runner.py` | EDIT - fix jobs path |
| `src/life/commands/run.py` | EDIT - fix jobs path |
| `src/life_jobs/today.py` | CREATE - processor |
| `src/life/jobs/today.yaml` | CREATE - job definition |
| `src/life/commands/today.py` | REWRITE - use run_job() |
| `src/life_jobs/email.py` | CREATE - processor |
| `src/life/jobs/email.yaml` | CREATE - job definition |
| `src/life/commands/email.py` | CREATE - verb |
| `src/life_jobs/shell.py` | DELETE |
| `src/life_jobs/generate.py` | DELETE if unused |
| `src/life/jobs/generate.yaml` | DELETE if unused |
| `docs/ARCHITECTURE.md` | REWRITE |
| `tests/test_email.py` | CREATE |
| `tests/test_today_refactored.py` | CREATE |

---

## Dependencies

- `jinja2>=3.0` (already added to pyproject.toml)
- `morch>=0.1.0` (existing)
- `llm>=0.19` (move from optional to required for today.prompt_llm)

---

## Repository

**Branch:** `feat/jobs-verbs-refactor`

**Merge Strategy:** squash
