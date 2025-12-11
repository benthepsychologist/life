# Contributing to Life-CLI

Thank you for your interest in contributing to Life-CLI!

## Development Setup

### Prerequisites

- Python 3.8 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Git

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/benthepsychologist/life.git
cd life

# Create virtual environment
uv venv
# Or: python -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode with dev dependencies
uv pip install -e ".[dev]"
# Or: pip install -e ".[dev]"
```

### Running the CLI

After installation, you can run the CLI from anywhere:

```bash
life --help
life --version
```

Changes to the source code will be reflected immediately (editable install).

## Project Structure

```
life/
├── src/
│   └── life/
│       ├── __init__.py          # Package init, version info
│       ├── cli.py               # Main CLI entry point, global options
│       ├── config.py            # YAML config loading
│       ├── state.py             # State management (Step 3)
│       ├── runner.py            # Command execution (Step 3-4)
│       ├── utils.py             # Helper utilities (Step 4)
│       └── commands/
│           ├── __init__.py
│           ├── sync.py          # Sync subcommand
│           ├── merge.py         # Merge subcommand
│           ├── process.py       # Process subcommand
│           └── status.py        # Status subcommand
├── tests/                       # Test suite (to be added)
├── examples/                    # Example configs
├── docs/                        # Additional documentation
├── .specwright/                 # Specwright AIP files
├── pyproject.toml              # Package configuration
├── README.md                    # User documentation
└── CONTRIBUTING.md             # This file
```

## Development Workflow

### Making Changes

1. Create a new branch:
   ```bash
   git checkout -b feat/your-feature-name
   ```

2. Make your changes to the code

3. Test your changes:
   ```bash
   # Install your changes
   uv pip install -e .

   # Test manually
   life --help
   life --config test-config.yml sync test-task

   # Run tests (when available)
   pytest
   ```

4. Commit your changes:
   ```bash
   git add .
   git commit -m "Add feature: description"
   ```

### Code Style

We use `ruff` for linting:

```bash
# Check code style
ruff check .

# Auto-fix issues
ruff check --fix .
```

Code style guidelines:
- Line length: 100 characters
- Follow PEP 8
- Use type hints where beneficial
- Add docstrings for public functions/classes

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=life --cov-report=html

# Run specific test
pytest tests/test_config.py
```

### Creating Test Configs

When testing, create config files in the project root:

```bash
# Create a test config
cat > test-config.yml <<EOF
workspace: ~/test-workspace

sync:
  test-task:
    command: echo "Test command"
    output: ~/test-output.json
EOF

# Test with it
life --config test-config.yml --dry-run sync test-task
```

## Implementation Steps (Specwright AIP)

Life-CLI is being built following a 5-step Agentic Implementation Plan (AIP):

- **Step 1 ✅**: Project scaffolding (LICENSE, pyproject.toml, structure)
- **Step 2 ✅**: Core CLI framework (typer, config loader, subcommands)
- **Step 3 🚧**: State management & incremental sync
- **Step 4 ⏳**: Multi-command & workflow support
- **Step 5 ⏳**: Documentation & examples

See [.specwright/specs/life-initial-spec.md](.specwright/specs/life-initial-spec.md) for details.

When contributing, check which step you're working on and follow the spec's guidance.

## Key Abstractions

### Config Loading (`config.py`)

Loads YAML config from `~/life.yml`, `./life.yml`, or custom path:

```python
from life.config import load_config

config = load_config()  # Uses defaults
config = load_config("/path/to/config.yml")  # Custom path
```

### Command Modules (`commands/*.py`)

Each subcommand is a typer app that:
1. Receives context from parent CLI (`ctx.obj`)
2. Validates task exists in config
3. Executes command or shows dry-run preview

Example structure:
```python
import typer

app = typer.Typer(help="Command description")

@app.callback(invoke_without_command=True)
def callback(ctx: typer.Context, task: str = typer.Argument(None)):
    config = ctx.obj.get("config", {})
    dry_run = ctx.obj.get("dry_run", False)
    # ... implementation
```

### State Management (`state.py` - Step 3)

Tracks incremental sync state:
- Last sync timestamps
- High-water marks for pagination
- Per-task state in JSON file

### Command Runner (`runner.py` - Step 3-4)

Executes shell commands with:
- Variable substitution
- Output redirection
- Error handling
- Logging

## Adding a New Feature

Example: Adding a new subcommand `validate`

1. Create `src/life/commands/validate.py`:
   ```python
   import typer

   app = typer.Typer(help="Validate data files")

   @app.callback(invoke_without_command=True)
   def validate_callback(ctx: typer.Context, task: str = typer.Argument(None)):
       # Implementation here
       pass
   ```

2. Register in `src/life/cli.py`:
   ```python
   from life.commands import validate

   app.add_typer(validate.app, name="validate")
   ```

3. Add config schema to README:
   ```yaml
   validate:
     task_name:
       command: "validation command"
       schema: ~/path/to/schema.json
   ```

4. Test it:
   ```bash
   life validate --help
   life --config test.yml validate my-task
   ```

## Commit Message Guidelines

Use conventional commits:

- `feat: Add new feature`
- `fix: Fix bug in config loader`
- `docs: Update README with examples`
- `refactor: Restructure command modules`
- `test: Add tests for state management`
- `chore: Update dependencies`

## Pull Request Process

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Update documentation (README, docstrings)
6. Submit PR with clear description

PR template:
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
How did you test this?

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] Tests added/updated
```

## Questions?

- Open an issue for bugs or feature requests
- Check existing issues before creating new ones
- Tag with appropriate labels (bug, feature, question)

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
