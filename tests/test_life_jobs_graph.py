"""Tests for life_jobs.graph module.

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

from unittest.mock import MagicMock, patch

from life_jobs import graph


class TestGraphGetMessages:
    """Tests for graph.get_messages function."""

    @patch("life_jobs.graph.GraphClient")
    def test_get_messages_writes_output(self, mock_client_class, tmp_path):
        """Should fetch messages and write to file."""
        mock_client = MagicMock()
        mock_client.get_all.return_value = [
            {"id": "1", "subject": "Test 1"},
            {"id": "2", "subject": "Test 2"},
        ]
        mock_client_class.from_authctl.return_value = mock_client

        output_file = tmp_path / "messages.json"

        result = graph.get_messages(
            account="test",
            output=str(output_file),
            top=10,
            select=["id", "subject"],
        )

        mock_client_class.from_authctl.assert_called_once_with(
            "test", scopes=["Mail.Read"]
        )
        mock_client.get_all.assert_called_once()

        assert result["messages"] == 2
        assert output_file.exists()

    @patch("life_jobs.graph.GraphClient")
    def test_get_messages_with_filter(self, mock_client_class, tmp_path):
        """Should pass filter to API."""
        mock_client = MagicMock()
        mock_client.get_all.return_value = []
        mock_client_class.from_authctl.return_value = mock_client

        output_file = tmp_path / "messages.json"

        graph.get_messages(
            account="test",
            output=str(output_file),
            filter="isRead eq false",
        )

        call_args = mock_client.get_all.call_args
        assert "$filter" in call_args[1]["params"]


class TestGraphSendMail:
    """Tests for graph.send_mail function."""

    @patch("life_jobs.graph.GraphClient")
    def test_send_mail_text(self, mock_client_class):
        """Should send plain text email."""
        mock_client = MagicMock()
        mock_client_class.from_authctl.return_value = mock_client

        result = graph.send_mail(
            account="test",
            to=["user@example.com"],
            subject="Test Subject",
            body="Test body",
        )

        mock_client_class.from_authctl.assert_called_once_with(
            "test", scopes=["Mail.Send"]
        )
        mock_client.post.assert_called_once()

        call_args = mock_client.post.call_args
        message = call_args[0][1]["message"]
        assert message["subject"] == "Test Subject"
        assert message["body"]["contentType"] == "Text"
        assert message["body"]["content"] == "Test body"

        assert result["sent"] is True
        assert result["to"] == ["user@example.com"]

    @patch("life_jobs.graph.GraphClient")
    def test_send_mail_html(self, mock_client_class):
        """Should send HTML email."""
        mock_client = MagicMock()
        mock_client_class.from_authctl.return_value = mock_client

        graph.send_mail(
            account="test",
            to=["user@example.com"],
            subject="Test",
            body="<h1>HTML</h1>",
            is_html=True,
        )

        call_args = mock_client.post.call_args
        message = call_args[0][1]["message"]
        assert message["body"]["contentType"] == "HTML"

    @patch("life_jobs.graph.GraphClient")
    def test_send_mail_from_file(self, mock_client_class, tmp_path):
        """Should read body from file."""
        mock_client = MagicMock()
        mock_client_class.from_authctl.return_value = mock_client

        body_file = tmp_path / "body.txt"
        body_file.write_text("Body from file")

        graph.send_mail(
            account="test",
            to=["user@example.com"],
            subject="Test",
            body_file=str(body_file),
        )

        call_args = mock_client.post.call_args
        message = call_args[0][1]["message"]
        assert message["body"]["content"] == "Body from file"

    @patch("life_jobs.graph.GraphClient")
    def test_send_mail_multiple_recipients(self, mock_client_class):
        """Should support multiple recipients."""
        mock_client = MagicMock()
        mock_client_class.from_authctl.return_value = mock_client

        graph.send_mail(
            account="test",
            to=["user1@example.com", "user2@example.com"],
            subject="Test",
            body="Test",
        )

        call_args = mock_client.post.call_args
        message = call_args[0][1]["message"]
        assert len(message["toRecipients"]) == 2


class TestGraphMe:
    """Tests for graph.me function."""

    @patch("life_jobs.graph.GraphClient")
    def test_me(self, mock_client_class):
        """Should return user profile."""
        mock_client = MagicMock()
        mock_client.me.return_value = {
            "displayName": "Test User",
            "mail": "test@example.com",
        }
        mock_client_class.from_authctl.return_value = mock_client

        result = graph.me(account="test")

        mock_client_class.from_authctl.assert_called_once_with(
            "test", scopes=["User.Read"]
        )
        assert result["displayName"] == "Test User"


class TestGraphGetCalendarEvents:
    """Tests for graph.get_calendar_events function."""

    @patch("life_jobs.graph.GraphClient")
    def test_get_calendar_events(self, mock_client_class, tmp_path):
        """Should fetch calendar events and write to file."""
        mock_client = MagicMock()
        mock_client.get_all.return_value = [
            {"id": "1", "subject": "Meeting 1"},
        ]
        mock_client_class.from_authctl.return_value = mock_client

        output_file = tmp_path / "events.json"

        result = graph.get_calendar_events(
            account="test",
            output=str(output_file),
        )

        mock_client_class.from_authctl.assert_called_once_with(
            "test", scopes=["Calendars.Read"]
        )
        assert result["events"] == 1
        assert output_file.exists()


class TestGraphGetFiles:
    """Tests for graph.get_files function."""

    @patch("life_jobs.graph.GraphClient")
    def test_get_files_root(self, mock_client_class, tmp_path):
        """Should fetch files from root."""
        mock_client = MagicMock()
        mock_client.get_all.return_value = [
            {"id": "1", "name": "file1.txt"},
        ]
        mock_client_class.from_authctl.return_value = mock_client

        output_file = tmp_path / "files.json"

        result = graph.get_files(
            account="test",
            output=str(output_file),
        )

        mock_client.get_all.assert_called_once()
        call_args = mock_client.get_all.call_args
        assert "/me/drive/root/children" in call_args[0][0]

        assert result["files"] == 1

    @patch("life_jobs.graph.GraphClient")
    def test_get_files_folder(self, mock_client_class, tmp_path):
        """Should fetch files from specific folder."""
        mock_client = MagicMock()
        mock_client.get_all.return_value = []
        mock_client_class.from_authctl.return_value = mock_client

        output_file = tmp_path / "files.json"

        graph.get_files(
            account="test",
            output=str(output_file),
            folder_path="Documents/Work",
        )

        call_args = mock_client.get_all.call_args
        assert "Documents/Work" in call_args[0][0]
