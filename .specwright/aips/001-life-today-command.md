---
version: "0.1"
tier: C
title: Add 'life today' Command for Daily Note Management
owner: user
goal: Enable CLI-based daily operational note creation and LLM-powered reflection
labels: [feature, cli, notes]
orchestrator_contract: "standard"
repo:
  working_branch: "feat/life-today-command"
---

# Add 'life today' Command for Daily Note Management

## Objective

> Enable CLI-based daily operational note creation and LLM-powered reflection

### Background

The legacy `life today` command from `~/tools/life/` provided valuable daily note management capabilities but was not integrated with the new life-cli orchestration system. This command helps maintain daily operational notes with templating support and LLM-based reflection capabilities.

Daily notes follow a structured format (Focus, Status Snapshot, Tasks, Reflection) and are stored in markdown format. The LLM integration allows users to ask questions about their notes and automatically appends Q&A sections for future reference.

### Acceptance Criteria

- `life today` creates today's daily note from template
- `life today create [YYYY-MM-DD]` creates note for specific date
- `life today prompt "question"` integrates with `llm` CLI tool
- `life today prompt "question" --context N` includes N previous days as context
- Graceful error handling for:
  - Note already exists (warn, exit cleanly)
  - Missing template (auto-create with sensible defaults)
  - Missing llm CLI (helpful error message)
  - Invalid date format (clear error message)
- Template supports `{{date}}` variable substitution
- Respects life-cli's `--dry-run` and `--verbose` flags
- Configuration via optional `today:` section in life.yml:
  ```yaml
  today:
    daily_dir: ~/vaults/personal-vault/notes/ops/daily
    template_path: ~/vaults/personal-vault/notes/templates/daily-ops.md
  ```
- Sensible defaults if config section omitted
- 90%+ test coverage on new code
- All existing tests continue to pass
- Documentation updated with usage examples

### Constraints

- No edits to protected paths (`src/life/state.py`, `src/life/config.py` core logic)
- Must work with existing life-cli configuration system
- Must follow established patterns (Typer subcommands, context passing)
- Should be tool-agnostic (calls external `llm` CLI, doesn't implement LLM logic)
- No breaking changes to existing commands

## Plan

### Step 1: Port Command Implementation [G0: Code Review]

**Prompt:**

Port the `life today` command from `~/tools/life/commands/today.py` to `src/life/commands/today.py` with the following adaptations:

1. Create new file `src/life/commands/today.py` as a Typer subcommand
2. Implement three commands:
   - `life today` (default: create today's note)
   - `life today create [date]` (create note for specific date)
   - `life today prompt "question" [--context N]` (LLM integration)
3. Adapt configuration handling:
   - Read `today:` section from life-cli config if present
   - Use sensible defaults: `~/vaults/personal-vault/notes/ops/daily/` and `~/vaults/personal-vault/notes/templates/daily-ops.md`
   - Remove hardcoded workspace detection logic (use config paths)
4. Support `--dry-run` mode (show what would be created without writing files)
5. Support `--verbose` mode (show detailed path resolution)
6. Template features:
   - Support `{{date}}` variable substitution
   - Auto-create default template if missing
7. Error handling:
   - Graceful exit if note exists
   - Clear error for invalid date format
   - Helpful message if `llm` CLI not installed
8. Use colorized output (typer.secho) for user feedback

**Commands:**

```bash
# Verify the file is syntactically correct
python -c "import sys; sys.path.insert(0, 'src'); from life.commands import today"
```

**Outputs:**
- `src/life/commands/today.py` (new)

---

### Step 2: Register Subcommand in CLI [G1: Integration Test]

**Prompt:**

Integrate the `today` subcommand into the main CLI:

1. Update `src/life/cli.py`:
   - Import `today` module
   - Register with `app.add_typer(today.app, name="today")`
   - Ensure context passing works (config, dry_run, verbose flags)
2. Update config validation if needed to support optional `today:` section
3. Test that context (config, dry_run, verbose) is properly passed to today commands

**Commands:**

```bash
# Verify CLI loads without errors
python -m life --help
python -m life today --help
python -m life today create --help
python -m life today prompt --help
```

**Outputs:**
- `src/life/cli.py` (updated)
- `src/life/config.py` (updated if needed for config schema)

---

### Step 3: Write Comprehensive Tests [G2: Test Coverage]

**Prompt:**

Create comprehensive test suite for the `today` command:

1. Create `tests/test_today.py` with test coverage for:
   - **Template loading:**
     - Load existing template
     - Auto-create missing template with defaults
     - Template variable substitution (`{{date}}`)
   - **Date parsing:**
     - Default to today's date
     - Parse valid YYYY-MM-DD format
     - Reject invalid date formats
   - **Note creation:**
     - Create note successfully
     - Error if note already exists
     - Create parent directories if missing
     - Respect --dry-run (no file writes)
   - **LLM integration:**
     - Call llm CLI with today's note
     - Include context from previous N days
     - Append Q&A section to note
     - Error if today's note doesn't exist
     - Error if llm CLI not installed
   - **Configuration:**
     - Use config paths if provided
     - Fall back to sensible defaults
     - Path expansion (~/ and env vars)
   - **Verbose mode:**
     - Show path resolution details
2. Use pytest fixtures for:
   - Temporary directories
   - Mock config objects
   - Mock subprocess calls (for llm CLI)
3. Achieve 90%+ code coverage on new code
4. Ensure all tests pass

**Commands:**

```bash
# Run new tests
pytest tests/test_today.py -v

# Check coverage
pytest tests/test_today.py --cov=src/life/commands/today --cov-report=term-missing

# Run full test suite to ensure no regressions
pytest tests/ -v
```

**Outputs:**
- `tests/test_today.py` (new)
- Coverage report (90%+ on today.py)

---

### Step 4: Update Documentation [G3: Documentation Review]

**Prompt:**

Update project documentation with `life today` command:

1. **README.md:**
   - Add `today` to command reference table
   - Add usage examples:
     ```bash
     # Create today's note
     life today

     # Create note for specific date
     life today create 2025-11-10

     # Ask LLM about today's note
     life today prompt "What were my main accomplishments?"

     # Include 3 previous days as context
     life today prompt "What patterns do you see?" --context 3
     ```
   - Document configuration options in Config section
2. **docs/ARCHITECTURE.md:**
   - Add note about `today` command being a helper utility (distinct from data pipeline commands)
   - Explain decision to integrate vs keep standalone
3. **Example config:**
   - Update `test-config.yml` or create example showing `today:` section

**Outputs:**
- `README.md` (updated)
- `docs/ARCHITECTURE.md` (updated)
- `test-config.yml` or example config (updated)

---

### Step 5: End-to-End Validation [G4: Pre-Release]

**Prompt:**

Perform end-to-end validation of the feature:

1. Install package in development mode: `pip install -e .`
2. Create test vault directory structure if needed
3. Run through user workflows:
   - Create today's note (`life today`)
   - Verify template created if missing
   - Verify note created with correct date
   - Try creating duplicate (should warn and exit)
   - Create note for specific date (`life today create 2025-11-15`)
   - Test dry-run mode (`life today --dry-run`)
   - Test verbose mode (`life today --verbose`)
   - If `llm` CLI available, test prompt command
4. Run full test suite: `pytest tests/ -v`
5. Check code quality: `ruff check src/life/commands/today.py`
6. Verify no regressions in existing commands

**Commands:**

```bash
# Install in development mode
pip install -e .

# Run full test suite
pytest tests/ -v --cov=src/life --cov-report=term-missing

# Check code quality
ruff check src/

# Manual testing
life today --help
life today --dry-run --verbose
life today create 2025-11-15 --dry-run
```

**Success Criteria:**
- All tests pass (100% of test suite)
- 90%+ coverage on new code
- No ruff violations
- Manual workflows complete successfully
- No regressions in existing functionality

**Outputs:**
- Test results (all passing)
- Coverage report (90%+ on today.py)
- Ruff check (no violations)
- Manual validation checklist (completed)

---

## Orchestrator

**State Machine:** Standard (pending → running → awaiting_human → succeeded/failed)

**Tools:** bash, pytest, ruff, python

**Models:** (defaults)

## Repository

**Branch:** `feat/life-today-command`

**Merge Strategy:** squash

**Commit Message Template:**
```
feat: Add 'life today' command for daily note management

Implements:
- Daily note creation with template support
- LLM-powered note reflection via 'llm' CLI
- Configurable paths via life.yml
- Auto-template creation with sensible defaults
- Comprehensive test coverage (90%+)

Closes #<issue-number>
```

---

## Rollback Procedure

If issues are discovered after merge:

1. Revert the merge commit: `git revert <merge-commit>`
2. The `today` command will be removed from CLI
3. No data loss (command only creates files, doesn't modify existing data)
4. Users can continue using old `~/tools/life/` implementation if needed

## Notes

- This command is conceptually different from life-cli's core mission (data pipeline orchestration)
- It's a helper/utility command for personal productivity
- Future consideration: Could be moved to separate package if life-cli scope creep becomes an issue
- LLM integration is optional (graceful degradation if `llm` CLI not installed)
