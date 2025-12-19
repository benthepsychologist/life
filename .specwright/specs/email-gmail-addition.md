---
version: "0.1"
tier: C
title: Add Gmail Support to life email
owner: benthepsychologist
goal: Enable sending emails via Gmail accounts using gorch alongside existing MS Graph/morch support
labels: [feature, email, gorch]
project_slug: life
spec_version: 1.0.0
created: 2025-12-18T21:43:57.291248+00:00
updated: 2025-12-18T21:43:57.291248+00:00
orchestrator_contract: "standard"
repo:
  working_branch: "feat/email-gmail-addition"
---

# Add Gmail Support to life email

## Objective

> Enable `life email send` and `life email batch` commands to work with Gmail accounts via the gorch library, in addition to the existing MS Graph/morch support for Exchange accounts.

## Acceptance Criteria

- [ ] `life email send --account gmail-acct` sends via Gmail API when account is in `email.gmail_accounts` config
- [ ] `life email send --account msgraph-acct` continues to work via MS Graph (backwards compatible)
- [ ] `life email batch` works with both providers
- [ ] Default to msgraph for unlisted accounts (backwards compat)
- [ ] If an account appears in both `email.gmail_accounts` and `email.msgraph_accounts`, `gmail` wins (explicit precedence)
- [ ] For Gmail + multiple recipients, implementation sends one message per recipient (documented behavior)
- [ ] CI green (`ruff` + `pytest`)
- [ ] New tests cover provider lookup + both provider branches (gmail + default msgraph)

## Context

### Background

The `life email` command currently only supports Microsoft Exchange via MS Graph API (morch library). Users with Gmail accounts cannot use `life email send` to send from those accounts.

The `gorch` package provides a fully implemented `GmailClient` that mirrors the morch `GraphClient` pattern:
- `GmailClient.from_authctl(account)` for authentication
- `send_message(to, subject, body, html=False)` for sending

Provider selection should be config-driven: accounts listed in `email.gmail_accounts` use gorch, accounts in `email.msgraph_accounts` use morch, unlisted accounts default to msgraph.

### Config Example

Example config shape (lists may be omitted; missing lists default to empty; unlisted accounts default to `msgraph`):

```yaml
email:
  account: "msgraph-acct"          # default if --account not provided
  gmail_accounts:
    - "gmail-acct"
  msgraph_accounts:
    - "msgraph-acct"
```

### Constraints

- Must maintain backwards compatibility (existing msgraph accounts work unchanged)
- No edits under protected paths (`src/core/**`, `infra/**`)
- GmailClient.send_message() only accepts single recipient (loop for multiple)

## Plan

### Step 1: Add gorch dependency [G1: Code Readiness]

**Prompt:**

Add gorch as a dependency in pyproject.toml:

```toml
dependencies = [
    ...existing deps...,
    "gorch>=0.1.0",
]
```

Note: This assumes `gorch` is resolvable in CI (published to the configured package index, a VCS URL dependency, or your repo’s standard monorepo/path dependency approach). If CI cannot resolve `gorch`, dependency installation will fail.

**Allowed Paths:**

- `pyproject.toml`

**Verification Commands:**

```bash
python -m pip install -e ".[dev]"
python -c "import gorch, morch"
ruff check .
```

**Outputs:**

- `pyproject.toml` (updated)

---

### Step 2: Update email processor with provider dispatch

**Prompt:**

Modify `src/life_jobs/email.py` to support both msgraph and gmail providers:

1. Add `provider: str = "msgraph"` parameter to `send()`, `send_templated()`, and `batch_send()` functions (default remains msgraph for backwards compatibility)

2. Create internal `_send_via_provider()` helper that dispatches based on provider:

```python
def _send_via_provider(
    provider: str,
    account: str,
    to: List[str],
    subject: str,
    body: str,
    is_html: bool,
) -> Dict[str, Any]:
    """Send email via specified provider."""
    try:
        if provider == "gmail":
            from gorch.gmail import GmailClient
            client = GmailClient.from_authctl(account)
            # GmailClient only accepts single recipient (send one per recipient)
            for recipient in to:
                client.send_message(recipient, subject, body, html=is_html)
        else:  # msgraph (default)
            from morch import GraphClient
            client = GraphClient.from_authctl(account, scopes=["Mail.Send"])
            message = {
                "subject": subject,
                "body": {
                    "contentType": "HTML" if is_html else "Text",
                    "content": body,
                },
                "toRecipients": [{"emailAddress": {"address": addr}} for addr in to],
            }
            client.post("/me/sendMail", {"message": message})

        return {"sent": True, "to": to, "subject": subject, "error": None}
    except Exception as e:
        return {"sent": False, "to": to, "subject": subject, "error": str(e)}
```

3. Update `send()` to call `_send_via_provider()` (preserve existing return shape)

4. Update `send_templated()` to accept and pass `provider` parameter (preserve existing return shape: `to` remains a single string)

5. Update `batch_send()` to accept and pass `provider` parameter to `send_templated()` (no behavior change beyond provider selection)

6. Update `__io__` declaration to include gmail external call (keep existing keys; add e.g. `gmail.send_message`)

7. Update module docstring to mention Gmail support and update “Side effects” to include gorch

**Allowed Paths:**

- `src/life_jobs/email.py`

**Verification Commands:**

```bash
ruff check src/life_jobs/email.py
python -c "import sys; sys.path.insert(0, 'src'); from life_jobs.email import send, send_templated, batch_send"
```

**Outputs:**

- `src/life_jobs/email.py` (updated)

---

### Step 3: Update CLI commands with provider lookup

**Prompt:**

Modify `src/life/commands/email.py` to determine provider from config:

1. Add helper function to lookup provider for an account:

```python
def _get_provider_for_account(account: str, config: dict) -> str:
    """Determine email provider for account from config.

    Checks email.gmail_accounts and email.msgraph_accounts lists.
    If the account is in both lists, gmail wins.
    Defaults to msgraph for backwards compatibility.
    """
    email_config = config.get("email", {})
    gmail_accounts = email_config.get("gmail_accounts", [])
    msgraph_accounts = email_config.get("msgraph_accounts", [])

    if account in gmail_accounts:
        return "gmail"
    if account in msgraph_accounts:
        return "msgraph"

    # Default to msgraph for backwards compat
    return "msgraph"
```

2. Update `send()` command to:
   - Call `_get_provider_for_account()` to determine provider
   - Pass `provider` in variables dict to `run_job()`

3. Update `batch()` command similarly

4. Update help text: `app = typer.Typer(help="Send emails via MS Graph or Gmail")`

**Allowed Paths:**

- `src/life/commands/email.py`

**Verification Commands:**

```bash
ruff check src/life/commands/email.py
python -c "import sys; sys.path.insert(0, 'src'); from life.commands.email import app"
```

**Outputs:**

- `src/life/commands/email.py` (updated)

---

### Step 4: Update job definitions

**Prompt:**

Modify `src/life/jobs/email.yaml` to include provider variable in all email jobs:

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
          provider: "{provider}"

  email.send_templated:
    description: "Send templated email to one recipient"
    steps:
      - name: send
        call: life_jobs.email.send_templated
        args:
          account: "{account}"
          to: "{to}"
          template: "{template}"
          provider: "{provider}"

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
          provider: "{provider}"
```

**Allowed Paths:**

- `src/life/jobs/email.yaml`

**Verification Commands:**

```bash
python -c "import sys; sys.path.insert(0, 'src'); from pathlib import Path; from life.job_runner import load_jobs; jobs = load_jobs(Path('src/life/jobs')); assert 'email.send' in jobs"
```

**Outputs:**

- `src/life/jobs/email.yaml` (updated)

---

### Step 5: Add tests for provider dispatch

**Prompt:**

Add tests in `tests/test_life_jobs_email.py` (or update existing):

1. Test `_send_via_provider()` with mocked GraphClient
2. Test `_send_via_provider()` with mocked GmailClient
3. Test `_get_provider_for_account()` with various config scenarios:
   - Account in gmail_accounts returns "gmail"
   - Account in msgraph_accounts returns "msgraph"
   - Unlisted account returns "msgraph" (default)
4. Test that `send()` passes provider correctly

**Allowed Paths:**

- `tests/test_life_jobs_email.py`
- `tests/test_email_commands.py`

**Verification Commands:**

```bash
ruff check tests/
pytest tests/test_life_jobs_email.py -v
pytest -q --cov=life_jobs.email --cov-report=term-missing
pytest -q
```

**Outputs:**

- `tests/test_life_jobs_email.py` (new or updated)

## Models & Tools

**Tools:** bash, pytest, ruff

**Models:** (to be filled by defaults)

## Repository

**Branch:** `feat/email-gmail-addition`

**Merge Strategy:** squash
