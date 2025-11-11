# Life-CLI Quick Reference for Future Sessions

**Last Updated:** 2025-11-11
**Purpose:** Get a new Claude session up to speed quickly on the current state of the project

## TL;DR Current State

- **Life-CLI Status:** Phase 1 complete (124 tests passing) - core orchestration layer functional
- **Working Directory:** `~/life-cockpit/` (NOT from life-cli repo)
- **Tools Location:** `~/tools/` (temporary monorepo with 15+ CLI tools)
- **PHI Data:** `~/phi-data/` (client registries, sensitive data)
- **Production Status:** Session summary automation fully operational

## Quick Start for New Sessions

### 1. Environment Setup
```bash
# Always work from life-cockpit directory
cd ~/life-cockpit

# Activate environment to get all tools on PATH
source ~/life-cockpit/activate.sh

# Verify tools are available
msg --help
gws --help
dv --help
```

### 2. Key File Locations

**Life-CLI Package (Orchestration Layer):**
- Repo: `/home/user/life-cli/`
- Status: Phase 1 complete, don't modify unless working on orchestration features
- Tests: `pytest` in life-cli directory (124 passing)

**Tools Monorepo (Business Logic):**
- Location: `/home/user/tools/`
- Virtual env: `/home/user/tools/.venv/`
- Key tools:
  - `messages/` - Gmail client (msg command)
  - `gws/` - Google Workspace management
  - `dataverse-sync/` - Dataverse client (dv command)
  - `recipes/` - Automation scripts

**Protected Health Information:**
- Location: `/home/user/phi-data/`
- Contents: `client-registry.json`, temporary PDFs
- **NEVER put PHI in code directories**

### 3. Production Workflows

**Session Summary Automation:**
```bash
bash ~/tools/recipes/session_summary.sh <client_email>
```

**What it does:**
1. Fetches session data from Dataverse
2. Generates PDF: `Firstname L - Session Summary - YYYY-MM-DD.pdf`
3. Sends email via drben@benthepsychologist.com with PDF
4. Uploads Google Doc to client's shared Drive folder
5. Includes Drive folder link in email
6. Cleans up temporary files

**Key CLI Tools:**
```bash
# Email operations
msg send --to user@example.com --subject "Test" --body "Content"
msg me  # Check authentication status

# Google Drive/Sheets
gws client-folder <email> --json  # Lookup client folder
gws register-client <email> <folder_id> --contactid <id>
gws upload <file> --folder <folder_id>

# Dataverse queries
dv query --entity contacts --email <email> --json
dv query --entity annotations --filter "some filter"
```

## Authentication & Config

### Gmail Authentication
**Config:** `~/tools/messages/gmail_config.json`

**Configured Accounts:**
- `ben@getmensio.com` → `ben_mensio` profile
- `bfarmstrong@gmail.com` → `bfarmstrong_personal` profile
- `drben@benthepsychologist.com` → `drben_benthepsych` profile (main production account)

**Re-authenticate if needed:**
```bash
python ~/tools/authenticate_gmail.py drben_benthepsych
```

### Google Drive/Workspace
**Config:** `~/tools/gws/config.json`
**Client Registry:** `~/phi-data/client-registry.json`

Registry format:
```json
{
  "clients": {
    "client@example.com": {
      "email": "client@example.com",
      "google_folder_id": "1ABC...",
      "contactid": "uuid-from-dataverse"
    }
  }
}
```

### Dataverse
**Config:** `~/tools/dataverse-sync/config.json`
**Entities:** contacts, annotations, appointments, etc.

## Common Tasks

### Adding a New Gmail Account
1. Add to `~/tools/messages/gmail_config.json`:
   ```json
   "mailboxes": {
     "new@example.com": {
       "provider": "gmail",
       "auth_profile": "new_profile"
     }
   },
   "auth_profiles": {
     "new_profile": {
       "oauth_client_ref": "existing_workspace",
       "token": null
     }
   }
   ```
2. Authenticate: `python ~/tools/authenticate_gmail.py new_profile`

### Registering a Client Folder
```bash
# Manual registration
gws register-client client@example.com 1ABCfolderID --contactid uuid-123

# Session summary script prompts automatically on first use
bash ~/tools/recipes/session_summary.sh newclient@example.com
# (Will prompt for folder ID if not in registry)
```

### Debugging Session Summary Issues
```bash
# Check Dataverse contact lookup
dv query --entity contacts --email client@example.com --select contactid,firstname,lastname --json

# Check Gmail authentication
msg auth-status

# Check Google Drive folder access
gws client-folder client@example.com --json

# Test session summary in dry-run mode
# (No dry-run flag exists, but you can comment out the send/upload sections in the script)
```

## Architecture Principles

### Life-CLI Philosophy
1. **Orchestration, not implementation** - Life-CLI coordinates, doesn't do the work
2. **Unix philosophy** - Each tool does one thing well
3. **Data over code** - Workflows are YAML, not Python

### Current Temporary Setup
- **Why:** Immediate productivity while finalizing architecture
- **Goal:** Modularize tools once data pipeline design is complete
- **Status:** Acceptable temporary state, documented in README

### Data Segregation
- **Code/Tools:** `~/tools/` (git, sharable, no PHI)
- **Protected Data:** `~/phi-data/` (never in git, client info)
- **Working Directory:** `~/life-cockpit/` (config, scripts)
- **Life-CLI Repo:** `/home/user/life-cli/` (orchestration only, no business logic)

## Important Notes for Future Claude Sessions

### DO:
- ✅ Work from `~/life-cockpit/` directory
- ✅ Source `activate.sh` before running commands
- ✅ Put PHI in `~/phi-data/`, never in code directories
- ✅ Use existing CLI tools (msg, gws, dv) for operations
- ✅ Test changes with real workflows (session_summary.sh)
- ✅ Check authentication status if APIs fail
- ✅ Update this document when making significant changes

### DON'T:
- ❌ Put PHI in `~/tools/` or `~/life-cli/`
- ❌ Work from life-cli repo directory (use `~/life-cockpit/`)
- ❌ Add business logic to life-cli package (orchestration only)
- ❌ Commit PHI to git
- ❌ Modify OAuth configs without backing up first
- ❌ Use Python 3.12+ f-strings with backslashes (syntax error)

### Python 3.12+ F-String Gotcha
**BROKEN:**
```python
f"text {variable.replace('a', 'b')}"  # ❌ Syntax error
```

**FIXED:**
```python
temp = variable.replace('a', 'b')
f"text {temp}"  # ✅ Works
```

## Testing Status

### Life-CLI Tests
```bash
cd ~/life-cli
pytest  # 124 tests passing
```

**Coverage:**
- Config loading and validation
- State management for incremental sync
- Variable substitution
- Command execution

### Manual Testing
```bash
# Test session summary workflow
bash ~/tools/recipes/session_summary.sh bfarmstrong@gmail.com

# Expected output:
# - Dataverse contact lookup
# - PDF generation
# - Email sent confirmation
# - Google Doc uploaded
# - PDF cleanup
```

## Recent Changes Summary

**Session Summary Script (`~/tools/recipes/session_summary.sh`):**
- ✅ Switched from Microsoft Graph to Gmail API
- ✅ Added Google Drive upload (HTML → Google Doc conversion)
- ✅ Folder registry with contactid for future-proofing
- ✅ PDF filename format: `Firstname L - Session Summary - YYYY-MM-DD.pdf`
- ✅ PHI storage moved to `~/phi-data/`
- ✅ Drive folder link in email body
- ✅ Automatic cleanup after successful send

**Gmail Config:**
- ✅ Added drben@benthepsychologist.com account
- ✅ OAuth tokens auto-refresh

**GWS (Google Workspace) Tool:**
- ✅ Client folder registry at `~/phi-data/client-registry.json`
- ✅ Contactid support for future Dataverse integration
- ✅ Fixed registry type checking (dict vs list)

## Common Error Messages & Solutions

### "dv: command not found"
**Solution:** Source the activation script
```bash
source ~/life-cockpit/activate.sh
```

### "Token expired" or OAuth errors
**Solution:** Re-authenticate
```bash
python ~/tools/authenticate_gmail.py drben_benthepsych
```

### "Registry is a list, not dict" error
**Solution:** Fixed in gws_cli.py, but if occurs:
```bash
# Check registry structure
cat ~/phi-data/client-registry.json
# Should have: {"clients": {}, "metadata": {}}
```

### F-string syntax errors
**Solution:** Extract backslash operations outside f-strings (Python 3.12+)

## Project Vision

**Current State:** Production-ready workflows with temporary tools monorepo

**Future State:** Life-CLI as lightweight orchestrator with modularized tools
- Each tool (msg, gws, dv, etc.) becomes its own package
- Life-CLI orchestrates via YAML workflows
- State tracking and incremental syncing built-in

**Timeline:** Refactor when data pipeline architecture is finalized (not blocking current work)

---

**For Claude:** Read this document first when starting a new session. It contains everything you need to know about the current state, common operations, and architecture decisions. Refer to [README.md](../README.md) for user documentation and [ARCHITECTURE.md](ARCHITECTURE.md) for design philosophy.
