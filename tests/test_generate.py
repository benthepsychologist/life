"""Tests for life_jobs.generate module.

Unit tests with mocked LLM responses - no actual API calls.

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

import json
import sys
import uuid
from unittest.mock import MagicMock, patch

import pytest


class TestImportGuard:
    """Tests for the llm import guard."""

    def test_require_llm_raises_when_not_installed(self, monkeypatch):
        """Should raise ImportError with helpful message when llm not installed."""
        # Force reload of generate module with llm unavailable
        monkeypatch.setitem(sys.modules, "llm", None)

        # Create a fresh module state
        with patch.dict("sys.modules", {"llm": None}):
            from life_jobs import generate

            # Manually set availability to False
            original_available = generate._LLM_AVAILABLE
            generate._LLM_AVAILABLE = False

            try:
                with pytest.raises(ImportError) as exc_info:
                    generate._require_llm()

                assert "life[llm]" in str(exc_info.value)
            finally:
                generate._LLM_AVAILABLE = original_available


class TestPathExpansion:
    """Tests for path expansion utilities."""

    def test_expand_path_expands_tilde(self):
        """Should expand ~ to home directory."""
        from life_jobs.generate import _expand_path

        result = _expand_path("~/test/path")
        assert "~" not in str(result)
        assert result.name == "path"

    def test_resolve_template_returns_inline_text(self):
        """Should return inline text as-is."""
        from life_jobs.generate import _resolve_template

        result = _resolve_template("This is inline text")
        assert result == "This is inline text"

    def test_resolve_template_reads_file(self, tmp_path):
        """Should read file contents when path exists."""
        from life_jobs.generate import _resolve_template

        template_file = tmp_path / "template.txt"
        template_file.write_text("Template from file")

        result = _resolve_template(str(template_file))
        assert result == "Template from file"


class TestContextAssembly:
    """Tests for context file assembly."""

    def test_assemble_context_formats_json(self, tmp_path):
        """Should format JSON files with pretty printing."""
        from life_jobs.generate import _assemble_context

        json_file = tmp_path / "data.json"
        json_file.write_text('{"key":"value"}')

        result = _assemble_context("My prompt", [json_file])

        assert "My prompt" in result
        assert "# CONTEXT" in result
        assert "## Data" in result
        assert "```json" in result

    def test_assemble_context_handles_text_files(self, tmp_path):
        """Should include text files without code blocks."""
        from life_jobs.generate import _assemble_context

        text_file = tmp_path / "notes.txt"
        text_file.write_text("Some notes")

        result = _assemble_context("Prompt", [text_file])

        assert "## Notes" in result
        assert "Some notes" in result

    def test_assemble_context_handles_invalid_json(self, tmp_path):
        """Should handle invalid JSON gracefully."""
        from life_jobs.generate import _assemble_context

        bad_json = tmp_path / "bad.json"
        bad_json.write_text("not valid json {")

        result = _assemble_context("Prompt", [bad_json])

        assert "not valid json {" in result

    def test_smart_order_baseline_first(self, tmp_path):
        """Should order baseline.json first."""
        from life_jobs.generate import _smart_order_files

        files = [
            tmp_path / "other.json",
            tmp_path / "baseline.json",
            tmp_path / "metrics.json",
        ]
        for f in files:
            f.touch()

        result = _smart_order_files(files)

        assert result[0].name == "baseline.json"

    def test_smart_order_session_delta_second(self, tmp_path):
        """Should order session*delta* files after baseline."""
        from life_jobs.generate import _smart_order_files

        files = [
            tmp_path / "other.json",
            tmp_path / "session_01_delta.json",
            tmp_path / "baseline.json",
        ]
        for f in files:
            f.touch()

        result = _smart_order_files(files)

        assert result[0].name == "baseline.json"
        assert result[1].name == "session_01_delta.json"


class TestPromptFunction:
    """Tests for the prompt() function."""

    @patch("life_jobs.generate._llm")
    @patch("life_jobs.generate._LLM_AVAILABLE", True)
    def test_prompt_basic(self, mock_llm):
        """Should execute basic prompt and return result."""
        from life_jobs.generate import prompt

        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text.return_value = "LLM response"
        mock_response.input_tokens = 10
        mock_response.output_tokens = 20
        mock_model.prompt.return_value = mock_response
        mock_llm.get_model.return_value = mock_model

        result = prompt("Hello LLM")

        assert result["output"] == "LLM response"
        assert result["model"] == "gpt-4o-mini"
        assert result["tokens"]["input"] == 10
        assert result["tokens"]["output"] == 20
        assert result["tokens"]["total"] == 30
        assert result["written"] is None

    @patch("life_jobs.generate._llm")
    @patch("life_jobs.generate._LLM_AVAILABLE", True)
    def test_prompt_with_custom_model(self, mock_llm):
        """Should use specified model."""
        from life_jobs.generate import prompt

        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text.return_value = "Response"
        mock_response.input_tokens = None
        mock_response.output_tokens = None
        mock_model.prompt.return_value = mock_response
        mock_llm.get_model.return_value = mock_model

        result = prompt("Test", model="gpt-4")

        mock_llm.get_model.assert_called_with("gpt-4")
        assert result["model"] == "gpt-4"

    @patch("life_jobs.generate._llm")
    @patch("life_jobs.generate._LLM_AVAILABLE", True)
    def test_prompt_with_system(self, mock_llm):
        """Should pass system prompt to model."""
        from life_jobs.generate import prompt

        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text.return_value = "Response"
        mock_response.input_tokens = None
        mock_response.output_tokens = None
        mock_model.prompt.return_value = mock_response
        mock_llm.get_model.return_value = mock_model

        prompt("Test", system="Be helpful")

        mock_model.prompt.assert_called_with("Test", system="Be helpful")

    @patch("life_jobs.generate._llm")
    @patch("life_jobs.generate._LLM_AVAILABLE", True)
    def test_prompt_writes_output(self, mock_llm, tmp_path):
        """Should write response to file when output specified."""
        from life_jobs.generate import prompt

        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text.return_value = "File content"
        mock_response.input_tokens = None
        mock_response.output_tokens = None
        mock_model.prompt.return_value = mock_response
        mock_llm.get_model.return_value = mock_model

        output_file = tmp_path / "output.md"
        result = prompt("Test", output=str(output_file))

        assert output_file.exists()
        assert output_file.read_text() == "File content"
        assert result["written"] == str(output_file)

    @patch("life_jobs.generate._llm")
    @patch("life_jobs.generate._LLM_AVAILABLE", True)
    def test_prompt_tokens_none_when_unavailable(self, mock_llm):
        """Should return None for tokens when model doesn't provide them."""
        from life_jobs.generate import prompt

        mock_model = MagicMock()
        mock_response = MagicMock(spec=[])  # No token attributes
        mock_response.text = MagicMock(return_value="Response")
        mock_model.prompt.return_value = mock_response
        mock_llm.get_model.return_value = mock_model

        result = prompt("Test")

        assert result["tokens"]["input"] is None
        assert result["tokens"]["output"] is None
        assert result["tokens"]["total"] is None


class TestPromptWithContext:
    """Tests for the prompt_with_context() function."""

    @patch("life_jobs.generate._llm")
    @patch("life_jobs.generate._LLM_AVAILABLE", True)
    def test_prompt_with_context_assembles_files(self, mock_llm, tmp_path):
        """Should assemble context files into prompt."""
        from life_jobs.generate import prompt_with_context

        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text.return_value = "Summary"
        mock_response.input_tokens = 100
        mock_response.output_tokens = 50
        mock_model.prompt.return_value = mock_response
        mock_llm.get_model.return_value = mock_model

        context_file = tmp_path / "data.json"
        context_file.write_text('{"key": "value"}')

        result = prompt_with_context(
            "Summarize this", context_files=[str(context_file)]
        )

        # Verify the assembled prompt was passed
        call_args = mock_model.prompt.call_args
        assembled_prompt = call_args[0][0]
        assert "Summarize this" in assembled_prompt
        assert "# CONTEXT" in assembled_prompt
        assert "key" in assembled_prompt

        assert result["output"] == "Summary"
        assert result["context_files"] == [str(context_file)]

    @patch("life_jobs.generate._llm")
    @patch("life_jobs.generate._LLM_AVAILABLE", True)
    def test_prompt_with_context_smart_ordering(self, mock_llm, tmp_path):
        """Should apply smart ordering to context files."""
        from life_jobs.generate import prompt_with_context

        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text.return_value = "Response"
        mock_response.input_tokens = None
        mock_response.output_tokens = None
        mock_model.prompt.return_value = mock_response
        mock_llm.get_model.return_value = mock_model

        # Create files in non-ideal order
        other = tmp_path / "other.json"
        baseline = tmp_path / "baseline.json"
        metrics = tmp_path / "metrics.json"
        for f in [other, baseline, metrics]:
            f.write_text("{}")

        result = prompt_with_context(
            "Test",
            context_files=[str(other), str(baseline), str(metrics)],
            smart_order=True,
        )

        # baseline should be first
        assert result["context_files"][0].endswith("baseline.json")


class TestBatchFunction:
    """Tests for the batch() function."""

    @patch("life_jobs.generate._llm")
    @patch("life_jobs.generate._LLM_AVAILABLE", True)
    def test_batch_processes_items(self, mock_llm, tmp_path):
        """Should process each item in batch."""
        from life_jobs.generate import batch

        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text.return_value = "Processed"
        mock_response.input_tokens = 10
        mock_response.output_tokens = 5
        mock_model.prompt.return_value = mock_response
        mock_llm.get_model.return_value = mock_model

        items_file = tmp_path / "items.json"
        items_file.write_text('[{"id": 1}, {"id": 2}]')

        output_file = tmp_path / "results.json"

        result = batch(
            str(items_file),
            "Process this item",
            output=str(output_file),
        )

        assert result["count"] == 2
        assert result["succeeded"] == 2
        assert result["failed"] == 0
        assert len(result["results"]) == 2
        assert result["written"] == str(output_file)

    @patch("life_jobs.generate._llm")
    @patch("life_jobs.generate._LLM_AVAILABLE", True)
    def test_batch_date_filtering(self, mock_llm, tmp_path):
        """Should filter items by date range."""
        from life_jobs.generate import batch

        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text.return_value = "OK"
        mock_response.input_tokens = 5
        mock_response.output_tokens = 2
        mock_model.prompt.return_value = mock_response
        mock_llm.get_model.return_value = mock_model

        items_file = tmp_path / "items.json"
        items_file.write_text(
            json.dumps(
                [
                    {"date": "2024-01-01", "id": 1},
                    {"date": "2024-06-15", "id": 2},
                    {"date": "2024-12-31", "id": 3},
                ]
            )
        )

        result = batch(
            str(items_file),
            "Process",
            start_date="2024-06-01",
            end_date="2024-08-01",
        )

        assert result["count"] == 1
        assert result["succeeded"] == 1

    @patch("life_jobs.generate._llm")
    @patch("life_jobs.generate._LLM_AVAILABLE", True)
    def test_batch_empty_after_filtering(self, mock_llm, tmp_path):
        """Should handle empty result after date filtering."""
        from life_jobs.generate import batch

        items_file = tmp_path / "items.json"
        items_file.write_text('[{"date": "2020-01-01"}]')

        result = batch(
            str(items_file),
            "Process",
            start_date="2024-01-01",
        )

        assert result["count"] == 0
        assert result["succeeded"] == 0
        assert result["failed"] == 0
        assert result["results"] == []
        assert result["written"] is None

    @patch("life_jobs.generate._llm")
    @patch("life_jobs.generate._LLM_AVAILABLE", True)
    def test_batch_call_id_uniqueness(self, mock_llm, tmp_path):
        """Should generate unique UUIDv4 call_id for each item."""
        from life_jobs.generate import batch

        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text.return_value = "OK"
        mock_response.input_tokens = 5
        mock_response.output_tokens = 2
        mock_model.prompt.return_value = mock_response
        mock_llm.get_model.return_value = mock_model

        items_file = tmp_path / "items.json"
        items_file.write_text('[{"id": 1}, {"id": 2}, {"id": 3}]')

        result = batch(str(items_file), "Process")

        call_ids = [r["call_id"] for r in result["results"]]

        # All unique
        assert len(call_ids) == len(set(call_ids))

        # All valid UUIDs
        for call_id in call_ids:
            uuid.UUID(call_id, version=4)

    @patch("life_jobs.generate._llm")
    @patch("life_jobs.generate._LLM_AVAILABLE", True)
    def test_batch_token_aggregation(self, mock_llm, tmp_path):
        """Should aggregate tokens across batch."""
        from life_jobs.generate import batch

        mock_model = MagicMock()

        # Different token counts per call
        responses = [
            MagicMock(input_tokens=10, output_tokens=5),
            MagicMock(input_tokens=20, output_tokens=10),
        ]
        for r in responses:
            r.text.return_value = "OK"

        mock_model.prompt.side_effect = responses
        mock_llm.get_model.return_value = mock_model

        items_file = tmp_path / "items.json"
        items_file.write_text('[{"id": 1}, {"id": 2}]')

        result = batch(str(items_file), "Process")

        assert result["total_tokens"]["input"] == 30
        assert result["total_tokens"]["output"] == 15
        assert result["total_tokens"]["total"] == 45


class TestBatchErrorHandling:
    """Tests for batch error handling and production safeguards."""

    @patch("life_jobs.generate._llm")
    @patch("life_jobs.generate._LLM_AVAILABLE", True)
    def test_batch_continue_on_error_true(self, mock_llm, tmp_path):
        """Should continue processing when continue_on_error=True."""
        from life_jobs.generate import batch

        mock_model = MagicMock()

        # First call fails, second succeeds
        mock_model.prompt.side_effect = [
            Exception("API Error"),
            MagicMock(text=MagicMock(return_value="OK"), input_tokens=5, output_tokens=2),
        ]
        mock_llm.get_model.return_value = mock_model

        items_file = tmp_path / "items.json"
        items_file.write_text('[{"id": 1}, {"id": 2}]')

        result = batch(
            str(items_file),
            "Process",
            continue_on_error=True,
            max_retries=0,  # No retries
        )

        assert result["count"] == 2
        assert result["succeeded"] == 1
        assert result["failed"] == 1
        assert result["results"][0]["status"] == "failed"
        assert result["results"][1]["status"] == "success"

    @patch("life_jobs.generate._llm")
    @patch("life_jobs.generate._LLM_AVAILABLE", True)
    def test_batch_continue_on_error_false_stops(self, mock_llm, tmp_path):
        """Should stop at first failure when continue_on_error=False."""
        from life_jobs.generate import batch

        mock_model = MagicMock()
        mock_model.prompt.side_effect = Exception("API Error")
        mock_llm.get_model.return_value = mock_model

        items_file = tmp_path / "items.json"
        items_file.write_text('[{"id": 1}, {"id": 2}, {"id": 3}]')

        result = batch(
            str(items_file),
            "Process",
            continue_on_error=False,
            max_retries=0,
        )

        # Should stop after first failure
        assert result["failed"] == 1
        assert len(result["results"]) == 1

    @patch("life_jobs.generate._llm")
    @patch("life_jobs.generate._LLM_AVAILABLE", True)
    def test_batch_accumulate_defaults_continue_on_error_false(self, mock_llm, tmp_path):
        """accumulate=True should default to continue_on_error=False."""
        from life_jobs.generate import batch

        mock_model = MagicMock()
        mock_model.prompt.side_effect = Exception("API Error")
        mock_llm.get_model.return_value = mock_model

        items_file = tmp_path / "items.json"
        items_file.write_text('[{"id": 1}, {"id": 2}]')

        result = batch(
            str(items_file),
            "Process",
            accumulate=True,
            max_retries=0,
        )

        # Should stop after first failure (default continue_on_error=False for accumulate)
        assert len(result["results"]) == 1

    @patch("life_jobs.generate._llm")
    @patch("life_jobs.generate._LLM_AVAILABLE", True)
    def test_batch_accumulate_with_explicit_continue(self, mock_llm, tmp_path):
        """Should honor explicit continue_on_error even with accumulate."""
        from life_jobs.generate import batch

        mock_model = MagicMock()

        # First fails, second succeeds
        mock_model.prompt.side_effect = [
            Exception("Fail"),
            MagicMock(text=MagicMock(return_value="OK"), input_tokens=5, output_tokens=2),
        ]
        mock_llm.get_model.return_value = mock_model

        items_file = tmp_path / "items.json"
        items_file.write_text('[{"id": 1}, {"id": 2}]')

        result = batch(
            str(items_file),
            "Process",
            accumulate=True,
            continue_on_error=True,  # Explicit override
            max_retries=0,
        )

        # Should continue despite accumulate=True
        assert len(result["results"]) == 2


class TestRetryWithBackoff:
    """Tests for retry with exponential backoff."""

    @patch("life_jobs.generate._llm")
    @patch("life_jobs.generate._LLM_AVAILABLE", True)
    def test_retry_on_transient_error(self, mock_llm, tmp_path):
        """Should retry on rate limit errors."""
        from life_jobs.generate import batch

        mock_model = MagicMock()
        sleep_times = []

        def fake_sleep(t):
            sleep_times.append(t)

        # First two calls fail with rate limit, third succeeds
        mock_model.prompt.side_effect = [
            Exception("rate limit exceeded"),
            Exception("429 too many requests"),
            MagicMock(text=MagicMock(return_value="OK"), input_tokens=5, output_tokens=2),
        ]
        mock_llm.get_model.return_value = mock_model

        items_file = tmp_path / "items.json"
        items_file.write_text('[{"id": 1}]')

        result = batch(
            str(items_file),
            "Process",
            max_retries=3,
            retry_delay=1.0,
            retry_backoff=2.0,
            _sleep_func=fake_sleep,
        )

        assert result["succeeded"] == 1
        assert len(sleep_times) == 2  # Two retries before success
        assert sleep_times[0] == 1.0  # First retry: delay * backoff^0
        assert sleep_times[1] == 2.0  # Second retry: delay * backoff^1


class TestRateLimiting:
    """Tests for rate limiting with injectable clock."""

    @patch("life_jobs.generate._llm")
    @patch("life_jobs.generate._LLM_AVAILABLE", True)
    def test_rate_limiting_sleeps(self, mock_llm, tmp_path):
        """Should sleep to respect rate limit."""
        from life_jobs.generate import batch

        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text.return_value = "OK"
        mock_response.input_tokens = 5
        mock_response.output_tokens = 2
        mock_model.prompt.return_value = mock_response
        mock_llm.get_model.return_value = mock_model

        # Fake clock
        current_time = [0.0]
        sleep_durations = []

        def fake_time():
            return current_time[0]

        def fake_sleep(duration):
            sleep_durations.append(duration)
            current_time[0] += duration

        items_file = tmp_path / "items.json"
        items_file.write_text('[{"id": 1}, {"id": 2}, {"id": 3}]')

        # 60 RPM = 1 request per second
        batch(
            str(items_file),
            "Process",
            rate_limit_rpm=60,
            _time_func=fake_time,
            _sleep_func=fake_sleep,
        )

        # Should have slept between requests
        assert len(sleep_durations) >= 2

    @patch("life_jobs.generate._llm")
    @patch("life_jobs.generate._LLM_AVAILABLE", True)
    def test_no_rate_limiting_when_none(self, mock_llm, tmp_path):
        """Should not sleep when rate_limit_rpm is None."""
        from life_jobs.generate import batch

        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text.return_value = "OK"
        mock_response.input_tokens = 5
        mock_response.output_tokens = 2
        mock_model.prompt.return_value = mock_response
        mock_llm.get_model.return_value = mock_model

        sleep_calls = []

        def fake_sleep(duration):
            sleep_calls.append(duration)

        items_file = tmp_path / "items.json"
        items_file.write_text('[{"id": 1}, {"id": 2}]')

        batch(
            str(items_file),
            "Process",
            rate_limit_rpm=None,
            _sleep_func=fake_sleep,
        )

        # No rate limiting sleep calls (only retry sleeps if any)
        # The rate limiter won't be created, so no waits
        assert len(sleep_calls) == 0


class TestBatchAccumulation:
    """Tests for batch accumulation mode."""

    @patch("life_jobs.generate._llm")
    @patch("life_jobs.generate._LLM_AVAILABLE", True)
    def test_accumulation_passes_previous_results(self, mock_llm, tmp_path):
        """Should include previous results in subsequent prompts."""
        from life_jobs.generate import batch

        mock_model = MagicMock()
        prompts_received = []

        def capture_prompt(prompt, system=None):
            prompts_received.append(prompt)
            response = MagicMock()
            response.text.return_value = f"Result {len(prompts_received)}"
            response.input_tokens = 10
            response.output_tokens = 5
            return response

        mock_model.prompt.side_effect = capture_prompt
        mock_llm.get_model.return_value = mock_model

        items_file = tmp_path / "items.json"
        items_file.write_text('[{"id": 1}, {"id": 2}]')

        batch(
            str(items_file),
            "Process item",
            accumulate=True,
        )

        # Second prompt should contain first result
        assert "Result 1" in prompts_received[1]
        assert "Previous Results" in prompts_received[1]


class TestBatchOutputFormat:
    """Tests for batch output file format."""

    @patch("life_jobs.generate._llm")
    @patch("life_jobs.generate._LLM_AVAILABLE", True)
    def test_output_is_json_array(self, mock_llm, tmp_path):
        """Output should be a valid JSON array."""
        from life_jobs.generate import batch

        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text.return_value = "OK"
        mock_response.input_tokens = 5
        mock_response.output_tokens = 2
        mock_model.prompt.return_value = mock_response
        mock_llm.get_model.return_value = mock_model

        items_file = tmp_path / "items.json"
        items_file.write_text('[{"id": 1}, {"id": 2}]')

        output_file = tmp_path / "results.json"
        batch(str(items_file), "Process", output=str(output_file))

        # Should be valid JSON array
        data = json.loads(output_file.read_text())
        assert isinstance(data, list)
        assert len(data) == 2

    @patch("life_jobs.generate._llm")
    @patch("life_jobs.generate._LLM_AVAILABLE", True)
    def test_results_ordering_matches_input(self, mock_llm, tmp_path):
        """Results should maintain input order."""
        from life_jobs.generate import batch

        mock_model = MagicMock()
        call_count = [0]

        def mock_prompt(prompt, system=None):
            call_count[0] += 1
            response = MagicMock()
            response.text.return_value = f"Response {call_count[0]}"
            response.input_tokens = 5
            response.output_tokens = 2
            return response

        mock_model.prompt.side_effect = mock_prompt
        mock_llm.get_model.return_value = mock_model

        items_file = tmp_path / "items.json"
        items_file.write_text('[{"id": "A"}, {"id": "B"}, {"id": "C"}]')

        result = batch(str(items_file), "Process")

        # Verify order
        assert result["results"][0]["item"]["id"] == "A"
        assert result["results"][1]["item"]["id"] == "B"
        assert result["results"][2]["item"]["id"] == "C"


class TestRateLimiterClass:
    """Direct tests for the RateLimiter class."""

    def test_rate_limiter_waits_between_calls(self):
        """Should wait appropriate time between calls."""
        from life_jobs.generate import RateLimiter

        current_time = [1.0]  # Start at time 1.0
        sleep_durations = []

        def fake_time():
            return current_time[0]

        def fake_sleep(duration):
            sleep_durations.append(duration)
            current_time[0] += duration

        limiter = RateLimiter(60, time_func=fake_time, sleep_func=fake_sleep)

        # First call after initialization (last_call=0)
        # elapsed = 1.0 - 0 = 1.0 >= interval (1.0), so no sleep
        limiter.wait()

        # Simulate only 0.3s passing
        current_time[0] = 1.3  # last_call was set to 1.0 after first wait

        # Second call - should wait 0.7s (interval - elapsed)
        limiter.wait()

        assert len(sleep_durations) == 1
        assert abs(sleep_durations[0] - 0.7) < 0.01

    def test_rate_limiter_no_wait_if_interval_passed(self):
        """Should not wait if interval has passed."""
        from life_jobs.generate import RateLimiter

        current_time = [1.0]  # Start at time 1.0
        sleep_durations = []

        def fake_time():
            return current_time[0]

        def fake_sleep(duration):
            sleep_durations.append(duration)
            current_time[0] += duration

        limiter = RateLimiter(60, time_func=fake_time, sleep_func=fake_sleep)

        # First call - enough time elapsed from 0
        limiter.wait()

        # Simulate 2 seconds passing (interval is 1s for 60 RPM)
        current_time[0] = 3.0

        # Second call - no sleep needed
        limiter.wait()

        # No sleep calls
        assert len(sleep_durations) == 0
