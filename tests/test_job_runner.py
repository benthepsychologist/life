"""Tests for job_runner module.

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

import json

import pytest

from life.job_runner import (
    CallNotAllowedError,
    InvalidJobNameError,
    JobLoadError,
    UnsubstitutedVariableError,
    _check_unsubstituted,
    _substitute_variables,
    get_job,
    list_jobs,
    load_jobs,
    resolve_callable,
    run_job,
    validate_job_name,
)


class TestResolveCallable:
    """Tests for resolve_callable function."""

    def test_resolve_callable_allowed_prefix(self):
        """Should resolve callables from allowed prefixes."""
        # life_jobs.shell.run is a valid callable
        # We'll test this once life_jobs module exists
        pass

    def test_resolve_callable_not_allowed(self):
        """Should reject callables not in allowlist."""
        with pytest.raises(CallNotAllowedError) as exc_info:
            resolve_callable("os.system")
        assert "not allowed" in str(exc_info.value)
        assert "life_jobs." in str(exc_info.value)

    def test_resolve_callable_builtins_blocked(self):
        """Should block builtin modules."""
        with pytest.raises(CallNotAllowedError):
            resolve_callable("subprocess.run")


class TestSubstituteVariables:
    """Tests for _substitute_variables function."""

    def test_simple_string(self):
        """Should substitute in simple strings."""
        result = _substitute_variables("Hello {name}!", {"name": "World"})
        assert result == "Hello World!"

    def test_dict_values(self):
        """Should substitute in dict values."""
        result = _substitute_variables(
            {"greeting": "Hello {name}!", "path": "{dir}/file.txt"},
            {"name": "User", "dir": "/home"},
        )
        assert result == {"greeting": "Hello User!", "path": "/home/file.txt"}

    def test_list_values(self):
        """Should substitute in list items."""
        result = _substitute_variables(
            ["{a}", "{b}", "literal"],
            {"a": "first", "b": "second"},
        )
        assert result == ["first", "second", "literal"]

    def test_nested_structures(self):
        """Should handle nested dicts and lists."""
        result = _substitute_variables(
            {"outer": {"inner": ["{val}"]}},
            {"val": "nested"},
        )
        assert result == {"outer": {"inner": ["nested"]}}

    def test_non_string_values_unchanged(self):
        """Should leave non-string values unchanged."""
        result = _substitute_variables(
            {"num": 42, "bool": True, "none": None},
            {"anything": "value"},
        )
        assert result == {"num": 42, "bool": True, "none": None}

    def test_missing_variable_leaves_placeholder(self):
        """Missing variables leave placeholder (caught by _check_unsubstituted)."""
        result = _substitute_variables("Hello {missing}!", {})
        assert result == "Hello {missing}!"


class TestCheckUnsubstituted:
    """Tests for _check_unsubstituted function."""

    def test_no_placeholders_ok(self):
        """Should pass when no placeholders remain."""
        _check_unsubstituted("Hello World!", "test_step")  # No exception

    def test_remaining_placeholder_raises(self):
        """Should raise when placeholders remain."""
        with pytest.raises(UnsubstitutedVariableError) as exc_info:
            _check_unsubstituted("Hello {name}!", "test_step")
        assert "name" in str(exc_info.value)
        assert "test_step" in str(exc_info.value)

    def test_multiple_unsubstituted(self):
        """Should report all unsubstituted variables."""
        with pytest.raises(UnsubstitutedVariableError) as exc_info:
            _check_unsubstituted(
                {"a": "{foo}", "b": "{bar}"},
                "test_step",
            )
        assert "foo" in str(exc_info.value)
        assert "bar" in str(exc_info.value)


class TestLoadJobs:
    """Tests for load_jobs function."""

    def test_load_from_empty_dir(self, tmp_path):
        """Should return empty dict for empty directory."""
        jobs = load_jobs(tmp_path)
        assert jobs == {}

    def test_load_from_nonexistent_dir(self, tmp_path):
        """Should return empty dict for nonexistent directory."""
        nonexistent = tmp_path / "nonexistent"
        jobs = load_jobs(nonexistent)
        assert jobs == {}

    def test_load_single_job_file(self, tmp_path):
        """Should load jobs from a single YAML file."""
        job_file = tmp_path / "test.yaml"
        job_file.write_text(
            """
jobs:
  test_job:
    description: "A test job"
    steps:
      - name: step1
        call: life_jobs.shell.run
        args:
          command: "echo hello"
"""
        )
        jobs = load_jobs(tmp_path)
        assert "test_job" in jobs
        assert jobs["test_job"]["description"] == "A test job"
        assert len(jobs["test_job"]["steps"]) == 1

    def test_load_multiple_files(self, tmp_path):
        """Should load jobs from multiple YAML files."""
        (tmp_path / "a.yaml").write_text(
            """
jobs:
  job_a:
    description: "Job A"
    steps: []
"""
        )
        (tmp_path / "b.yaml").write_text(
            """
jobs:
  job_b:
    description: "Job B"
    steps: []
"""
        )
        jobs = load_jobs(tmp_path)
        assert "job_a" in jobs
        assert "job_b" in jobs

    def test_yaml_error_raises_job_load_error(self, tmp_path):
        """Should raise JobLoadError for invalid YAML."""
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("invalid: yaml: content: [")

        with pytest.raises(JobLoadError) as exc_info:
            load_jobs(tmp_path)
        assert len(exc_info.value.errors) == 1
        assert "bad.yaml" in str(exc_info.value.errors[0][0])

    def test_multiple_yaml_errors(self, tmp_path):
        """Should collect all YAML errors."""
        (tmp_path / "bad1.yaml").write_text("invalid: [")
        (tmp_path / "bad2.yaml").write_text("also: bad: [")

        with pytest.raises(JobLoadError) as exc_info:
            load_jobs(tmp_path)
        assert len(exc_info.value.errors) == 2


class TestListJobs:
    """Tests for list_jobs function."""

    def test_list_empty(self, tmp_path):
        """Should return empty list for empty directory."""
        result = list_jobs(tmp_path)
        assert result == []

    def test_list_jobs_with_descriptions(self, tmp_path):
        """Should return job IDs and descriptions."""
        (tmp_path / "test.yaml").write_text(
            """
jobs:
  job_a:
    description: "First job"
    steps: []
  job_b:
    description: "Second job"
    steps: []
"""
        )
        result = list_jobs(tmp_path)
        assert len(result) == 2
        assert result[0] == {"job_id": "job_a", "description": "First job"}
        assert result[1] == {"job_id": "job_b", "description": "Second job"}


class TestValidateJobName:
    """Tests for validate_job_name function."""

    def test_valid_dotted_names(self):
        """Should accept valid dotted namespace names."""
        validate_job_name("email.send")
        validate_job_name("today.create_note")
        validate_job_name("dataverse.query")

    def test_invalid_undotted_names(self):
        """Should reject names without dots."""
        with pytest.raises(InvalidJobNameError):
            validate_job_name("send_email")
        with pytest.raises(InvalidJobNameError):
            validate_job_name("greet")

    def test_invalid_multi_dot_names(self):
        """Should reject names with more than one dot."""
        with pytest.raises(InvalidJobNameError):
            validate_job_name("email.send.batch")


class TestGetJob:
    """Tests for get_job function."""

    def test_get_existing_job(self, tmp_path):
        """Should return job definition for existing job."""
        (tmp_path / "test.yaml").write_text(
            """
jobs:
  test.job:
    description: "My job"
    steps:
      - name: step1
        call: life_jobs.dataverse.query
        args:
          entity: "contacts"
"""
        )
        job = get_job("test.job", tmp_path)
        assert job["description"] == "My job"
        assert len(job["steps"]) == 1

    def test_get_nonexistent_job(self, tmp_path):
        """Should raise KeyError for nonexistent job."""
        with pytest.raises(KeyError) as exc_info:
            get_job("test.nonexistent", tmp_path)
        assert "test.nonexistent" in str(exc_info.value)

    def test_get_job_invalid_name(self, tmp_path):
        """Should raise InvalidJobNameError for invalid job names."""
        with pytest.raises(InvalidJobNameError):
            get_job("invalid_name", tmp_path)


class TestRunJob:
    """Tests for run_job function."""

    def test_run_job_dry_run(self, tmp_path):
        """Should return step info without executing in dry-run mode."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()
        (jobs_dir / "test.yaml").write_text(
            """
jobs:
  test.job:
    description: "Test job"
    steps:
      - name: step1
        call: life_jobs.dataverse.query
        args:
          entity: "contacts"
"""
        )
        event_log = tmp_path / "events.jsonl"

        result = run_job(
            "test.job",
            dry_run=True,
            jobs_dir=jobs_dir,
            event_log=event_log,
        )

        assert result["status"] == "success"
        assert "run_id" in result
        assert len(result["steps"]) == 1
        assert result["steps"][0]["status"] == "skipped"
        assert result["steps"][0]["dry_run"] is True
        assert result["steps"][0]["call"] == "life_jobs.dataverse.query"

    def test_run_job_logs_events(self, tmp_path):
        """Should log events to JSONL file."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()
        (jobs_dir / "test.yaml").write_text(
            """
jobs:
  test.job:
    description: "Test job"
    steps:
      - name: step1
        call: life_jobs.dataverse.query
        args:
          entity: "contacts"
"""
        )
        event_log = tmp_path / "events.jsonl"

        run_job(
            "test.job",
            dry_run=True,
            jobs_dir=jobs_dir,
            event_log=event_log,
        )

        # Check event log
        assert event_log.exists()
        events = [json.loads(line) for line in event_log.read_text().strip().split("\n")]
        assert len(events) >= 2  # job.started and job.completed
        assert events[0]["event_type"] == "job.started"
        assert events[-1]["event_type"] == "job.completed"

    def test_run_job_nonexistent_raises(self, tmp_path):
        """Should raise KeyError for nonexistent job."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()
        event_log = tmp_path / "events.jsonl"

        with pytest.raises(KeyError):
            run_job(
                "test.nonexistent",
                dry_run=True,
                jobs_dir=jobs_dir,
                event_log=event_log,
            )

    def test_run_job_invalid_name_raises(self, tmp_path):
        """Should raise InvalidJobNameError for invalid job names."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()
        event_log = tmp_path / "events.jsonl"

        with pytest.raises(InvalidJobNameError):
            run_job(
                "invalid_name",
                dry_run=True,
                jobs_dir=jobs_dir,
                event_log=event_log,
            )

    def test_run_job_with_variables(self, tmp_path):
        """Should substitute variables in args."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()
        (jobs_dir / "test.yaml").write_text(
            """
jobs:
  test.greet:
    description: "Greet someone"
    steps:
      - name: greet
        call: life_jobs.dataverse.query
        args:
          entity: "{entity_name}"
"""
        )
        event_log = tmp_path / "events.jsonl"

        result = run_job(
            "test.greet",
            dry_run=True,
            jobs_dir=jobs_dir,
            event_log=event_log,
            variables={"entity_name": "contacts"},
        )

        assert result["steps"][0]["args"]["entity"] == "contacts"

    def test_run_job_unsubstituted_variable_error(self, tmp_path):
        """Should raise error for unsubstituted variables."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()
        (jobs_dir / "test.yaml").write_text(
            """
jobs:
  test.needs_var:
    description: "Needs a variable"
    steps:
      - name: step1
        call: life_jobs.dataverse.query
        args:
          entity: "{missing_var}"
"""
        )
        event_log = tmp_path / "events.jsonl"

        with pytest.raises(UnsubstitutedVariableError) as exc_info:
            run_job(
                "test.needs_var",
                dry_run=True,
                jobs_dir=jobs_dir,
                event_log=event_log,
            )
        assert "missing_var" in str(exc_info.value)


class TestEventClient:
    """Tests for EventClient."""

    def test_log_event_creates_file(self, tmp_path):
        """Should create log file if it doesn't exist."""
        from life.event_client import EventClient

        log_path = tmp_path / "subdir" / "events.jsonl"
        client = EventClient(log_path)
        client.log_event("job.started", "test-123", "success", {"job_id": "test"})

        assert log_path.exists()

    def test_log_event_appends(self, tmp_path):
        """Should append events to file."""
        from life.event_client import EventClient

        log_path = tmp_path / "events.jsonl"
        client = EventClient(log_path)
        client.log_event("job.started", "test-123", "success", {})
        client.log_event("job.completed", "test-123", "success", {})

        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_log_event_invalid_type_raises(self, tmp_path):
        """Should raise for invalid event types."""
        from life.event_client import EventClient

        log_path = tmp_path / "events.jsonl"
        client = EventClient(log_path)

        with pytest.raises(ValueError) as exc_info:
            client.log_event("invalid.type", "test-123", "success", {})
        assert "Unknown event_type" in str(exc_info.value)

    def test_log_event_includes_timestamp(self, tmp_path):
        """Should include timestamp in events."""
        from life.event_client import EventClient

        log_path = tmp_path / "events.jsonl"
        client = EventClient(log_path)
        client.log_event("job.started", "test-123", "success", {})

        event = json.loads(log_path.read_text().strip())
        assert "timestamp" in event
        assert "T" in event["timestamp"]  # ISO format

    def test_log_event_includes_error_message(self, tmp_path):
        """Should include error_message when provided."""
        from life.event_client import EventClient

        log_path = tmp_path / "events.jsonl"
        client = EventClient(log_path)
        client.log_event(
            "job.failed", "test-123", "failed", {}, error_message="Something went wrong"
        )

        event = json.loads(log_path.read_text().strip())
        assert event["error_message"] == "Something went wrong"
