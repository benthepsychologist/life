# Life-CLI Architecture

## Design Philosophy

Life-CLI follows three core principles:

### 1. Orchestration, Not Implementation

Life-CLI **does not implement business logic**. It orchestrates tools that do.

```
❌ Bad: Life-CLI has built-in Dataverse client
✅ Good: Life-CLI calls your `dv` CLI tool
```

This keeps the codebase small, focused, and lets you use best-in-class tools for each domain.

### 2. Unix Philosophy: Do One Thing Well

Each specialized CLI tool does one thing:
- `dv`: Query Dataverse
- `msg`: Handle email operations
- `cal`: Sync calendar
- `gws`: Google Sheets operations
- `assess`: Score assessments

Life-CLI's "one thing" is **orchestrating these tools** with:
- YAML configuration
- State tracking
- Workflow sequencing
- Variable injection

### 3. Data Over Code

Workflows are **data** (YAML), not code (Python/Bash). This makes them:
- Easy to read and modify
- Version controllable
- Sharable across projects
- Editable without programming knowledge

## Architecture Layers

```
┌─────────────────────────────────────────────────┐
│  User Interface                                 │
│  - CLI commands (life sync, life merge, etc.)  │
│  - Global options (--dry-run, --verbose)       │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│  Configuration Layer (config.py)                │
│  - Load YAML config                             │
│  - Expand paths (~/, env vars)                  │
│  - Validate structure                           │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│  State Management (state.py) - Step 3           │
│  - Track last sync times                        │
│  - High-water marks for incremental syncs       │
│  - Per-task state persistence                   │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│  Command Runner (runner.py) - Step 3-4          │
│  - Variable substitution                        │
│  - Execute shell commands                       │
│  - Handle errors and logging                    │
│  - Support multi-command sequences              │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│  External CLI Tools (user's tools)              │
│  - dv, msg, cal, gws, custom CLIs               │
│  - Each handles its own domain                  │
└─────────────────────────────────────────────────┘
```

## Key Components

### CLI Entry Point (`cli.py`)

**Responsibility**: Parse arguments, load config, dispatch to subcommands

```python
# Main app with global options
@app.callback()
def main_callback(
    ctx: typer.Context,
    config_path: Optional[str] = typer.Option(None, "--config"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    verbose: bool = typer.Option(False, "--verbose"),
):
    # Load config, setup logging, pass to subcommands
    config = load_config(config_path)
    ctx.obj = {"config": config, "dry_run": dry_run, "verbose": verbose}
```

**Why this design**: Typer's context system lets us load config once and share it with all subcommands.

### Config Loader (`config.py`)

**Responsibility**: Load and validate YAML configuration

```python
def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    # Try ~/life.yml, ./life.yml, or custom path
    # Expand paths, validate YAML
    # Return dict
```

**Why this design**: Simple function, no complex class hierarchy. YAML maps directly to Python dicts.

### Subcommands (`commands/*.py`)

**Responsibility**: Handle domain-specific command logic

Each subcommand:
1. Receives context from parent (`ctx.obj`)
2. Looks up task in config
3. Validates task exists
4. Executes or shows dry-run

```python
# commands/sync.py
@app.callback(invoke_without_command=True)
def sync_callback(ctx: typer.Context, task: str = typer.Argument(None)):
    config = ctx.obj.get("config", {})
    dry_run = ctx.obj.get("dry_run", False)

    task_config = config["sync"][task]
    # Execute task...
```

**Why this design**: Each subcommand is independent, easy to understand, easy to extend.

**Note on `today` command**: The `today` subcommand is conceptually different from data pipeline commands (`sync`, `merge`, `process`, `status`). While those commands orchestrate external CLI tools, `today` is a built-in utility for daily note management. It's included for convenience and workflow integration but doesn't follow the pure orchestration pattern. It has sensible defaults and works without a config file, making it more like a standalone helper tool that happens to share the `life` command namespace.

### State Management (`state.py` - Step 3)

**Responsibility**: Track incremental sync state

```python
class StateManager:
    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.state = self._load()

    def get_last_sync(self, task_name: str, field: str) -> Optional[str]:
        # Return high-water mark for incremental sync

    def update_last_sync(self, task_name: str, field: str, value: str):
        # Update and persist state
```

**Why this design**: Simple JSON file per state file path. No database overhead. Human-readable for debugging.

### Command Runner (`runner.py` - Step 3-4)

**Responsibility**: Execute shell commands with variable substitution

```python
def run_command(
    command: str,
    variables: Dict[str, str],
    dry_run: bool = False,
) -> subprocess.CompletedProcess:
    # Substitute variables
    # Execute shell command
    # Handle errors
    # Return result
```

**Why this design**: Thin wrapper around subprocess. Variable substitution happens before execution, making it debuggable.

## Data Flow Example

User runs: `life sync contacts`

1. **CLI Entry** (`cli.py`):
   - Parse args: subcommand=`sync`, task=`contacts`
   - Load config from `~/life.yml`
   - Set dry_run=False, verbose=False
   - Pass config to sync subcommand

2. **Sync Subcommand** (`commands/sync.py`):
   - Receive `ctx.obj = {"config": {...}, "dry_run": False}`
   - Look up `config["sync"]["contacts"]`
   - Extract command, output, state_file, incremental_field

3. **State Manager** (`state.py`):
   - Check last sync time for "contacts.modifiedon"
   - Return "2025-11-09T10:30:00Z" (or None if first sync)

4. **Command Runner** (`runner.py`):
   - Build variables: `{extra_args}` = `--since 2025-11-09T10:30:00Z`
   - Substitute: `dv query ... {extra_args}` → `dv query ... --since 2025-11-09T10:30:00Z`
   - Execute command
   - Capture output

5. **State Manager** (`state.py`):
   - Update last sync time to current timestamp
   - Write state file

6. **CLI Entry** (`cli.py`):
   - Exit with success code

## Design Decisions

### Why YAML over JSON?

- **Human-readable**: Comments, multi-line strings
- **Widely used**: Familiar to data engineers
- **Tooling**: Syntax highlighting, validation

### Why subprocess over Python imports?

- **Tool agnostic**: Works with ANY CLI tool (Python, Go, Rust, Bash)
- **Isolation**: Tool crashes don't crash life-cli
- **Versioning**: Each tool has its own version, dependencies
- **Simplicity**: No need to maintain Python bindings for every API

### Why JSON state files over SQLite?

- **Simple**: No schema migrations
- **Portable**: Easy to backup, version control
- **Debuggable**: Human-readable
- **Lightweight**: No database driver dependencies

For 99% of personal workflows, JSON is sufficient. If you have 1000+ tasks, you probably need Airflow.

### Why typer over argparse/click?

- **Modern**: Type hints, automatic help generation
- **Composable**: Easy to add subcommands
- **Great UX**: Beautiful help messages, auto-completion
- **Less boilerplate**: `typer.Argument()` vs argparse ceremony

## Extensibility Points

### Adding New Subcommands

1. Create `src/life/commands/new_command.py`
2. Define typer app
3. Register in `cli.py`: `app.add_typer(new_command.app, name="new")`

### Adding New Variable Types

1. Update `runner.py` variable substitution logic
2. Document in README config reference

### Adding New State Backends

1. Create new state manager class (inherit from base)
2. Use dependency injection in commands

## Non-Goals

Life-CLI intentionally **does not**:

- ❌ Run a web server (use Airflow if you need this)
- ❌ Implement scheduling (use cron, systemd timers, or your editor)
- ❌ Handle distributed execution (single machine workflows)
- ❌ Provide a GUI (CLI-first by design)
- ❌ Implement specific API clients (use specialized tools)
- ❌ Replace your tools (orchestrate them)

## Comparison with Alternatives

### vs Bash Scripts

| Feature | Bash Scripts | Life-CLI |
|---------|--------------|----------|
| Structure | None | YAML config |
| State tracking | Manual | Built-in |
| Variable injection | `$VAR` | `{var}` with validation |
| Error handling | Manual | Automatic |
| Dry-run | Manual `echo` | Built-in `--dry-run` |
| Maintainability | Low (grows into spaghetti) | High (declarative) |

### vs Make/Taskfile

| Feature | Make/Taskfile | Life-CLI |
|---------|---------------|----------|
| Incremental state | File timestamps only | Custom high-water marks |
| Data pipelines | Not designed for it | Core use case |
| Config format | Makefile/Justfile | YAML |
| State persistence | None | JSON state files |

### vs Airflow

| Feature | Airflow | Life-CLI |
|---------|---------|----------|
| Scheduler | Built-in | None (use cron/editor) |
| Web UI | Yes | No |
| Complexity | High | Low |
| Setup time | Hours | Minutes |
| Best for | Team workflows, 100+ tasks | Personal workflows, 5-20 tasks |

### vs Meltano

| Feature | Meltano | Life-CLI |
|---------|---------|----------|
| Protocol | Singer taps/targets | Any CLI tool |
| Focus | Data warehouse ELT | General orchestration |
| Tool support | Singer ecosystem | Anything with a CLI |
| State tracking | Built-in | Built-in |

## Current Implementation Status

### Phase 1: Complete (124 tests passing)
- ✅ Config management with hierarchical loading
- ✅ State tracking for incremental syncs
- ✅ Variable substitution and command execution
- ✅ Comprehensive test coverage

### Production Environment: Temporary Tools Monorepo

While life-cli's orchestration layer is being finalized, production workflows use a temporary setup:

**Directory Structure:**
```
~/life-cockpit/           # Working directory
├── activate.sh           # Environment setup script

~/tools/                  # Temporary monorepo (15+ CLI tools)
├── .venv/               # Unified virtual environment
├── messages/            # Gmail client (msg)
├── gws/                 # Google Workspace (gws)
├── dataverse-sync/      # Dataverse client (dv)
├── recipes/             # Automation scripts
│   └── session_summary.sh  # Production workflow
└── [other tools]/

~/phi-data/              # Protected Health Information
├── client-registry.json # Client folder registry
└── [temporary files]    # PDF generation, etc.
```

**Tool Integration:**

All tools are accessible via PATH after sourcing `~/life-cockpit/activate.sh`:
```bash
export PATH="$HOME/tools/.venv/bin:$PATH"
export TOOLS_DIR="$HOME/tools"
export PYTHONPATH="$TOOLS_DIR:${PYTHONPATH:-}"
```

**Authentication Setup:**
- Gmail OAuth: `~/tools/messages/gmail_config.json` (3 configured accounts)
- Google Drive API: Integrated with `gws` tool
- Dataverse: CRM system integration via `dv` tool

**Production Workflow Example: Session Summary**

[`~/tools/recipes/session_summary.sh`](../tools/recipes/session_summary.sh) demonstrates end-to-end automation:

1. **Data Fetch** - Query Dataverse for session data by client email
2. **Contact Lookup** - Resolve client name, folder ID, contactid from Dataverse
3. **PDF Generation** - Create `Firstname L - Session Summary - YYYY-MM-DD.pdf` in `~/phi-data/`
4. **Email** - Send via Gmail API (drben@benthepsychologist.com) with PDF attachment
5. **Drive Upload** - Convert HTML to Google Doc in client's shared folder
6. **Registry** - Track folder IDs with contactid for future lookups
7. **Cleanup** - Remove PDF from `~/phi-data/` after successful send

This workflow is fully operational and used in production daily.

**Why This Temporary Setup:**

1. **Immediate Productivity** - Don't wait for final architecture decisions
2. **Proof of Concept** - Validate workflows before orchestration layer integration
3. **PHI Segregation** - Clear separation between code and sensitive data
4. **Future Refactoring** - Once data pipeline architecture is finalized, tools will be properly modularized

## Future Considerations

As Life-CLI evolves, we may add:

- **Dependency graphs** (DAG execution): `depends_on: [task1, task2]`
- **Parallel execution**: Run independent tasks concurrently
- **Retry logic**: `retry: 3` with exponential backoff
- **Hooks**: Pre/post command execution callbacks
- **Templates**: Reusable task definitions
- **Tool Modularization**: Migrate from monorepo to individual packages

But we'll only add these if they maintain the core philosophy: **lightweight orchestration for personal CLI workflows**.

## Contributing to Architecture

When proposing architectural changes:

1. **Check the philosophy**: Does it align with "orchestration, not implementation"?
2. **Consider alternatives**: Could this be a separate tool that life-cli calls?
3. **Measure complexity**: Does this make the codebase significantly more complex?
4. **Evaluate scope**: Is this a feature most users need, or edge case?

Open an issue with:
- Problem statement
- Proposed solution
- Alternatives considered
- Complexity analysis

---

**Remember**: Life-CLI's strength is its simplicity. When in doubt, keep it simple.
