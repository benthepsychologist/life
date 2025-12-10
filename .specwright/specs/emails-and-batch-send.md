---
version: "0.1"
tier: C
title: Emails and batch send
owner: benthepsychologist
goal: Implement email sending and batch send with Jinja templates as job runner functions
labels: []
project_slug: life-cli
spec_version: 1.0.0
created: 2025-12-10T17:13:55.375033+00:00
updated: 2025-12-10T17:13:55.375033+00:00
orchestrator_contract: "standard"
repo:
  working_branch: "feat/emails-and-batch-send"
---

# Emails and batch send

## Objective

Add a `life_jobs.messages` module with functions for:
1. **`send_mail`** - Send a single email via Microsoft Graph (wrapper with template support)
2. **`send_templated`** - Render a Jinja template and send to one recipient
3. **`batch_send`** - Render a Jinja template for each recipient in a JSON list and send all

## Acceptance Criteria

- [ ] CI green (lint + unit)
- [ ] No protected paths modified
- [ ] 70% test coverage achieved
- [ ] `life run send_test_email` sends a single email via Graph
- [ ] `life run batch_send_test` sends templated emails to multiple recipients
- [ ] Templates support YAML frontmatter (subject, defaults) + Jinja body

## Context

### Background

We are migrating CLI tools from `/workspace/tools/` into life-cli's job runner. The existing `life_jobs.graph.send_mail` function provides basic email sending via Microsoft Graph. We need higher-level functions that support:

1. **Markdown templates** with YAML frontmatter for subject/defaults
2. **Jinja2 rendering** with `{{variable}}` substitution
3. **Batch sending** - loop over a JSON list of recipients, render template per-recipient, send each

This enables workflows like:
- Send a single notification email
- Batch send personalized reminders to a list of clients

### Template Format

Templates are Markdown files with YAML frontmatter:

```markdown
---
subject: "Follow-up reminder for {{client_name}}"
# Default values (overridden by recipient data)
signature: Dr. Benjamin Armstrong
form_url: https://forms.example.com/assessment
---

Dear {{client_name}},

Please complete your follow-up assessment using the link below.

{{form_url}}

Thank you,
{{signature}}
```

### Constraints

- No edits under protected paths (`src/core/**`, `infra/**`)
- Follow Rule 8: never print, never read global config, return simple dicts
- Use `morch.GraphClient` for actual email sending (already used in `life_jobs.graph`)
- Add `jinja2` as a dependency

## Plan

### Files to Touch

1. `src/life_jobs/email.py` - **NEW** - Core email functions (domain module)
2. `src/life/commands/email.py` - **NEW** - `life email` verb (Shell layer)
3. `src/life/cli.py` - Register email command
4. `src/life/jobs/email.yaml` - **NEW** - Job definitions
5. `tests/test_email.py` - **NEW** - Unit tests
6. `pyproject.toml` - Add `jinja2` dependency

---

### Step 1: Add jinja2 dependency

Update `pyproject.toml` to include `jinja2>=3.0`.

---

### Step 2: Implement `life_jobs.email` module (Engine layer)

**`src/life_jobs/email.py`**

Functions:
- `send()` - Send a single email (plain or HTML)
- `send_templated()` - Render Jinja template and send to one recipient
- `batch_send()` - Render template for each recipient in a list, send all

Helper functions (internal):
- `parse_template()` - Extract YAML frontmatter + body from markdown
- `render_template()` - Jinja2 render with context merging

All functions follow Rule 8: no printing, return dicts only.

---

### Step 3: Implement `life email` verb (Shell layer)

**`src/life/commands/email.py`**

The verb is a thin wrapper that:
1. Parses CLI flags/args
2. Builds a normalized args dict
3. Calls `life_jobs.email.*` functions directly
4. Formats output for humans

**Subcommands:**

```bash
# Send plain email
life email send <to> --subject "Subject" --body "Body text"
life email send <to> -s "Subject" -b "Body text"

# Send templated email
life email send <to> --template ~/templates/welcome.md --var name=Alice

# Batch send
life email batch --template ~/templates/reminder.md --recipients ~/data/clients.json
life email batch --template ~/templates/reminder.md --recipients ~/data/clients.json --dry-run
```

**Design notes:**
- The verb does NOT shell out to `life run` - it calls `life_jobs.email.*` directly
- Jobs YAML exists for automation (`life run send_email --var to=...`) but the verb is the human UX
- `--account` defaults to config value or "default" if not specified
- `--dry-run` inherited from global `life --dry-run email ...`

---

### Step 4: Register in cli.py

Add:
```python
from life.commands import email
app.add_typer(email.app, name="email")
```

Add "email" to `commands_with_optional_config` list.

---

### Step 5: Job YAML definitions

**`src/life/jobs/email.yaml`**

```yaml
jobs:
  send_email:
    description: "Send a single email"
    steps:
      - name: send
        call: life_jobs.email.send
        args:
          account: "{account}"
          to: ["{to}"]
          subject: "{subject}"
          body: "{body}"

  send_templated_email:
    description: "Send a templated email to one recipient"
    steps:
      - name: send
        call: life_jobs.email.send_templated
        args:
          account: "{account}"
          to: "{to}"
          template: "{template}"

  batch_send_emails:
    description: "Send templated emails to multiple recipients"
    steps:
      - name: batch
        call: life_jobs.email.batch_send
        args:
          account: "{account}"
          template: "{template}"
          recipients_file: "{recipients_file}"
          dry_run: false
```

---

### Step 6: Write unit tests

**`tests/test_email.py`**

Test coverage for:
- `parse_template` - frontmatter extraction, no frontmatter case
- `render_template` - Jinja substitution, defaults merging
- `send` - mocked GraphClient call
- `send_templated` - end-to-end with mock
- `batch_send` - multiple recipients, dry_run mode, missing email field errors

---

### Step 7: Validation

```bash
ruff check .
pytest tests/test_email.py -v
pytest -q  # full suite
```

## Models & Tools

**Tools:** bash, pytest, ruff

**Dependencies:** jinja2>=3.0

## Repository

**Branch:** `feat/emails-and-batch-send`

**Merge Strategy:** squash