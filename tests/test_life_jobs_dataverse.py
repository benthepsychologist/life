"""Tests for life_jobs.dataverse module.

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

import json
from unittest.mock import MagicMock, patch

from life_jobs import dataverse


class TestDataverseQuery:
    """Tests for dataverse.query function."""

    @patch("life_jobs.dataverse.DataverseClient")
    def test_query_returns_records(self, mock_client_class):
        """Should query Dataverse and return records."""
        # Setup mock
        mock_client = MagicMock()
        mock_client.query.return_value = [
            {"id": "1", "name": "Test 1"},
            {"id": "2", "name": "Test 2"},
        ]
        mock_client_class.from_authctl.return_value = mock_client

        result = dataverse.query(
            account="test_account",
            entity="contacts",
            select=["id", "name"],
            filter="statecode eq 0",
        )

        # Verify client was called correctly
        mock_client_class.from_authctl.assert_called_once_with("test_account")
        mock_client.query.assert_called_once_with(
            "contacts",
            select=["id", "name"],
            filter="statecode eq 0",
            orderby=None,
            top=None,
            expand=None,
        )

        # Verify result
        assert result["count"] == 2
        assert len(result["records"]) == 2
        assert "output" not in result  # No output file

    @patch("life_jobs.dataverse.DataverseClient")
    def test_query_writes_output_when_specified(self, mock_client_class, tmp_path):
        """Should write to file when output is specified."""
        mock_client = MagicMock()
        mock_client.query.return_value = [{"id": "1"}]
        mock_client_class.from_authctl.return_value = mock_client

        output_file = tmp_path / "output.json"

        result = dataverse.query(
            account="test",
            entity="contacts",
            output=str(output_file),
        )

        assert output_file.exists()
        assert result["output"] == str(output_file)
        data = json.loads(output_file.read_text())
        assert len(data) == 1

    @patch("life_jobs.dataverse.DataverseClient")
    def test_query_creates_parent_dirs(self, mock_client_class, tmp_path):
        """Should create parent directories for output file."""
        mock_client = MagicMock()
        mock_client.query.return_value = []
        mock_client_class.from_authctl.return_value = mock_client

        output_file = tmp_path / "subdir" / "nested" / "output.json"

        dataverse.query(
            account="test",
            entity="contacts",
            output=str(output_file),
        )

        assert output_file.exists()


class TestDataverseGetSingle:
    """Tests for dataverse.get_single function."""

    @patch("life_jobs.dataverse.DataverseClient")
    def test_get_single_record(self, mock_client_class):
        """Should fetch a single record by ID."""
        mock_client = MagicMock()
        mock_client.query_single.return_value = {"id": "123", "name": "Test"}
        mock_client_class.from_authctl.return_value = mock_client

        result = dataverse.get_single(
            account="test",
            entity="contacts",
            record_id="123",
            select=["id", "name"],
        )

        mock_client.query_single.assert_called_once_with(
            "contacts", "123", select=["id", "name"]
        )
        assert result["id"] == "123"


class TestDataverseCreate:
    """Tests for dataverse.create function."""

    @patch("life_jobs.dataverse.DataverseClient")
    def test_create_record(self, mock_client_class):
        """Should create a new record."""
        mock_client = MagicMock()
        mock_client.post.return_value = {"id": "new-123", "name": "New Record"}
        mock_client_class.from_authctl.return_value = mock_client

        result = dataverse.create(
            account="test",
            entity="contacts",
            data={"name": "New Record"},
        )

        mock_client.post.assert_called_once_with("contacts", {"name": "New Record"})
        assert result["id"] == "new-123"


class TestDataverseUpdate:
    """Tests for dataverse.update function."""

    @patch("life_jobs.dataverse.DataverseClient")
    def test_update_record(self, mock_client_class):
        """Should update an existing record."""
        mock_client = MagicMock()
        mock_client.patch.return_value = {"id": "123", "name": "Updated"}
        mock_client_class.from_authctl.return_value = mock_client

        result = dataverse.update(
            account="test",
            entity="contacts",
            record_id="123",
            data={"name": "Updated"},
        )

        mock_client.patch.assert_called_once_with("contacts", "123", {"name": "Updated"})
        assert result["name"] == "Updated"


class TestDataverseDelete:
    """Tests for dataverse.delete function."""

    @patch("life_jobs.dataverse.DataverseClient")
    def test_delete_record(self, mock_client_class):
        """Should delete a record."""
        mock_client = MagicMock()
        mock_client_class.from_authctl.return_value = mock_client

        result = dataverse.delete(
            account="test",
            entity="contacts",
            record_id="123",
        )

        mock_client.delete.assert_called_once_with("contacts", "123")
        assert result["deleted"] is True
        assert result["record_id"] == "123"
