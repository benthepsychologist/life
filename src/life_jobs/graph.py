"""Graph API operations via morch.

Implementation rules enforced here (Rule 8):
- Never print
- Never read global config or environment (except Path.expanduser)
- Always return simple dicts
- Side effects: file IO, morch API calls only

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

# I/O declaration for static analysis and auditing
__io__ = {
    "reads": ["body_file"],
    "writes": ["output"],
    "external": ["msgraph.get", "msgraph.post"],
}

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from morch import GraphClient


def get_messages(
    account: str,
    output: str,
    top: int = 50,
    select: Optional[List[str]] = None,
    filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch messages from Graph API.

    Args:
        account: authctl account name for authentication
        output: Path to write JSON results
        top: Maximum number of messages (default: 50)
        select: List of fields to select
        filter: OData filter expression

    Returns:
        Dict with message count and output path
    """
    client = GraphClient.from_authctl(account, scopes=["Mail.Read"])

    params: Dict[str, str] = {"$top": str(top)}
    if select:
        params["$select"] = ",".join(select)
    if filter:
        params["$filter"] = filter

    messages = client.get_all("/me/messages", params=params)

    output_path = Path(output).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(messages, indent=2, default=str))

    return {"messages": len(messages), "output": str(output_path)}


def send_mail(
    account: str,
    to: List[str],
    subject: str,
    body: Optional[str] = None,
    body_file: Optional[str] = None,
    is_html: bool = False,
) -> Dict[str, Any]:
    """Send an email via Graph API.

    Args:
        account: authctl account name for authentication
        to: List of recipient email addresses
        subject: Email subject
        body: Email body text
        body_file: Path to file containing email body (alternative to body)
        is_html: Whether body is HTML (default: False)

    Returns:
        Dict confirming send with recipients and subject
    """
    client = GraphClient.from_authctl(account, scopes=["Mail.Send"])

    # Build body
    if body_file:
        body = Path(body_file).expanduser().read_text()

    message = {
        "subject": subject,
        "body": {
            "contentType": "HTML" if is_html else "Text",
            "content": body,
        },
        "toRecipients": [{"emailAddress": {"address": addr}} for addr in to],
    }

    client.post("/me/sendMail", {"message": message})
    return {"sent": True, "to": to, "subject": subject}


def me(account: str) -> Dict[str, Any]:
    """Get current user profile.

    Args:
        account: authctl account name for authentication

    Returns:
        User profile dict
    """
    client = GraphClient.from_authctl(account, scopes=["User.Read"])
    return client.me()


def get_calendar_events(
    account: str,
    output: str,
    top: int = 50,
    select: Optional[List[str]] = None,
    filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch calendar events from Graph API.

    Args:
        account: authctl account name for authentication
        output: Path to write JSON results
        top: Maximum number of events (default: 50)
        select: List of fields to select
        filter: OData filter expression

    Returns:
        Dict with event count and output path
    """
    client = GraphClient.from_authctl(account, scopes=["Calendars.Read"])

    params: Dict[str, str] = {"$top": str(top)}
    if select:
        params["$select"] = ",".join(select)
    if filter:
        params["$filter"] = filter

    events = client.get_all("/me/events", params=params)

    output_path = Path(output).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(events, indent=2, default=str))

    return {"events": len(events), "output": str(output_path)}


def get_files(
    account: str,
    output: str,
    folder_path: Optional[str] = None,
    top: int = 100,
) -> Dict[str, Any]:
    """Fetch files from OneDrive.

    Args:
        account: authctl account name for authentication
        output: Path to write JSON results
        folder_path: OneDrive folder path (default: root)
        top: Maximum number of files (default: 100)

    Returns:
        Dict with file count and output path
    """
    client = GraphClient.from_authctl(account, scopes=["Files.Read"])

    if folder_path:
        endpoint = f"/me/drive/root:/{folder_path}:/children"
    else:
        endpoint = "/me/drive/root/children"

    params: Dict[str, str] = {"$top": str(top)}
    files = client.get_all(endpoint, params=params)

    output_path = Path(output).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(files, indent=2, default=str))

    return {"files": len(files), "output": str(output_path)}
