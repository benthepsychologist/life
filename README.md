# Life-CLI

**Lightweight, stateful, CLI-first orchestrator for personal data pipelines**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

Life-CLI is a tool for orchestrating personal data workflows without the overhead of enterprise solutions like Airflow. It wraps your specialized CLI tools (data sync, transformations, APIs) with YAML configuration, incremental state tracking, and workflow management.

## Why Life-CLI?

**The Problem:** You have multiple CLI tools for different data tasks (syncing APIs, transforming data, updating spreadsheets). You've outgrown bash scripts but don't need a full orchestration platform.

**The Gap:**
- **Bash scripts**: No structure, no state tracking, grows unmaintainable
- **Make/Taskfile**: No incremental state, not designed for data pipelines
- **Airflow/Prefect**: Scheduler-first, web UI overhead, too heavyweight
- **Meltano**: Singer-protocol only, not generalized for any CLI tool

**Life-CLI fills this gap:** Lightweight orchestration for ANY CLI tool, with stateful syncing, triggered on-demand (e.g., from your editor).

## Features

- 🎯 **CLI-first**: Trigger workflows from command line or editor (Neovim, VS Code)
- 📝 **YAML configuration**: Declarative workflow definitions
- 🔄 **Incremental syncing**: Track state between runs, avoid full refreshes
- 🧩 **Tool-agnostic**: Orchestrate any CLI tool, not just specific protocols
- 🏃 **On-demand execution**: No scheduler required, run when you need it
- 🔍 **Dry-run mode**: Preview what will execute before running
- 📦 **Lightweight**: Minimal dependencies (typer, pyyaml)

## Installation

### Using uv (recommended)

```bash
# Clone the repository
git clone https://github.com/benthepsychologist/life.git
cd life

# Create virtual environment and install
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

### Using pip

```bash
git clone https://github.com/benthepsychologist/life.git
cd life
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Verify installation

```bash
life --version
# Output: life version 0.1.0
```

### Shell Completion (Optional)

Life-CLI supports shell completion for bash, zsh, and fish:

```bash
# For bash
life --install-completion bash
source ~/.bashrc

# For zsh
life --install-completion zsh
source ~/.zshrc

# For fish
life --install-completion fish
```

After installation, you can use Tab to autocomplete commands and options.

## Quick Start

### 1. Initialize a project

```bash
# Create a new project (creates .life/config.yml)
cd ~/my-project
life init

# Or specify a custom workspace
life init --workspace ~/my-data
```

This creates `.life/config.yml` with sensible defaults for your project.

### 2. Configure your tasks

Edit `.life/config.yml` (or create `~/life.yml` or `./life.yml` for global config):

```yaml
workspace: ~/my-data-workspace

sync:
  contacts:
    command: |
      my-crm-tool export contacts
        --format json
        --output {output}
    output: ~/my-data-workspace/contacts.json
    description: Sync contacts from CRM

  calendar:
    command: |
      my-calendar-tool export
        --from {from_date}
        --to {to_date}
        --output {output}
    output: ~/my-data-workspace/calendar.json
    date_range: 7d

merge:
  reports:
    contacts_calendar:
      command: |
        jq -s '.[0] + .[1]' {contacts_file} {calendar_file}
      contacts_file: ~/my-data-workspace/contacts.json
      calendar_file: ~/my-data-workspace/calendar.json
      output: ~/my-data-workspace/merged_report.json

process:
  generate_report:
    command: |
      my-report-tool create
        --input {input}
        --output {output}
    input: ~/my-data-workspace/merged_report.json
    output: ~/my-data-workspace/final_report.pdf

status:
  check_pipeline:
    command: |
      echo "Contacts: $(jq length ~/my-data-workspace/contacts.json)"
      echo "Events: $(jq length ~/my-data-workspace/calendar.json)"
```

### 3. Run commands

```bash
# Sync data from external sources
life sync contacts

# Merge datasets
life merge reports contacts_calendar

# Process data
life process generate_report

# Check status
life status check_pipeline

# Preview without executing
life --dry-run sync contacts

# Use custom config location
life --config /path/to/config.yml sync contacts

# Verbose logging
life --verbose sync contacts
```

## Commands

### `life init`
Initialize a new Life-CLI project. Creates `.life/config.yml` with default configuration.

```bash
# Initialize in current directory
life init

# Specify custom workspace
life init --workspace ~/my-data

# Force overwrite existing config
life init --force

# Preview what would be created
life --dry-run init
```

### `life sync <task>`
Execute data synchronization tasks. Supports incremental syncing with state tracking.

### `life merge <category> <task>`
Merge and transform datasets using nested task organization.

### `life process <task>`
Process data through transformation pipelines.

### `life status <task>`
Run status checks and generate reports.

### `life today`
Create and manage daily operational notes with template support and LLM-powered reflection.

```bash
# Create today's daily note
life today

# Create note for specific date
life today create 2025-11-15

# Ask LLM about today's note (requires 'llm' CLI)
life today prompt "What were my main accomplishments?"

# Include previous 3 days as context
life today prompt "What patterns do you see?" --context 3
```

### `life run <job_id>`
Execute a job defined in YAML files. Jobs are sequences of steps that call Python functions.

```bash
# Run a job
life run query_contacts

# Dry-run mode (preview without executing)
life --dry-run run query_contacts

# Pass variables to a job
life run --var recipient=user@example.com send_test_email

# Verbose output
life --verbose run query_contacts
```

### `life jobs list`
List all available jobs from YAML files in the jobs directory.

```bash
life jobs list

# Show YAML parse errors if any
life jobs list --errors
```

### `life jobs show <job_id>`
Display the full definition of a job.

```bash
life jobs show query_contacts
```

### Global Options
- `--config PATH` / `-c PATH`: Path to config file (default: `~/life.yml` or `./life.yml`)
- `--dry-run`: Show what would be executed without running commands
- `--verbose` / `-v`: Enable verbose logging with timestamps

## Job Runner

The job runner provides a way to execute Python functions directly from YAML definitions, without subprocess overhead.

### Setup

1. Create a jobs directory:
```bash
mkdir -p ~/.life/jobs
```

2. Add job definitions (YAML files):
```yaml
# ~/.life/jobs/dataverse.yaml
jobs:
  query_contacts:
    description: "Query contacts from Dataverse"
    steps:
      - name: query
        call: life_jobs.dataverse.query
        args:
          account: lifeos
          entity: contacts
          select: [firstname, lastname, emailaddress1]
          filter: "statecode eq 0"
          output: ~/data/contacts.json
```

3. Run jobs:
```bash
life run query_contacts
```

### Job Definition Format

Jobs are YAML files with sequences of steps. Each step calls a Python function via `call:`:

```yaml
jobs:
  my_workflow:
    description: "Multi-step workflow"
    steps:
      - name: step1
        call: life_jobs.dataverse.query
        args:
          account: myaccount
          entity: contacts
          output: ~/data/contacts.json

      - name: step2
        call: life_jobs.graph.send_mail
        args:
          account: personal
          to: ["{recipient}"]
          subject: "Data ready"
          body: "Contacts synced successfully"
```

### Variable Substitution

Use `{variable}` placeholders in args, pass values with `--var`:

```bash
life run my_job --var recipient=user@example.com --var date=2025-01-01
```

### Available Step Functions

**Dataverse (`life_jobs.dataverse`):**
- `query` - Query entities and write to JSON
- `get_single` - Fetch single record by ID
- `create` - Create new record
- `update` - Update existing record
- `delete` - Delete record

**Graph API (`life_jobs.graph`):**
- `get_messages` - Fetch emails
- `send_mail` - Send email
- `me` - Get user profile
- `get_calendar_events` - Fetch calendar events
- `get_files` - List OneDrive files

**LLM Generate (`life_jobs.generate`):** *(requires `pip install 'life[llm]'`)*
- `prompt` - Execute single LLM prompt with optional system prompt
- `prompt_with_context` - Execute prompt with JSON/text files as context
- `batch` - Process JSON array through LLM with retry, rate limiting, and error handling

**Shell (`life_jobs.shell`):**
- `run` - Execute shell command (transitional, prefer Python functions)

### Event Logging

All job executions are logged to `~/.life/events.jsonl` with correlation IDs for debugging.

## LLM Integration

Life-CLI supports native LLM processing via the `llm` library (by Simon Willison). This allows jobs to call LLM models directly without subprocess overhead.

### Installation

```bash
# Install with LLM support
pip install 'life[llm]'
```

### Example Job Definitions

```yaml
# ~/.life/jobs/generate.yaml
jobs:
  simple_prompt:
    description: "Simple LLM prompt"
    steps:
      - name: generate
        call: life_jobs.generate.prompt
        args:
          prompt: "{user_prompt}"
          model: gpt-4o-mini
          output: ~/output/response.md

  summarize_json:
    description: "Summarize JSON data with context"
    steps:
      - name: generate
        call: life_jobs.generate.prompt_with_context
        args:
          prompt: "Summarize the key points from this data."
          context_files: ["{input_file}"]
          system: "You are a helpful assistant."
          output: ~/output/summary.md

  batch_process:
    description: "Process items through LLM"
    steps:
      - name: batch
        call: life_jobs.generate.batch
        args:
          items_file: "{items}"
          prompt: "Analyze this item."
          output: ~/output/results.json
          rate_limit_rpm: 60
          max_retries: 3
```

### Usage

```bash
# Simple prompt
life run simple_prompt --var user_prompt="Explain quantum computing"

# Summarize a JSON file
life run summarize_json --var input_file=~/data/report.json

# Batch process items
life run batch_process --var items=~/data/items.json
```

### Production Safeguards

The `batch()` function includes:
- **Retry with backoff**: Automatic retry on transient failures (rate limits, timeouts)
- **Rate limiting**: Configurable requests-per-minute limit
- **Error handling**: Continue on failure or fail-fast mode
- **Token tracking**: Aggregated token usage across batch
- **Unique call_id**: UUIDv4 per invocation for debugging

### Configuration

Add to your config file:
```yaml
jobs:
  dir: ~/.life/jobs          # Job definitions directory
  event_log: ~/.life/events.jsonl  # Event log path
```

## Configuration

### Config File Locations

Life-CLI looks for configuration in this order (first found wins):

1. `./.life/config.yml` - Project-local (recommended, created by `life init`)
2. `./life.yml` - Legacy local config
3. `~/life.yml` - User global config
4. `--config PATH` - Custom path (overrides all)

**Best practice:** Use `life init` to create `.life/config.yml` in each project.

### Configuration Reference

### Sync Tasks

```yaml
sync:
  task_name:
    command: "cli-tool command with {variables}"
    output: ~/output/path.json
    incremental_field: modifiedon        # Field to track for incremental updates
    state_file: ~/.life-state.json       # Where to store sync state
    id_field: id                          # Unique identifier field
    description: "Human-readable description"
```

### Merge Tasks

```yaml
merge:
  category_name:
    task_name:
      command: "transformation command with {input_vars}"
      input_file: ~/path/to/input.json
      output: ~/path/to/output.json
      description: "What this merge does"
```

### Multi-Command Execution

```yaml
process:
  complex_task:
    commands:
      - "command one"
      - "command two"
      - "command three"
    output: ~/final/output.json
```

### Conditional Execution

Execute commands only when conditions are met:

```yaml
gen:
  session_note:
    commands:
      - "fetch_data.sh > {data_file}"
      - command: "process_data.sh {data_file}"
        condition:
          file_exists: "{data_file}"
          file_not_empty: "{data_file}"
    variables:
      data_file: "/tmp/data.json"
```

**Supported conditions:**
- `file_exists: path` - Check if file exists
- `file_not_empty: path` - Check if file exists and has content
- `json_has_field: {file: path, field: name}` - Check if JSON file contains a field

Multiple conditions must all pass for the command to execute.

### HITL (Human-in-the-Loop) Prompts

Pause workflows for user confirmation with optional preview:

```yaml
sync:
  import_data:
    commands:
      - "curl -o {temp_file} {api_url}"
      - prompt:
          message: "Import this data?"
          preview_file: "{temp_file}"
          preview_lines: 10
          type: confirm
      - command: "python import.py {temp_file}"
    variables:
      temp_file: "/tmp/data.json"
      api_url: "https://api.example.com/data"
```

**Prompt options:**
- `message` (required): Message to display to user
- `preview_file` (optional): File to show preview of
- `preview_lines` (optional): Number of lines to preview (default: 10)
- `type` (optional): "confirm" or "input" (default: confirm)

### Variable Substitution

Life-CLI supports these built-in variables:
- `{output}`: Replaced with the task's output path
- `{from_date}`, `{to_date}`: Calculated from `date_range` config
- `{extra_args}`: Injected for incremental syncs (Step 3 feature)
- Custom variables: Any field in the task config can be referenced

### Today Command Configuration

The `today` command works relative to your current directory or workspace:

**Default Behavior (no config):**
- Daily notes: `./notes/daily/YYYY-MM-DD.md`
- Template: `./notes/templates/daily-ops.md`

**With workspace defined:**
```yaml
workspace: ~/my-workspace

# Notes will be created in:
# ~/my-workspace/notes/daily/YYYY-MM-DD.md
```

**Explicit paths:**
```yaml
today:
  daily_dir: ~/my-notes/daily
  template_path: ~/my-notes/templates/daily.md
```

This makes `life today` work like Git - it operates on your current working directory or uses configured paths.

If template doesn't exist, a default template is created automatically with sections for:
- Focus
- Status Snapshot
- Tasks
- Reflection / "State of the Game"

**LLM Integration:** The `prompt` subcommand requires the [`llm` CLI](https://llm.datasette.io/):
```bash
pip install llm
```

## Development Status

**Current:** Phase 1 Complete - Core orchestration layer with 154 passing tests

**Roadmap:**
- ✅ Step 1: Project scaffolding (LICENSE, pyproject.toml, structure)
- ✅ Step 2: Core CLI framework (typer, config loader, subcommands)
- ✅ Step 3: State management & incremental sync (complete)
- ⏳ Step 4: Multi-command & workflow support
- ⏳ Step 5: Documentation & examples

See [.specwright/specs/life-initial-spec.md](.specwright/specs/life-initial-spec.md) for the full implementation plan.

### Current Working Environment

While life's orchestration layer is being completed, a full set of production-ready CLI tools is available in a temporary monorepo setup at `~/tools/`. This allows immediate productivity without waiting for final architecture decisions.

**Available Tools (15+ CLIs):**
- `msg` - Gmail client for email operations (configured with OAuth)
- `gws` - Google Workspace management (Drive, Sheets, Docs with folder registry)
- `dv` - Dataverse query and sync operations
- `cal`, `assess`, `mon`, `gen`, `rio`, `xl`, `fire`, `ingest` - Additional specialized tools

**Working Directory Setup:**

Work from `~/life-cockpit/` (not from the life repo):
```bash
# Activate environment to add all tools to PATH
source ~/life-cockpit/activate.sh

# All tools now available
msg --help        # Email operations
gws --help        # Google Drive/Docs management
dv --help         # Dataverse queries
bash ~/tools/recipes/session_summary.sh <email>  # Automated workflows
```

**Data Segregation:**
- Code/Tools: `~/tools/` (temporary monorepo)
- Protected Health Information: `~/phi-data/` (client registries, temp files)
- Orchestration config: `~/life-cockpit/` (working directory)

**Production Workflow Example:**

The session summary automation is fully operational:
1. Fetches session data from Dataverse by client email
2. Generates PDF summary with proper naming
3. Sends email via Gmail (drben@benthepsychologist.com) with PDF attachment
4. Uploads summary to client's Google Drive folder as Google Doc
5. Includes Drive folder link in email
6. Cleans up temporary files

This temporary setup will be refactored once life's orchestration capabilities mature and the data pipeline architecture is finalized.

## Architecture

Life-CLI follows the Unix philosophy: do one thing well. It orchestrates CLI tools, it doesn't replace them.

```
life:     Orchestration layer (workflows, state, sequencing)
│
├─ dv:        Your Dataverse CLI
├─ msg:       Your email CLI
├─ cal:       Your calendar CLI
├─ my-tool:   Your custom tool
└─ ...        Any CLI tool
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed design philosophy.

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup.

## Complete Example: Clinical Session Note Generation

Here's a real-world example combining conditional execution and HITL prompts:

```yaml
# ~/.life/config.yml or ~/life.yml
workspace: ~/life-cockpit

gen:
  session_note:
    description: "Generate SOAP note from latest session transcript"
    commands:
      # 1. Look up client by email using dv tool
      - command: "source ~/life-cockpit/activate.sh && dv find-contact --email {client_email} --json > {contact_file}"

      # 2. Pull latest session data
      - command: "source ~/life-cockpit/activate.sh && dv pull --client {client_email} --limit 1"

      # 3. Preview transcript and ask for confirmation
      - prompt:
          message: "Generate SOAP note for this session?"
          preview_file: "{transcript_file}"
          preview_lines: 15
          type: confirm

      # 4. Generate SOAP note (only if transcript exists)
      - command: |
          source ~/life-cockpit/activate.sh && \
          gen run {transcript_file} \
            --system {system_prompt} \
            --prompt {note_prompt} \
            --out {output_file}
        condition:
          file_exists: "{transcript_file}"
          file_not_empty: "{transcript_file}"

    variables:
      vault_dir: "~/vaults/clinic-vault"
      contact_file: "/tmp/contact_{client_email}.json"
      transcript_file: "{vault_dir}/clients/{client_email}/sessions/latest/transcript.md"
      output_file: "{vault_dir}/clients/{client_email}/sessions/latest/soap_note.md"
      system_prompt: "system_clinical"
      note_prompt: "soap_note"
```

**Usage:**
```bash
life gen session_note --variables client_email=patient@example.com
```

This workflow:
1. Looks up the client in Dataverse
2. Pulls their latest session with transcript
3. Shows a preview and asks for confirmation
4. Generates a SOAP note only if the transcript exists
5. All orchestrated through YAML - no Python code needed!

See [examples/session-note-config.yml](examples/session-note-config.yml) for more examples.

## Use Cases

Life-CLI was built for personal data management workflows:

- **Clinical practice**: Sync patient sessions, calendar, emails → merge → generate reports (see example above)
- **Research**: Fetch datasets from multiple APIs → transform → analyze
- **Personal analytics**: Aggregate data from various services → process → visualize
- **Content workflows**: Fetch sources → transform → publish

If you're orchestrating 5-10 specialized CLI tools in a personal workflow, life is for you.

## License

Apache License 2.0 - See [LICENSE](LICENSE) for details.

## Related Projects

- **Meltano**: ELT orchestration (Singer protocol, data warehouse focused)
- **Taskfile**: Simple task runner (no state tracking)
- **Airflow**: Enterprise workflow platform (scheduler, web UI, distributed)
- **dbt**: SQL transformation pipelines (database-centric)

Life-CLI sits between bash scripts and enterprise orchestrators, optimized for personal CLI tool workflows.

---

**Status**: Alpha (v0.1.0) - API may change as we implement remaining features
