"""Dataverse operations via morch.

Implementation rules enforced here (Rule 8):
- Never print
- Never read global config or environment (except Path.expanduser)
- Always return simple dicts
- Side effects: file IO, morch API calls, state updates only

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

# I/O declaration for static analysis and auditing
__io__ = {
    "reads": [],
    "writes": ["output"],
    "external": ["dataverse.query", "dataverse.post", "dataverse.patch", "dataverse.delete"],
}

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from morch import DataverseClient


def query(
    account: str,
    entity: str,
    select: Optional[List[str]] = None,
    filter: Optional[str] = None,
    orderby: Optional[str] = None,
    top: Optional[int] = None,
    expand: Optional[str] = None,
    output: Optional[str] = None,
) -> Dict[str, Any]:
    """Query Dataverse and return results.

    Args:
        account: authctl account name for authentication
        entity: Dataverse entity logical name (e.g., "contacts")
        select: List of fields to select
        filter: OData filter expression
        orderby: OData orderby expression
        top: Maximum number of records
        expand: OData expand expression
        output: Optional path to write JSON results

    Returns:
        Dict with records count, records list, and output path if written
    """
    client = DataverseClient.from_authctl(account)

    records = client.query(
        entity,
        select=select,
        filter=filter,
        orderby=orderby,
        top=top,
        expand=expand,
    )

    result: Dict[str, Any] = {"count": len(records), "records": records}

    if output:
        output_path = Path(output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(records, indent=2, default=str))
        result["output"] = str(output_path)

    return result


def get_single(
    account: str,
    entity: str,
    record_id: str,
    select: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Fetch a single record by ID.

    Args:
        account: authctl account name for authentication
        entity: Dataverse entity logical name
        record_id: Record GUID
        select: List of fields to select

    Returns:
        The record as a dict
    """
    client = DataverseClient.from_authctl(account)
    return client.query_single(entity, record_id, select=select)


def create(
    account: str,
    entity: str,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a new record in Dataverse.

    Args:
        account: authctl account name for authentication
        entity: Dataverse entity logical name
        data: Record data to create

    Returns:
        The created record
    """
    client = DataverseClient.from_authctl(account)
    return client.post(entity, data)


def update(
    account: str,
    entity: str,
    record_id: str,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """Update an existing record in Dataverse.

    Args:
        account: authctl account name for authentication
        entity: Dataverse entity logical name
        record_id: Record GUID
        data: Fields to update

    Returns:
        The updated record
    """
    client = DataverseClient.from_authctl(account)
    return client.patch(entity, record_id, data)


def delete(
    account: str,
    entity: str,
    record_id: str,
) -> Dict[str, Any]:
    """Delete a record from Dataverse.

    Args:
        account: authctl account name for authentication
        entity: Dataverse entity logical name
        record_id: Record GUID

    Returns:
        Dict confirming deletion
    """
    client = DataverseClient.from_authctl(account)
    client.delete(entity, record_id)
    return {"deleted": True, "entity": entity, "record_id": record_id}
