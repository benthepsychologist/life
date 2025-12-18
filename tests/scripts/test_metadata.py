"""Tests for script metadata loading and validation."""

import pytest
from datetime import date
from pathlib import Path
import tempfile

from life.scripts.metadata import (
    ScriptMetadata,
    ScriptValidationError,
    validate_name,
    load_metadata,
)


class TestValidateName:
    """Tests for validate_name function."""

    def test_valid_names(self):
        """Valid script names should pass validation."""
        valid_names = [
            "backfill-december",
            "cleanup-orphans",
            "a",
            "a-b-c",
            "test123",
            "my-script-2025",
            "x-y-z-1-2-3",
        ]
        for name in valid_names:
            validate_name(name)  # Should not raise

    def test_empty_name(self):
        """Empty name should raise error."""
        with pytest.raises(ScriptValidationError, match="cannot be empty"):
            validate_name("")

    def test_path_traversal_double_dot(self):
        """Path traversal with .. should be rejected."""
        with pytest.raises(ScriptValidationError, match="path traversal"):
            validate_name("../etc/passwd")

        with pytest.raises(ScriptValidationError, match="path traversal"):
            validate_name("foo..bar")

    def test_path_separators(self):
        """Path separators should be rejected."""
        with pytest.raises(ScriptValidationError, match="path separators"):
            validate_name("foo/bar")

        with pytest.raises(ScriptValidationError, match="path separators"):
            validate_name("foo\\bar")

    def test_dots(self):
        """Dots should be rejected."""
        with pytest.raises(ScriptValidationError, match="dots not allowed"):
            validate_name("foo.bar")

        with pytest.raises(ScriptValidationError, match="dots not allowed"):
            validate_name("script.sh")

    def test_uppercase(self):
        """Uppercase letters should be rejected."""
        with pytest.raises(ScriptValidationError, match="lowercase alphanumeric"):
            validate_name("BackfillDecember")

        with pytest.raises(ScriptValidationError, match="lowercase alphanumeric"):
            validate_name("UPPERCASE")

    def test_underscores(self):
        """Underscores should be rejected."""
        with pytest.raises(ScriptValidationError, match="lowercase alphanumeric"):
            validate_name("foo_bar")

    def test_spaces(self):
        """Spaces should be rejected."""
        with pytest.raises(ScriptValidationError, match="lowercase alphanumeric"):
            validate_name("foo bar")


class TestScriptMetadata:
    """Tests for ScriptMetadata dataclass."""

    def test_valid_metadata(self):
        """Valid metadata should pass validation."""
        metadata = ScriptMetadata(
            name="backfill-december",
            description="One-time backfill for December data",
            owner="@benthepsychologist",
            created_at=date(2025, 12, 17),
            ttl_days=30,
            promotion_target="job/backfill-pipeline",
        )
        metadata.validate()  # Should not raise

    def test_valid_metadata_with_email_owner(self):
        """Email owner should be valid."""
        metadata = ScriptMetadata(
            name="test-script",
            description="Test script",
            owner="ben@example.com",
            created_at=date(2025, 12, 17),
            ttl_days=30,
            promotion_target="job/test",
        )
        metadata.validate()  # Should not raise

    def test_valid_metadata_with_calls(self):
        """Metadata with calls list should be valid."""
        metadata = ScriptMetadata(
            name="test-script",
            description="Test script",
            owner="@user",
            created_at=date(2025, 12, 17),
            ttl_days=30,
            promotion_target="job/test",
            calls=["job/ingest-source", "job/validate-schema"],
        )
        metadata.validate()  # Should not raise

    def test_invalid_name(self):
        """Invalid name should fail validation."""
        metadata = ScriptMetadata(
            name="Invalid_Name",
            description="Test",
            owner="@user",
            created_at=date(2025, 12, 17),
            ttl_days=30,
            promotion_target="job/test",
        )
        with pytest.raises(ScriptValidationError, match="lowercase alphanumeric"):
            metadata.validate()

    def test_empty_description(self):
        """Empty description should fail validation."""
        metadata = ScriptMetadata(
            name="test-script",
            description="",
            owner="@user",
            created_at=date(2025, 12, 17),
            ttl_days=30,
            promotion_target="job/test",
        )
        with pytest.raises(ScriptValidationError, match="description is required"):
            metadata.validate()

    def test_invalid_owner_format(self):
        """Invalid owner format should fail validation."""
        metadata = ScriptMetadata(
            name="test-script",
            description="Test",
            owner="not-a-valid-owner",
            created_at=date(2025, 12, 17),
            ttl_days=30,
            promotion_target="job/test",
        )
        with pytest.raises(ScriptValidationError, match="owner must be"):
            metadata.validate()

    def test_zero_ttl(self):
        """Zero TTL should fail validation."""
        metadata = ScriptMetadata(
            name="test-script",
            description="Test",
            owner="@user",
            created_at=date(2025, 12, 17),
            ttl_days=0,
            promotion_target="job/test",
        )
        with pytest.raises(ScriptValidationError, match="ttl_days must be positive"):
            metadata.validate()

    def test_negative_ttl(self):
        """Negative TTL should fail validation."""
        metadata = ScriptMetadata(
            name="test-script",
            description="Test",
            owner="@user",
            created_at=date(2025, 12, 17),
            ttl_days=-10,
            promotion_target="job/test",
        )
        with pytest.raises(ScriptValidationError, match="ttl_days must be positive"):
            metadata.validate()

    def test_empty_promotion_target(self):
        """Empty promotion target should fail validation."""
        metadata = ScriptMetadata(
            name="test-script",
            description="Test",
            owner="@user",
            created_at=date(2025, 12, 17),
            ttl_days=30,
            promotion_target="",
        )
        with pytest.raises(ScriptValidationError, match="promotion_target is required"):
            metadata.validate()


class TestLoadMetadata:
    """Tests for load_metadata function."""

    def test_load_valid_metadata(self, tmp_path):
        """Should load valid metadata from file."""
        # Create script and metadata files
        script_file = tmp_path / "test-script.sh"
        script_file.write_text("#!/bin/bash\necho hello")

        meta_file = tmp_path / "test-script.meta.yaml"
        meta_file.write_text("""
name: test-script
description: A test script
owner: "@testuser"
created_at: 2025-12-17
ttl_days: 30
promotion_target: job/test-pipeline
calls:
  - job/step-one
  - job/step-two
""")

        script_path, metadata = load_metadata("test-script", [tmp_path])

        assert script_path == script_file
        assert metadata.name == "test-script"
        assert metadata.description == "A test script"
        assert metadata.owner == "@testuser"
        assert metadata.created_at == date(2025, 12, 17)
        assert metadata.ttl_days == 30
        assert metadata.promotion_target == "job/test-pipeline"
        assert metadata.calls == ["job/step-one", "job/step-two"]

    def test_load_from_multiple_search_paths(self, tmp_path):
        """Should search multiple paths and find first match."""
        path1 = tmp_path / "path1"
        path2 = tmp_path / "path2"
        path1.mkdir()
        path2.mkdir()

        # Script only in path2
        script_file = path2 / "my-script.sh"
        script_file.write_text("#!/bin/bash\necho test")

        meta_file = path2 / "my-script.meta.yaml"
        meta_file.write_text("""
name: my-script
description: Test
owner: "@user"
created_at: 2025-01-01
ttl_days: 14
promotion_target: job/target
""")

        script_path, metadata = load_metadata("my-script", [path1, path2])
        assert script_path == script_file
        assert metadata.name == "my-script"

    def test_invalid_name_before_filesystem(self, tmp_path):
        """Invalid name should be rejected before filesystem access."""
        with pytest.raises(ScriptValidationError, match="lowercase alphanumeric"):
            load_metadata("Invalid_Script", [tmp_path])

    def test_metadata_not_found(self, tmp_path):
        """Should raise error if metadata not found."""
        with pytest.raises(ScriptValidationError, match="no metadata file found"):
            load_metadata("nonexistent", [tmp_path])

    def test_metadata_without_script(self, tmp_path):
        """Should raise error if metadata exists but script doesn't."""
        meta_file = tmp_path / "orphan.meta.yaml"
        meta_file.write_text("""
name: orphan
description: Test
owner: "@user"
created_at: 2025-01-01
ttl_days: 14
promotion_target: job/target
""")

        with pytest.raises(ScriptValidationError, match="script.*not found"):
            load_metadata("orphan", [tmp_path])

    def test_invalid_yaml(self, tmp_path):
        """Should raise error on invalid YAML."""
        script_file = tmp_path / "bad-yaml.sh"
        script_file.write_text("#!/bin/bash")

        meta_file = tmp_path / "bad-yaml.meta.yaml"
        meta_file.write_text("invalid: yaml: syntax: [")

        with pytest.raises(ScriptValidationError, match="invalid YAML"):
            load_metadata("bad-yaml", [tmp_path])

    def test_name_mismatch(self, tmp_path):
        """Should raise error if metadata name doesn't match filename."""
        script_file = tmp_path / "actual-name.sh"
        script_file.write_text("#!/bin/bash")

        meta_file = tmp_path / "actual-name.meta.yaml"
        meta_file.write_text("""
name: different-name
description: Test
owner: "@user"
created_at: 2025-01-01
ttl_days: 14
promotion_target: job/target
""")

        with pytest.raises(ScriptValidationError, match="does not match filename"):
            load_metadata("actual-name", [tmp_path])

    def test_missing_required_field(self, tmp_path):
        """Should raise error if required field is missing."""
        script_file = tmp_path / "missing-field.sh"
        script_file.write_text("#!/bin/bash")

        meta_file = tmp_path / "missing-field.meta.yaml"
        meta_file.write_text("""
name: missing-field
description: Test
owner: "@user"
# missing created_at
ttl_days: 14
promotion_target: job/target
""")

        with pytest.raises(ScriptValidationError, match="created_at is required"):
            load_metadata("missing-field", [tmp_path])

    def test_nonexistent_search_path(self, tmp_path):
        """Should skip nonexistent search paths gracefully."""
        nonexistent = tmp_path / "does-not-exist"

        # Create valid script in tmp_path
        script_file = tmp_path / "test.sh"
        script_file.write_text("#!/bin/bash")

        meta_file = tmp_path / "test.meta.yaml"
        meta_file.write_text("""
name: test
description: Test
owner: "@user"
created_at: 2025-01-01
ttl_days: 14
promotion_target: job/target
""")

        # Should find it in tmp_path even though nonexistent is first
        script_path, metadata = load_metadata("test", [nonexistent, tmp_path])
        assert metadata.name == "test"
