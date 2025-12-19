"""Tests for life_jobs.writeback module.

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from life_jobs.writeback import (
    EPSILON,
    _build_patch,
    _is_file_changed,
    _parse_frontmatter,
    apply_writeback,
    plan_writeback,
)


class TestParseFrontmatter:
    """Tests for _parse_frontmatter helper."""

    def test_parse_valid_frontmatter(self, tmp_path):
        """Should parse valid YAML frontmatter."""
        md_file = tmp_path / "test.md"
        md_file.write_text("""---
entity: cre92_clientsessions
record_id: abc-123
projected_at: '2025-01-01T00:00:00+00:00'
---

Body content here.
""")
        frontmatter, body = _parse_frontmatter(md_file)

        assert frontmatter is not None
        assert frontmatter["entity"] == "cre92_clientsessions"
        assert frontmatter["record_id"] == "abc-123"
        assert body.strip() == "Body content here."

    def test_parse_no_frontmatter(self, tmp_path):
        """Should return None for files without frontmatter."""
        md_file = tmp_path / "test.md"
        md_file.write_text("Just plain content, no frontmatter.")

        frontmatter, body = _parse_frontmatter(md_file)

        assert frontmatter is None
        assert "Just plain content" in body

    def test_parse_unclosed_frontmatter(self, tmp_path):
        """Should return None for unclosed frontmatter delimiter."""
        md_file = tmp_path / "test.md"
        md_file.write_text("""---
entity: test
No closing delimiter
""")
        frontmatter, body = _parse_frontmatter(md_file)

        assert frontmatter is None

    def test_parse_invalid_yaml(self, tmp_path):
        """Should return None for invalid YAML in frontmatter."""
        md_file = tmp_path / "test.md"
        md_file.write_text("""---
entity: [unclosed bracket
---

Body
""")
        frontmatter, body = _parse_frontmatter(md_file)

        assert frontmatter is None

    def test_parse_non_dict_frontmatter(self, tmp_path):
        """Should return None if frontmatter is not a dict."""
        md_file = tmp_path / "test.md"
        md_file.write_text("""---
- item1
- item2
---

Body
""")
        frontmatter, body = _parse_frontmatter(md_file)

        assert frontmatter is None


class TestIsFileChanged:
    """Tests for _is_file_changed helper."""

    def test_changed_file(self, tmp_path):
        """Should detect file changed after projection."""
        md_file = tmp_path / "test.md"
        md_file.write_text("content")

        # Set projected_at to well before the file was created
        old_time = "2020-01-01T00:00:00+00:00"

        assert _is_file_changed(md_file, old_time) is True

    def test_unchanged_file(self, tmp_path):
        """Should detect file not changed since projection."""
        md_file = tmp_path / "test.md"
        md_file.write_text("content")

        # Set projected_at to now (future relative to file mtime)
        future_time = datetime.now(timezone.utc).isoformat()
        # Wait a moment to ensure file mtime is in the past
        time.sleep(0.1)

        # Rewrite projected_at to be after file mtime
        future_dt = datetime.now(timezone.utc)
        future_time = future_dt.isoformat()

        # The file was written before future_time, so it's unchanged
        # We need to set the file's mtime to before projected_at
        old_mtime = future_dt.timestamp() - EPSILON - 10
        os.utime(md_file, (old_mtime, old_mtime))

        assert _is_file_changed(md_file, future_time) is False

    def test_epsilon_boundary(self, tmp_path):
        """Should respect EPSILON for change detection."""
        md_file = tmp_path / "test.md"
        md_file.write_text("content")

        # Get current file mtime
        file_mtime = os.path.getmtime(md_file)

        # Set projected_at to exactly file_mtime (within epsilon = not changed)
        projected_at_dt = datetime.fromtimestamp(file_mtime, tz=timezone.utc)
        projected_at_str = projected_at_dt.isoformat()

        # File mtime == projected_at, so file_mtime <= projected_at + EPSILON
        assert _is_file_changed(md_file, projected_at_str) is False


class TestBuildPatch:
    """Tests for _build_patch helper."""

    def test_build_patch_from_frontmatter(self):
        """Should build patch from frontmatter fields."""
        frontmatter = {"title": "My Title", "status": "completed"}
        body = "Body content"
        editable_fields = {
            "crf_title": "title",
            "crf_status": "status",
        }

        patch = _build_patch(frontmatter, body, editable_fields)

        assert patch == {
            "crf_title": "My Title",
            "crf_status": "completed",
        }

    def test_build_patch_with_body(self):
        """Should include body content when mapped."""
        frontmatter = {"title": "Title"}
        body = "This is the note content."
        editable_fields = {
            "crf_title": "title",
            "crf_note": "body",
        }

        patch = _build_patch(frontmatter, body, editable_fields)

        assert patch["crf_title"] == "Title"
        assert patch["crf_note"] == "This is the note content."

    def test_build_patch_with_body_html(self):
        """Should convert markdown body to HTML when mapped via body_html."""
        frontmatter = {}
        body = "**Bold**\n\nParagraph"
        editable_fields = {
            "crf_rich": "body_html",
        }

        patch = _build_patch(frontmatter, body, editable_fields)

        assert patch["crf_rich"].strip().startswith("<")
        assert "<strong>Bold</strong>" in patch["crf_rich"]

    def test_build_patch_skips_missing_fields(self):
        """Should skip fields not in frontmatter."""
        frontmatter = {"title": "Title"}
        body = "Body"
        editable_fields = {
            "crf_title": "title",
            "crf_status": "nonexistent_field",
        }

        patch = _build_patch(frontmatter, body, editable_fields)

        assert "crf_title" in patch
        assert "crf_status" not in patch

    def test_build_patch_skips_none_values(self):
        """Should skip fields with None values."""
        frontmatter = {"title": None, "status": "active"}
        body = "Body"
        editable_fields = {
            "crf_title": "title",
            "crf_status": "status",
        }

        patch = _build_patch(frontmatter, body, editable_fields)

        assert "crf_title" not in patch
        assert patch["crf_status"] == "active"


class TestPlanWriteback:
    """Tests for plan_writeback function."""

    def _create_md_file(self, path: Path, frontmatter: dict, body: str = "Body"):
        """Helper to create a markdown file with frontmatter."""
        fm_yaml = yaml.safe_dump(frontmatter, sort_keys=False)
        content = f"---\n{fm_yaml}---\n\n{body}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def test_plan_writeback_detects_changed_files(self, tmp_path):
        """Should detect files changed since projection."""
        vault = tmp_path / "vault"
        plan_file = tmp_path / "plan.json"

        # Create a file with old projected_at
        self._create_md_file(
            vault / "session.md",
            {
                "entity": "cre92_clientsessions",
                "record_id": "abc-123",
                "projected_at": "2020-01-01T00:00:00+00:00",
                "editable_fields": {"crf_note": "body"},
            },
            body="Updated note content",
        )

        result = plan_writeback(
            vault_root=str(vault),
            plan_path=str(plan_file),
        )

        assert result["files_scanned"] == 1
        assert result["files_changed"] == 1
        assert plan_file.exists()

        plan = json.loads(plan_file.read_text())
        assert len(plan["operations"]) == 1
        assert plan["operations"][0]["entity"] == "cre92_clientsessions"
        assert plan["operations"][0]["id"] == "abc-123"
        assert plan["operations"][0]["patch"]["crf_note"] == "Updated note content"

    def test_plan_writeback_skips_unchanged_files(self, tmp_path):
        """Should skip files not changed since projection."""
        vault = tmp_path / "vault"
        plan_file = tmp_path / "plan.json"

        # Create file
        md_file = vault / "session.md"
        self._create_md_file(
            md_file,
            {
                "entity": "cre92_clientsessions",
                "record_id": "abc-123",
                "projected_at": datetime.now(timezone.utc).isoformat(),
                "editable_fields": {"crf_note": "body"},
            },
        )

        # Set file mtime to before projected_at
        old_mtime = datetime.now(timezone.utc).timestamp() - EPSILON - 100
        os.utime(md_file, (old_mtime, old_mtime))

        result = plan_writeback(
            vault_root=str(vault),
            plan_path=str(plan_file),
        )

        assert result["files_scanned"] == 1
        assert result["files_changed"] == 0

        plan = json.loads(plan_file.read_text())
        assert len(plan["operations"]) == 0

    def test_plan_writeback_skips_no_frontmatter(self, tmp_path):
        """Should skip files without frontmatter."""
        vault = tmp_path / "vault"
        plan_file = tmp_path / "plan.json"

        (vault / "plain.md").mkdir(parents=True, exist_ok=True)
        (vault / "plain.md").rmdir()
        vault.mkdir(parents=True, exist_ok=True)
        (vault / "plain.md").write_text("Just plain content")

        result = plan_writeback(
            vault_root=str(vault),
            plan_path=str(plan_file),
        )

        assert result["files_scanned"] == 1
        assert result["files_skipped"] == 1
        assert result["files_changed"] == 0

    def test_plan_writeback_skips_missing_required_keys(self, tmp_path):
        """Should skip files missing required frontmatter keys."""
        vault = tmp_path / "vault"
        plan_file = tmp_path / "plan.json"

        # Missing editable_fields
        self._create_md_file(
            vault / "incomplete.md",
            {
                "entity": "cre92_clientsessions",
                "record_id": "abc-123",
                "projected_at": "2020-01-01T00:00:00+00:00",
                # Missing editable_fields
            },
        )

        result = plan_writeback(
            vault_root=str(vault),
            plan_path=str(plan_file),
        )

        assert result["files_skipped"] == 1
        assert len(result["errors"]) == 1
        assert "editable_fields" in result["errors"][0]["reason"]

    def test_plan_writeback_skips_invalid_editable_fields(self, tmp_path):
        """Should skip files with invalid editable_fields."""
        vault = tmp_path / "vault"
        plan_file = tmp_path / "plan.json"

        # editable_fields is not a dict
        self._create_md_file(
            vault / "bad.md",
            {
                "entity": "cre92_clientsessions",
                "record_id": "abc-123",
                "projected_at": "2020-01-01T00:00:00+00:00",
                "editable_fields": "not a dict",
            },
        )

        result = plan_writeback(
            vault_root=str(vault),
            plan_path=str(plan_file),
        )

        assert result["files_skipped"] == 1
        assert "non-empty dict" in result["errors"][0]["reason"]

    def test_plan_writeback_writes_plan_json(self, tmp_path):
        """Should write properly formatted plan JSON."""
        vault = tmp_path / "vault"
        plan_file = tmp_path / "plans" / "nested" / "plan.json"

        self._create_md_file(
            vault / "session.md",
            {
                "entity": "cre92_clientsessions",
                "record_id": "abc-123",
                "projected_at": "2020-01-01T00:00:00+00:00",
                "editable_fields": {"crf_note": "body"},
            },
        )

        plan_writeback(
            vault_root=str(vault),
            plan_path=str(plan_file),
        )

        assert plan_file.exists()
        plan = json.loads(plan_file.read_text())

        assert plan["version"] == 1
        assert "generated_at" in plan
        assert "vault_root" in plan
        assert "operations" in plan

    def test_plan_writeback_uses_glob_pattern(self, tmp_path):
        """Should respect glob_pattern argument."""
        vault = tmp_path / "vault"
        plan_file = tmp_path / "plan.json"

        # Create .md file
        self._create_md_file(
            vault / "notes" / "session.md",
            {
                "entity": "cre92_clientsessions",
                "record_id": "abc-123",
                "projected_at": "2020-01-01T00:00:00+00:00",
                "editable_fields": {"crf_note": "body"},
            },
        )

        # Create .txt file (should be ignored)
        (vault / "notes" / "other.txt").write_text("ignored")

        result = plan_writeback(
            vault_root=str(vault),
            plan_path=str(plan_file),
            glob_pattern="**/*.md",
        )

        assert result["files_scanned"] == 1  # Only .md file

    def test_plan_writeback_multiple_files(self, tmp_path):
        """Should handle multiple changed files."""
        vault = tmp_path / "vault"
        plan_file = tmp_path / "plan.json"

        for i in range(3):
            self._create_md_file(
                vault / f"session-{i}.md",
                {
                    "entity": "cre92_clientsessions",
                    "record_id": f"id-{i}",
                    "projected_at": "2020-01-01T00:00:00+00:00",
                    "editable_fields": {"crf_note": "body"},
                },
                body=f"Content {i}",
            )

        result = plan_writeback(
            vault_root=str(vault),
            plan_path=str(plan_file),
        )

        assert result["files_scanned"] == 3
        assert result["files_changed"] == 3

        plan = json.loads(plan_file.read_text())
        assert len(plan["operations"]) == 3


class TestApplyWriteback:
    """Tests for apply_writeback function."""

    @patch("life_jobs.writeback.DataverseClient")
    def test_apply_writeback_calls_patch(self, mock_client_class, tmp_path):
        """Should call Dataverse patch for each operation."""
        mock_client = MagicMock()
        mock_client_class.from_authctl.return_value = mock_client

        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps({
            "version": 1,
            "generated_at": "2025-01-01T00:00:00+00:00",
            "vault_root": "/vault",
            "operations": [
                {
                    "entity": "cre92_clientsessions",
                    "id": "abc-123",
                    "source_path": "session.md",
                    "patch": {"crf_note": "Updated note"},
                },
            ],
        }))

        result = apply_writeback(
            account="lifeos",
            plan_path=str(plan_file),
        )

        mock_client_class.from_authctl.assert_called_once_with("lifeos")
        mock_client.patch.assert_called_once_with(
            "cre92_clientsessions",
            "abc-123",
            {"crf_note": "Updated note"},
        )
        assert result["operations"] == 1
        assert result["succeeded"] == 1
        assert result["failed"] == 0

    @patch("life_jobs.writeback.DataverseClient")
    def test_apply_writeback_handles_failures(self, mock_client_class, tmp_path):
        """Should continue on error and report failures."""
        mock_client = MagicMock()
        mock_client.patch.side_effect = [
            None,  # First succeeds
            Exception("API Error"),  # Second fails
            None,  # Third succeeds
        ]
        mock_client_class.from_authctl.return_value = mock_client

        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps({
            "version": 1,
            "generated_at": "2025-01-01T00:00:00+00:00",
            "vault_root": "/vault",
            "operations": [
                {"entity": "e1", "id": "id-1", "patch": {}},
                {"entity": "e2", "id": "id-2", "patch": {}},
                {"entity": "e3", "id": "id-3", "patch": {}},
            ],
        }))

        result = apply_writeback(
            account="lifeos",
            plan_path=str(plan_file),
        )

        assert result["operations"] == 3
        assert result["succeeded"] == 2
        assert result["failed"] == 1
        assert len(result["errors"]) == 1
        assert result["errors"][0]["id"] == "id-2"
        assert "API Error" in result["errors"][0]["reason"]

    def test_apply_writeback_validates_version(self, tmp_path):
        """Should reject unsupported plan versions."""
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps({
            "version": 999,
            "operations": [],
        }))

        with pytest.raises(ValueError, match="Unsupported plan version"):
            apply_writeback(account="lifeos", plan_path=str(plan_file))

    @patch("life_jobs.writeback.DataverseClient")
    def test_apply_writeback_empty_operations(self, mock_client_class, tmp_path):
        """Should return early for empty operations without creating client."""
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps({
            "version": 1,
            "generated_at": "2025-01-01T00:00:00+00:00",
            "vault_root": "/vault",
            "operations": [],
        }))

        result = apply_writeback(
            account="lifeos",
            plan_path=str(plan_file),
        )

        # Client should not be created for empty operations
        mock_client_class.from_authctl.assert_not_called()
        assert result["operations"] == 0
        assert result["succeeded"] == 0
        assert result["failed"] == 0

    @patch("life_jobs.writeback.DataverseClient")
    def test_apply_writeback_multiple_operations(self, mock_client_class, tmp_path):
        """Should process multiple operations."""
        mock_client = MagicMock()
        mock_client_class.from_authctl.return_value = mock_client

        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps({
            "version": 1,
            "generated_at": "2025-01-01T00:00:00+00:00",
            "vault_root": "/vault",
            "operations": [
                {"entity": "e1", "id": "id-1", "patch": {"f1": "v1"}},
                {"entity": "e2", "id": "id-2", "patch": {"f2": "v2"}},
            ],
        }))

        result = apply_writeback(
            account="lifeos",
            plan_path=str(plan_file),
        )

        assert mock_client.patch.call_count == 2
        assert result["succeeded"] == 2
