---
version: "0.1"
tier: C
title: Email Templates Directory
owner: benthepsychologist
goal: Add ~/.life/templates/email/ as default template directory for life email commands
labels: []
project_slug: life-cli
spec_version: 1.0.0
created: 2025-12-11T13:34:32.310834+00:00
updated: 2025-12-11T13:34:32.310834+00:00
orchestrator_contract: "standard"
repo:
  working_branch: "feat/email-templates-directory"
---

# Email Templates Directory

## Objective

Add support for a default email templates directory at `~/.life/templates/email/` so users can:
1. Reference templates by name only (e.g., `--template reminder` instead of full path)
2. Store reusable email templates in a standard location
3. Optionally configure a custom templates directory via config

## Acceptance Criteria

- [ ] CI green (lint + unit)
- [ ] 70% test coverage on new `_resolve_template_path()` function
- [ ] `life email send --template reminder` resolves to `~/.life/templates/email/reminder.md`
- [ ] `life email batch reminder recipients.json` works with template name
- [ ] Config `email.templates_dir` overrides default location
- [ ] Full paths still work (backwards compatible)
- [ ] `life_jobs.email.*` processors unchanged - accept absolute paths only, no config awareness
- [ ] `life run email.send_templated --var template=/full/path.md` works (power user path, no magic)

## Context

### Background

Currently, `life email send` and `life email batch` require full paths to template files:
```bash
life email send user@example.com --template ~/templates/reminder.md
life email batch ~/templates/reminder.md ~/data/clients.json
```

This is cumbersome for frequently-used templates. Users should be able to:
```bash
life email send user@example.com --template reminder
life email batch reminder clients.json
```

The template resolution should follow the existing `~/.life/` convention (where `events.jsonl`, `jobs/`, and `writeback/` already live).

### Template Resolution Order

1. If path contains `/`, `\`, or starts with `~`, treat as file path (existing behavior)
2. Otherwise, look up in templates directory:
   - Check `email.templates_dir` from config
   - Fall back to `~/.life/templates/email/`
   - If no extension, try `.md` first, then `.html`

**Extension precedence:** When no extension is provided, `.md` is tried first. If both `reminder.md` and `reminder.html` exist, `.md` wins. To use `.html`, specify it explicitly: `--template reminder.html`.

Note: `reminder.md` without a path separator resolves to `~/.life/templates/email/reminder.md` (user expectation).

### Constraints

- Maintain backwards compatibility with full paths
- Follow existing config patterns (see `_get_template_path()` in `commands/today.py`)

## Plan

### Files to Touch

1. `src/life/commands/email.py` - Add template resolution helper, use before `run_job()` calls
2. `tests/test_email_commands.py` - **Create new file** with tests for template resolution (command layer only)
3. `docs/ARCHITECTURE.md` - Document `email.templates_dir` config option, clarify user templates vs user jobs

**NOT touched:** `src/life_jobs/email.py` - Processors receive fully-resolved paths only. No config, no `~` expansion, no template name resolution.

### Step 1: Add template resolution helper

Add a `_resolve_template_path()` function in `src/life/commands/email.py`:

```python
def _resolve_template_path(template: str, config: dict) -> str:
    """Resolve template name to full path.

    Resolution order:
    1. If contains path separator or starts with ~, treat as file path (expand ~ and return)
    2. Otherwise, look up in templates directory

    Called by commands BEFORE run_job(). Processors only see resolved paths.
    """
    # Check if already a path (contains separator or starts with ~)
    if "/" in template or "\\" in template or template.startswith("~"):
        return str(Path(template).expanduser())

    # Get templates directory from config or default
    email_config = config.get("email", {})
    templates_dir = email_config.get("templates_dir", "~/.life/templates/email")
    templates_path = Path(templates_dir).expanduser()

    # If template already has extension, use it directly
    if template.endswith(".md") or template.endswith(".html"):
        return str(templates_path / template)

    # Try .md first, then .html (documented precedence)
    md_path = templates_path / f"{template}.md"
    if md_path.exists():
        return str(md_path)

    html_path = templates_path / f"{template}.html"
    if html_path.exists():
        return str(html_path)

    # Default to .md path (processor will give clear error if missing)
    return str(templates_path / f"{template}.md")
```

### Step 2: Update send command

Modify the `send()` command to resolve template paths:

```python
if template:
    template = _resolve_template_path(template, config)
```

### Step 3: Update batch command

Modify the `batch()` command to resolve template paths:

```python
template = _resolve_template_path(template, config)
```

### Step 4: Add tests

**Create new file** `tests/test_email_commands.py` with test cases for `_resolve_template_path()`:
- Full path passthrough (`/abs/path/bar.md` → unchanged)
- Home path passthrough (`~/foo/bar.md` → expanded path)
- Tilde-only path (`~reminder` edge case - treated as path, not template name)
- Template name resolution (`reminder` → `~/.life/templates/email/reminder.md`)
- Template with `.md` extension (`reminder.md` → `~/.life/templates/email/reminder.md`)
- Template with `.html` extension (`reminder.html` → `~/.life/templates/email/reminder.html`)
- Extension precedence (when both `.md` and `.html` exist, `.md` wins)
- Custom `templates_dir` from config overrides default

### Step 5: Validation

```bash
ruff check src/life/commands/email.py tests/test_email_commands.py
pytest tests/test_email_commands.py -v
pytest -q  # Full suite
```

## Config Example

```yaml
# .life/config.yml
email:
  account: default
  templates_dir: ~/.life/templates/email  # optional, this is the default
```

## Architecture Note

Add to `docs/ARCHITECTURE.md`:

```markdown
### User Content vs User Jobs

- `~/.life/templates/*` - User content (email templates, notes). Verbs resolve these.
- `~/.life/jobs/` - Reserved for future user-defined jobs (not yet implemented).

The "no user jobs" rule means jobs only live in `src/life/jobs/*.yaml`.
User templates are different - they're content files, not job definitions.

### Email Template Resolution

The `life email` commands support template name shorthand:

| Input | Resolves To |
|-------|-------------|
| `reminder` | `~/.life/templates/email/reminder.md` (or `.html` if `.md` missing) |
| `reminder.md` | `~/.life/templates/email/reminder.md` |
| `reminder.html` | `~/.life/templates/email/reminder.html` |
| `~/custom/path.md` | `~/custom/path.md` (expanded) |
| `/abs/path.md` | `/abs/path.md` (unchanged) |

Override the default directory with `email.templates_dir` in config.
```

## Models & Tools

**Tools:** bash, pytest, ruff

## Repository

**Branch:** `feat/email-templates-directory`

**Merge Strategy:** squash