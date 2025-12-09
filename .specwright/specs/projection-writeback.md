---
version: "0.1"
tier: C
title: projection writeback
owner: benthepsychologist
goal: Implement projection writeback
labels: []
project_slug: life-cli
spec_version: 1.0.0
created: 2025-12-09T16:05:53.242692+00:00
updated: 2025-12-09T16:05:53.242692+00:00
orchestrator_contract: "standard"
repo:
  working_branch: "feat/projection-writeback"
---

# projection writeback

## Objective

Enable bidirectional sync between projected markdown files in `~/clinical-vault/views/` and Dataverse. Users edit frontmatter in markdown files, then writeback detects changes and PATCHes them back to Dataverse.

## Acceptance Criteria

- [ ] CI green (lint + unit)
- [ ] `life run writeback_plan` generates a plan file from changed markdown files
- [ ] `life run writeback_apply` applies the plan to Dataverse
- [ ] 70% test coverage on new code

## Context

### Background

The current pipeline is one-way:
1. `lorchestra` pulls data from Dataverse → BigQuery → SQLite (`local.db`) → Markdown files
2. Users can view and edit the markdown files in their vault
3. There's no way to push changes back to Dataverse

The writeback feature closes this loop:
1. **project** → populate `~/clinical-vault` + `local.db` with `projected_at` timestamp
2. **edit markdown** → user modifies frontmatter (title, datetime, etc.)
3. **writeback-plan** → detect changes by comparing file mtime vs `projected_at`
4. **writeback-apply** → PATCH changes to Dataverse
5. **project again** → reset everything to fresh state

### Data Model

**local.db** = "projection baseline" only, owned by the projection job. Says "this is what we generated last time from Dataverse."

**Writeback layer** = stateless between projections. It only needs:
- The projected markdown files (frontmatter has identity + `projected_at`)
- Frontmatter → Dataverse field mapping
- Idempotence is "soft": if you PATCH the same payload twice, it's harmless

`local.db` is optional - only used for baseline validation if you want extra safety.

### Constraints

- No edits to protected paths (`src/core/**`, `infra/**`)
- Writeback does NOT update SQLite - projection is the only writer
- Changes detected via: `file_mtime > projected_at + epsilon`

### Key Design Decisions

**1. Frontmatter is the source of truth**

All identity and change detection info lives in frontmatter:
- `entity` + `record_id`: identify the Dataverse record
- `projected_at`: baseline for change detection
- `record_id_field`: documents which source field the ID came from

Writeback globs files and reads frontmatter directly - no path reconstruction or sqlite lookups for identity.

**2. Time handling**

- `projected_at` stored as UTC ISO string: `datetime.now(timezone.utc).isoformat()`
- Comparison:
  - Parse `projected_at` with `datetime.fromisoformat()`
  - Get file mtime with `os.path.getmtime(path)` → float (seconds since epoch)
  - Convert `projected_at` to epoch: `projected_at_dt.timestamp()`
  - `epsilon = 2.0` seconds (covers filesystem resolution + processing latency)
  - Condition: `if file_mtime > projected_at_ts + epsilon:`

**3. Empty result handling**

If BQ returns 0 rows, `SyncSqliteProcessor`:
- Still ensures table exists with correct schema (CREATE TABLE IF NOT EXISTS with known columns)
- Deletes existing rows (full replace semantics)
- Commits empty table
- Does NOT blow up on `rows[0]`

**4. Frontmatter error handling**

`plan_writeback` is **lenient** - it skips bad files rather than failing the whole plan:
- File has no frontmatter → skip
- Frontmatter is invalid YAML → skip, record in `errors`
- Required keys missing (`entity`, `record_id`, `projected_at`) → skip, record in `errors`
- Missing mapped fields (title, datetime, etc.) → they just don't appear in the patch, not an error

Summary includes: `{"files_skipped": 2, "errors": [{"path": "...", "reason": "..."}]}`

**5. Field mapping is explicit and isolated**

Frontmatter → Dataverse mapping lives in a dedicated dict/function, not inline:

```python
FRONTMATTER_TO_DV = {
    "title": "crf_title",
    "datetime": "crf_starttime",
    # ...
}

def build_session_patch(frontmatter: dict) -> dict:
    return {dv_field: frontmatter.get(fm_field)
            for fm_field, dv_field in FRONTMATTER_TO_DV.items()
            if frontmatter.get(fm_field) is not None}
```

This makes adding new entities (e.g., `crf_client`) straightforward.

## Plan

### Files to Touch

1. `/workspace/lorchestra/lorchestra/processors/projection.py` - Add `projected_at` column to `SyncSqliteProcessor`, inject `_projected_at` for frontmatter in `FileProjectionProcessor`
2. `/workspace/lorchestra/tests/test_projection_processor.py` - Add tests for `projected_at` column and frontmatter injection
3. `/workspace/life-cli/src/life_jobs/writeback.py` - New file with `plan_writeback()` and `apply_writeback()`
4. `/workspace/life-cli/tests/test_writeback.py` - New file with tests for writeback functions
5. `/workspace/life-cli/examples/jobs/writeback.yaml` - Job definitions for writeback

---

### Step 1: Add `projected_at` to lorchestra (in `/workspace/lorchestra`)

#### 1a. `SyncSqliteProcessor.run()` - Add `projected_at` column

**Note:** `storage_client.query_to_dataframe()` returns `list[dict[str, Any]]`, not a pandas DataFrame. The name is historical.

```python
from datetime import datetime, timezone

# Capture projection time BEFORE any processing
projection_time = datetime.now(timezone.utc).isoformat()

# Query BQ - returns list[dict], not DataFrame
rows: list[dict[str, Any]] = storage_client.query_to_dataframe(f"SELECT * FROM {view_name}")

# Handle empty results - don't blow up on rows[0]
if not rows:
    # Early return is fine here - existing code already handles this
    return

# Get columns from first row, add projected_at
columns = list(rows[0].keys()) + ["projected_at"]
col_defs = ", ".join(f'"{col}" TEXT' for col in columns)

# Create table, delete existing, insert new
conn.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({col_defs})')
conn.execute(f'DELETE FROM "{table}"')

# Insert with projected_at appended
placeholders = ", ".join("?" * len(columns))
col_names = ", ".join(f'"{c}"' for c in columns)
insert_sql = f'INSERT INTO "{table}" ({col_names}) VALUES ({placeholders})'

for row in rows:
    values = [str(row.get(col)) if row.get(col) is not None else None for col in columns[:-1]]
    values.append(projection_time)  # Same timestamp for all rows in this sync
    conn.execute(insert_sql, values)
```

#### 1b. `FileProjectionProcessor.run()` - Add `entity`, `record_id`, `projected_at` to frontmatter

Instead of tracking in a separate table, add the required fields directly to frontmatter.

**Job spec addition:**
```json
{
  "sink": {
    "base_path": "~/clinical-vault/views",
    "path_template": "...",
    "content_template": "...",
    "front_matter": {
      "source_type": "clinical_document",
      "entity": "crf_sessions",           # Constant: Dataverse entity name
      "record_id": "{session_id}",        # Template: the GUID field from row data
      "record_id_field": "session_id",    # Constant: documents which field record_id came from
      "projected_at": "{_projected_at}",  # Special variable injected by processor
      "idem_key": "{idem_key}",
      "session_id": "{session_id}",       # Keep original for readability
      "client_id": "{client_id}",
      "doc_type": "{doc_type}"
    }
  }
}
```

For a different entity type (e.g., progress reports):
```json
{
  "front_matter": {
    "entity": "crf_documents",
    "record_id": "{document_id}",
    "record_id_field": "document_id",
    "projected_at": "{_projected_at}",
    ...
  }
}
```

**Implementation:**
```python
# Capture projection time at start of job
projection_time = datetime.now(timezone.utc).isoformat()

# In the file-writing loop:
for row in rows:
    # Inject _projected_at into row data for template substitution
    row_with_meta = {**row, "_projected_at": projection_time}

    # Build frontmatter (existing logic, but now row has _projected_at)
    resolved = {}
    for key, value in front_matter_spec.items():
        if isinstance(value, str):
            resolved[key] = value.format(**row_with_meta)
        else:
            resolved[key] = value

    # Write file with frontmatter...
```

**Key point:** `projected_at` is the same for all files in a single projection run, ensuring consistent baseline for change detection.

**Tests:**
- `test_sync_sqlite_adds_projected_at_column` - verify column exists
- `test_sync_sqlite_projected_at_is_valid_iso_timestamp` - parse with fromisoformat()
- `test_sync_sqlite_projected_at_same_for_all_rows` - all rows get same timestamp
- `test_sync_sqlite_handles_empty_results` - no crash on 0 rows
- `test_file_projection_injects_projected_at` - `_projected_at` available in frontmatter template

---

### Step 2: Implement `life_jobs.writeback` (in `/workspace/life-cli`)

#### `plan_writeback()`

Pure read-only operation over filesystem (+ optional sqlite validation).

**Inputs:**
- `vault_root` (e.g., `~/clinical-vault/views`)
- `plan_path` (e.g., `~/.life/writeback/plan.json`)
- `glob_pattern` - which files to scan (default: `**/*.md`)
- `db_path` (optional) - for baseline validation (e.g., `~/clinical-vault/local.db`)

**Algorithm:**

```python
EPSILON = 2.0  # seconds - covers filesystem resolution + processing latency

def plan_writeback(
    vault_root: str,
    plan_path: str,
    glob_pattern: str = "**/*.md",
    db_path: str | None = None,  # Optional: for baseline validation
) -> dict:
```

1. Glob for markdown files under `vault_root` (e.g., `**/*.md` or specific patterns like `**/session-note.md`)
2. For each file:
   - Try to parse YAML frontmatter
   - On parse error or no frontmatter → skip
   - Check required frontmatter keys: `entity`, `record_id`, `projected_at`
   - If missing → skip, record in `errors`
3. For each file with valid frontmatter:
   - Parse `projected_at`: `datetime.fromisoformat(frontmatter["projected_at"]).timestamp()`
   - Get file mtime: `os.path.getmtime(path)`
   - If `file_mtime > projected_at_ts + EPSILON` → mark as changed
4. For each changed file:
   - (Optional) Validate `record_id` exists in sqlite baseline → if not, skip with error
   - Build a write operation:
     - `entity` from frontmatter
     - `id` = `frontmatter["record_id"]`
     - `patch` = `build_patch(frontmatter)` using field mapping
5. Write plan to JSON file at `plan_path`
6. Return summary

**Source of truth: Frontmatter**

Frontmatter is the canonical source for file identity and writeback.

**Current frontmatter (existing):**
```yaml
---
source_type: clinical_document
idem_key: dataverse:dataverse-clinic:session:c78067ad-...#session_note
document_id: c78067ad-df10-f011-998a-002248b0cb29-note
session_id: c78067ad-df10-f011-998a-002248b0cb29
client_id: 20ed1dc4-57e3-ef11-be21-6045bd5d7bd7
doc_type: soap-note
---
```

**Updated frontmatter (add `entity`, `record_id`, `projected_at`):**
```yaml
---
source_type: clinical_document
entity: crf_sessions                              # NEW: Dataverse entity name
record_id: c78067ad-df10-f011-998a-002248b0cb29   # NEW: generic GUID for writeback
record_id_field: session_id                       # NEW: which field this came from (for context)
projected_at: 2025-12-09T16:00:00+00:00           # NEW: when this file was last projected
idem_key: dataverse:dataverse-clinic:session:c78067ad-...#session_note
document_id: c78067ad-df10-f011-998a-002248b0cb29-note
session_id: c78067ad-df10-f011-998a-002248b0cb29  # Keep original field name
client_id: 20ed1dc4-57e3-ef11-be21-6045bd5d7bd7
doc_type: soap-note
# User-editable fields below:
title: "Session 1 - Initial Assessment"
status: completed
---
```

- `entity`: Dataverse entity to PATCH
- `record_id`: generic GUID - writeback uses this
- `record_id_field`: documents which source field this came from (e.g., `session_id`, `document_id`)
- Original field (`session_id`) is preserved for human readability and debugging

**Required fields for writeback:**
- `entity`: Dataverse entity name (e.g., `crf_sessions`, `crf_documents`)
- `record_id`: Dataverse GUID - the record to PATCH
- `projected_at`: ISO timestamp - for change detection

**Why frontmatter, not path or sqlite:**
- Path is derived, lossy, and unstable (names change, folder conventions change)
- Frontmatter travels with the file - move/rename it, metadata stays intact
- This is the standard pattern in static sites, Obsidian, and note systems

**Change detection:**
- Compare `file_mtime > frontmatter["projected_at"] + epsilon`
- No need for `projected_files` table - the frontmatter has everything

**Validation (optional safety check):**
- If `db_path` is provided, verify `record_id` exists in sqlite baseline
- If frontmatter and sqlite disagree (record_id not found in baseline), **frontmatter wins for intent** - skip with error "record_id not found in baseline"
- This catches corrupted/mangled IDs but doesn't block writeback if sqlite is unavailable

**Field Mapping (isolated):**

```python
FRONTMATTER_TO_DV = {
    "title": "crf_title",
    "datetime": "crf_starttime",
    "status": "crf_status",
    # Add more as needed
}

def build_session_patch(frontmatter: dict) -> dict:
    """Build Dataverse patch payload from frontmatter."""
    return {
        dv_field: frontmatter[fm_field]
        for fm_field, dv_field in FRONTMATTER_TO_DV.items()
        if fm_field in frontmatter and frontmatter[fm_field] is not None
    }
```

**Return value:**

```python
{
    "files_scanned": 42,
    "files_changed": 3,
    "files_skipped": 2,
    "errors": [
        {"path": "John D/sessions/session-1/session-note.md", "reason": "Invalid YAML frontmatter"},
        {"path": "Jane S/sessions/session-2/session-note.md", "reason": "Missing required key: session_id"}
    ],
    "plan_path": "/home/user/.life/writeback/session_plan.json"
}
```

#### Plan File Format

The plan file is JSON with a versioned envelope:

```json
{
  "version": 1,
  "generated_at": "2025-12-09T16:10:00+00:00",
  "vault_root": "~/clinical-vault/views",
  "operations": [
    {
      "entity": "crf_sessions",
      "id": "abc-123-guid",
      "source_path": "John D/sessions/session-1/session-note.md",
      "patch": {
        "crf_title": "Session 1 - Initial Assessment",
        "crf_starttime": "2025-01-15T10:00:00Z"
      }
    }
  ]
}
```

- `version`: plan format version (currently `1`)
- `generated_at`: when the plan was created
- `vault_root`: where files were scanned (for debugging)
- `operations`: list of Dataverse PATCH operations
  - `entity`: from frontmatter
  - `id`: from frontmatter `record_id`
  - `source_path`: relative path (for debugging/logging only)
  - `patch`: field mapping result

---

#### `apply_writeback()`

Stateless except for Dataverse API calls.

**Inputs:**
- `plan_path` (default: `~/.life/writeback/plan.json`)
- `account` - authctl account name for Dataverse

**Algorithm:**

```python
def apply_writeback(
    account: str,
    plan_path: str = "~/.life/writeback/plan.json",
) -> dict:
```

1. Load the plan JSON file
2. Validate version (currently only `1` supported)
3. If `plan["operations"]` is empty, return early:
   ```python
   if not plan["operations"]:
       return {"operations": 0, "succeeded": 0, "failed": 0, "errors": []}
   ```
4. Create `DataverseClient.from_authctl(account)`
5. For each operation:
   - `client.patch(operation["entity"], operation["id"], operation["patch"])`
   - Catch exceptions, record failure, continue to next
6. Return summary

**Return value:**

```python
{
    "operations": 3,
    "succeeded": 2,
    "failed": 1,
    "errors": [
        {"id": "abc-123", "source_path": "...", "reason": "404 Not Found"}
    ]
}
```

---

### Step 3: Job YAML Definitions

**`examples/jobs/writeback.yaml`:**

```yaml
jobs:
  writeback_plan:
    description: "Scan vault and build writeback plan for changed files"
    steps:
      - name: plan
        call: life_jobs.writeback.plan_writeback
        args:
          vault_root: ~/clinical-vault/views
          plan_path: ~/.life/writeback/plan.json
          glob_pattern: "**/*.md"
          db_path: ~/clinical-vault/local.db  # Optional: for baseline validation

  writeback_apply:
    description: "Apply writeback plan to Dataverse"
    steps:
      - name: apply
        call: life_jobs.writeback.apply_writeback
        args:
          account: lifeos
          plan_path: ~/.life/writeback/plan.json
```

**Note:** `db_path` is optional - only needed if you want to validate `record_id` against the sqlite baseline.

---

### Step 4: Write unit tests for lorchestra and life-cli

**For lorchestra (`test_projection_processor.py`):**
- `test_sync_sqlite_adds_projected_at_column` - verify column exists after sync
- `test_sync_sqlite_projected_at_is_valid_iso_timestamp` - can parse with `fromisoformat()`
- `test_sync_sqlite_projected_at_same_for_all_rows` - all rows get identical timestamp
- `test_sync_sqlite_handles_empty_results` - no crash when BQ returns 0 rows
- `test_file_projection_injects_projected_at` - `_projected_at` variable available for frontmatter

**For life-cli (`test_writeback.py`):**
- `test_plan_writeback_detects_changed_files` - mtime > projected_at + epsilon
- `test_plan_writeback_skips_unchanged_files` - mtime <= projected_at + epsilon
- `test_plan_writeback_skips_no_frontmatter` - files without frontmatter are skipped
- `test_plan_writeback_skips_invalid_frontmatter` - records error, doesn't crash
- `test_plan_writeback_skips_missing_required_keys` - entity, record_id, projected_at required
- `test_plan_writeback_writes_plan_json` - correct envelope format with version
- `test_plan_writeback_uses_field_mapping` - FRONTMATTER_TO_DV applied correctly
- `test_plan_writeback_uses_entity_and_record_id_from_frontmatter` - ID comes from frontmatter
- `test_apply_writeback_calls_dataverse_patch` - mocked API call with correct args
- `test_apply_writeback_handles_failures` - partial success, continues on error
- `test_apply_writeback_validates_plan_version` - rejects unknown versions
- `test_apply_writeback_empty_operations_returns_early` - no client created when nothing to do

---

### Step 5: Validation

```bash
cd /workspace/lorchestra && pytest tests/test_projection_processor.py -v
cd /workspace/life-cli && pytest tests/test_writeback.py -v
ruff check .
```

## Models & Tools

**Tools:** bash, pytest, ruff

**Models:** (to be filled by defaults)

## Repository

**Branch:** `feat/projection-writeback`

**Merge Strategy:** squash