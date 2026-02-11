# Copyright 2025 Ben Mensi
# SPDX-License-Identifier: Apache-2.0

"""Tests for email.* JobDef YAMLs.

These tests verify:
1. JobDef YAML files load correctly
2. Compilation resolves @payload.* references correctly
3. The steps are configured correctly (file.read + lorchestra.run)
4. Execution reads templates and passes content to lorchestra
"""

import pytest

from life.compiler import compile_job, load_job_yaml
from life.executor import execute


class TestEmailSendJobDef:
    """Tests for email.send JobDef."""

    def test_load_email_send(self):
        """Should load email.send JobDef YAML."""
        job_def = load_job_yaml("email.send")
        assert job_def["job_id"] == "email.send"
        assert job_def["version"] == "1.0"
        assert len(job_def["steps"]) == 1
        assert job_def["steps"][0]["op"] == "lorchestra.run"

    def test_compile_email_send(self):
        """Should compile email.send with payload."""
        job_def = load_job_yaml("email.send")
        payload = {
            "to": "user@example.com",
            "subject": "Test Subject",
            "body": "Test body content",
            "is_html": True,
            "provider": "gmail",
            "account": "personal-gmail",
        }

        instance = compile_job(job_def, payload=payload)

        assert instance.job_id == "email.send"
        assert len(instance.steps) == 1

        step = instance.steps[0]
        assert step.step_id == "send"
        assert step.op == "lorchestra.run"
        assert step.params["job_id"] == "email.send"

        # Verify payload passthrough
        step_payload = step.params["payload"]
        assert step_payload["to"] == "user@example.com"
        assert step_payload["subject"] == "Test Subject"
        assert step_payload["body"] == "Test body content"
        assert step_payload["is_html"] is True
        assert step_payload["provider"] == "gmail"
        assert step_payload["account"] == "personal-gmail"

    def test_compile_email_send_defaults_is_html(self):
        """Should default is_html to False when not provided."""
        job_def = load_job_yaml("email.send")
        payload = {
            "to": "user@example.com",
            "subject": "Test",
            "body": "Body",
            "provider": "gmail",
            "account": "test",
        }

        instance = compile_job(job_def, payload=payload)
        step_payload = instance.steps[0].params["payload"]

        # is_html should default to False
        assert step_payload["is_html"] is False


class TestEmailSendTemplatedJobDef:
    """Tests for email.send_templated JobDef."""

    def test_load_email_send_templated(self):
        """Should load email.send_templated JobDef YAML with two steps."""
        job_def = load_job_yaml("email.send_templated")
        assert job_def["job_id"] == "email.send_templated"
        assert job_def["version"] == "1.0"
        assert len(job_def["steps"]) == 2
        assert job_def["steps"][0]["op"] == "file.read"
        assert job_def["steps"][1]["op"] == "lorchestra.run"

    def test_compile_email_send_templated(self):
        """Should compile email.send_templated with payload."""
        job_def = load_job_yaml("email.send_templated")
        payload = {
            "to": "user@example.com",
            "template_path": "/abs/path/template.jinja2",
            "template_vars": {"name": "Alice", "date": "2025-01-01"},
            "provider": "gmail",
            "account": "personal-gmail",
        }

        instance = compile_job(job_def, payload=payload)

        assert instance.job_id == "email.send_templated"
        assert len(instance.steps) == 2

        # First step: file.read
        read_step = instance.steps[0]
        assert read_step.step_id == "read_template"
        assert read_step.op == "file.read"
        assert read_step.params["path"] == "/abs/path/template.jinja2"

        # Second step: lorchestra.run (template is @run ref, resolved at runtime)
        send_step = instance.steps[1]
        assert send_step.params["job_id"] == "email.send_templated"
        step_payload = send_step.params["payload"]
        assert step_payload["to"] == "user@example.com"
        assert step_payload["template"] == "@run.read_template.content"  # Resolved at runtime
        assert step_payload["template_vars"] == {"name": "Alice", "date": "2025-01-01"}
        assert step_payload["provider"] == "gmail"
        assert step_payload["account"] == "personal-gmail"

    def test_execute_email_send_templated_reads_file(self, tmp_path):
        """Should read template file and pass content to lorchestra."""
        # Create a test template
        template_file = tmp_path / "template.jinja2"
        template_file.write_text("Subject: Hello {{ name }}!\n\nWelcome, {{ name }}!")

        job_def = load_job_yaml("email.send_templated")
        payload = {
            "to": "user@example.com",
            "template_path": str(template_file),
            "template_vars": {"name": "Alice"},
            "provider": "gmail",
            "account": "test",
        }

        instance = compile_job(job_def, payload=payload)
        # Execute with dry_run to avoid actual lorchestra call
        record = execute(instance, ctx={"dry_run": True})

        assert record.success
        assert len(record.outcomes) == 2

        # First step should have read the file
        read_outcome = record.outcomes[0]
        assert read_outcome.step_id == "read_template"
        assert read_outcome.status == "completed"
        assert read_outcome.output["content"] == "Subject: Hello {{ name }}!\n\nWelcome, {{ name }}!"

        # Second step should have the template content in payload
        send_outcome = record.outcomes[1]
        assert send_outcome.step_id == "send"
        assert send_outcome.status == "completed"
        assert send_outcome.output["payload"]["template"] == "Subject: Hello {{ name }}!\n\nWelcome, {{ name }}!"


class TestEmailBatchSendJobDef:
    """Tests for email.batch_send JobDef."""

    def test_load_email_batch_send(self):
        """Should load email.batch_send JobDef YAML with two steps."""
        job_def = load_job_yaml("email.batch_send")
        assert job_def["job_id"] == "email.batch_send"
        assert job_def["version"] == "1.0"
        assert len(job_def["steps"]) == 2
        assert job_def["steps"][0]["op"] == "file.read"
        assert job_def["steps"][1]["op"] == "lorchestra.run"

    def test_compile_email_batch_send(self):
        """Should compile email.batch_send with pre-expanded items."""
        job_def = load_job_yaml("email.batch_send")
        items = [
            {"to": "alice@example.com", "template_vars": {"name": "Alice"}},
            {"to": "bob@example.com", "template_vars": {"name": "Bob"}, "idempotency_key": "bob-key"},
        ]
        payload = {
            "template_path": "/abs/path/batch_template.jinja2",
            "items": items,
            "provider": "sendgrid",
            "account": "marketing",
        }

        instance = compile_job(job_def, payload=payload)

        assert instance.job_id == "email.batch_send"
        assert len(instance.steps) == 2

        # First step: file.read
        read_step = instance.steps[0]
        assert read_step.op == "file.read"
        assert read_step.params["path"] == "/abs/path/batch_template.jinja2"

        # Second step: lorchestra.run
        send_step = instance.steps[1]
        step_payload = send_step.params["payload"]
        assert step_payload["template"] == "@run.read_template.content"  # Resolved at runtime
        assert step_payload["provider"] == "sendgrid"
        assert step_payload["account"] == "marketing"

        # Verify items are passed through unchanged (pre-expanded)
        assert len(step_payload["items"]) == 2
        assert step_payload["items"][0]["to"] == "alice@example.com"
        assert step_payload["items"][0]["template_vars"] == {"name": "Alice"}
        assert step_payload["items"][1]["to"] == "bob@example.com"
        assert step_payload["items"][1]["idempotency_key"] == "bob-key"

    def test_execute_email_batch_send_reads_file(self, tmp_path):
        """Should read template file and pass content to lorchestra."""
        # Create a test template
        template_file = tmp_path / "batch_template.jinja2"
        template_file.write_text("Subject: Batch Hello {{ name }}!\n\nHi {{ name }}!")

        job_def = load_job_yaml("email.batch_send")
        items = [{"to": "alice@example.com", "template_vars": {"name": "Alice"}}]
        payload = {
            "template_path": str(template_file),
            "items": items,
            "provider": "gmail",
            "account": "test",
        }

        instance = compile_job(job_def, payload=payload)
        record = execute(instance, ctx={"dry_run": True})

        assert record.success
        assert len(record.outcomes) == 2

        # First step should have read the file
        read_outcome = record.outcomes[0]
        assert read_outcome.output["content"] == "Subject: Batch Hello {{ name }}!\n\nHi {{ name }}!"

        # Second step should have the template content in payload
        send_outcome = record.outcomes[1]
        assert send_outcome.output["payload"]["template"] == "Subject: Batch Hello {{ name }}!\n\nHi {{ name }}!"


class TestFileReadOp:
    """Tests for the file.read op."""

    def test_file_read_missing_path(self):
        """Should fail if path parameter is missing."""
        from life.executor import _handle_file_read

        outcome = _handle_file_read("test_step", {}, {})
        assert outcome.status == "failed"
        assert "requires 'path' parameter" in outcome.error

    def test_file_read_relative_path(self):
        """Should fail for relative paths."""
        from life.executor import _handle_file_read

        outcome = _handle_file_read("test_step", {"path": "relative/path.txt"}, {})
        assert outcome.status == "failed"
        assert "requires absolute path" in outcome.error

    def test_file_read_file_not_found(self):
        """Should fail if file doesn't exist."""
        from life.executor import _handle_file_read

        outcome = _handle_file_read("test_step", {"path": "/nonexistent/file.txt"}, {})
        assert outcome.status == "failed"
        assert "File not found" in outcome.error

    def test_file_read_success(self, tmp_path):
        """Should read file content successfully."""
        from life.executor import _handle_file_read

        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        outcome = _handle_file_read("test_step", {"path": str(test_file)}, {})
        assert outcome.status == "completed"
        assert outcome.output["content"] == "Hello, World!"
        assert outcome.output["path"] == str(test_file)

    def test_file_read_ignores_dry_run(self, tmp_path):
        """Should read file even in dry_run mode (local op, needed for @run refs)."""
        from life.executor import _handle_file_read

        test_file = tmp_path / "test.txt"
        test_file.write_text("Content here")

        outcome = _handle_file_read("test_step", {"path": str(test_file)}, {"dry_run": True})
        assert outcome.status == "completed"
        assert outcome.output["content"] == "Content here"
