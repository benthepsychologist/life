"""Daily note operations.

Implementation rules enforced here (Rule 8):
- Never print
- Never read global config or environment (except Path.expanduser)
- Always return simple dicts
- Side effects: file IO only
- External calls: llm Python library (NOT subprocess)

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

# I/O declaration for static analysis and auditing
__io__ = {
    "reads": ["template_path", "daily_dir/{date}.md", "daily_dir/{prev_dates}.md"],
    "writes": ["daily_dir/{date}.md"],
    "external": ["llm.prompt"],
}

# Default template content
DEFAULT_TEMPLATE = """# Daily Ops — {{date}}

## Focus


## Status Snapshot


## Tasks


## Reflection / "State of the Game"

"""


def create_note(
    date: str,
    template_path: str,
    daily_dir: str,
) -> Dict[str, Any]:
    """Create daily note from template.

    Reads: template_path
    Writes: daily_dir/{date}.md
    Idempotency: Fails if note already exists.

    Args:
        date: Date string in YYYY-MM-DD format
        template_path: Path to template file
        daily_dir: Directory for daily notes

    Returns:
        {path: str, created: bool, error: str|None}
    """
    # Validate date format
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return {
            "path": None,
            "created": False,
            "error": f"Invalid date format: {date}. Use YYYY-MM-DD",
        }

    daily_path = Path(daily_dir).expanduser()
    template = Path(template_path).expanduser()
    note_path = daily_path / f"{date}.md"

    # Check if already exists (idempotency)
    if note_path.exists():
        return {
            "path": str(note_path),
            "created": False,
            "error": f"Note already exists: {note_path}",
        }

    # Load or create template
    if template.exists():
        template_content = template.read_text()
    else:
        # Create default template
        template.parent.mkdir(parents=True, exist_ok=True)
        template.write_text(DEFAULT_TEMPLATE)
        template_content = DEFAULT_TEMPLATE

    # Populate template with date
    note_content = template_content.replace("{{date}}", date)

    # Create directory if needed
    daily_path.mkdir(parents=True, exist_ok=True)

    # Write note
    note_path.write_text(note_content)

    return {
        "path": str(note_path),
        "created": True,
        "error": None,
    }


def prompt_llm(
    note_path: str,
    question: str,
    context_days: int = 0,
) -> Dict[str, Any]:
    """Ask LLM about today's note.

    Reads: note_path (and previous N days if context_days > 0)
    Writes: Appends Q&A section to note_path
    External: llm Python library (NOT subprocess)

    Args:
        note_path: Path to today's note
        question: Question to ask the LLM
        context_days: Number of previous days to include as context

    Returns:
        {response: str, appended_to: str, error: str|None}
    """
    import llm

    path = Path(note_path).expanduser()

    if not path.exists():
        return {
            "response": None,
            "appended_to": None,
            "error": f"Note not found: {note_path}",
        }

    # Read today's note
    note_content = path.read_text()

    # Extract date from filename for context lookup
    date_str = path.stem  # e.g., "2025-01-15"
    try:
        today = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        today = datetime.now()

    # Build context from previous days
    context_notes = []
    if context_days > 0:
        daily_dir = path.parent
        for i in range(1, context_days + 1):
            prev_date = today - timedelta(days=i)
            prev_date_str = prev_date.strftime("%Y-%m-%d")
            prev_path = daily_dir / f"{prev_date_str}.md"

            if prev_path.exists():
                prev_content = prev_path.read_text()
                context_notes.append(f"# {prev_date_str}\n{prev_content}")

    # Build full prompt
    context_section = ""
    if context_notes:
        context_section = (
            "\n# Previous Days\n" + "\n\n".join(reversed(context_notes)) + "\n\n"
        )

    full_prompt = f"""You are helping review daily operations notes.

{context_section}# Today's Note ({date_str})
{note_content}

# Question
{question}

Provide a concise, actionable response."""

    # Call LLM using Python library
    try:
        model = llm.get_model()
        response_obj = model.prompt(full_prompt)
        response = response_obj.text()
    except Exception as e:
        return {
            "response": None,
            "appended_to": None,
            "error": f"LLM error: {e}",
        }

    # Format Q&A section
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    context_note = f" (context: {context_days} days)" if context_days > 0 else ""
    qa_section = f"""
---

### LLM Processing - {timestamp}{context_note}

**Q:** {question}

**A:**
{response}

"""

    # Append to note
    with open(path, "a") as f:
        f.write(qa_section)

    return {
        "response": response,
        "appended_to": str(path),
        "error": None,
    }
