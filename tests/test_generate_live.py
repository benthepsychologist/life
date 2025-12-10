"""Live acceptance tests for life_jobs.generate module.

These tests make real LLM API calls and only run when LLM_LIVE_TESTS=1.

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

import json
import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("LLM_LIVE_TESTS") != "1",
    reason="Live LLM tests disabled (set LLM_LIVE_TESTS=1 to run)",
)


class TestLivePrompt:
    """Live tests for prompt() function."""

    def test_live_prompt(self):
        """Single prompt should return non-empty text."""
        from life_jobs.generate import prompt

        result = prompt(
            "Respond with exactly one word: Hello",
            model="gpt-4o-mini",
        )

        assert result["output"]
        assert len(result["output"]) > 0
        assert result["model"] == "gpt-4o-mini"
        assert "tokens" in result

    def test_live_prompt_with_system(self):
        """Prompt with system message should work."""
        from life_jobs.generate import prompt

        result = prompt(
            "What is 2+2?",
            system="You are a math tutor. Answer briefly.",
            model="gpt-4o-mini",
        )

        assert result["output"]
        assert "4" in result["output"]

    def test_live_prompt_writes_file(self, tmp_path):
        """Should write response to file."""
        from life_jobs.generate import prompt

        output_file = tmp_path / "response.md"

        result = prompt(
            "Say 'test complete'",
            model="gpt-4o-mini",
            output=str(output_file),
        )

        assert output_file.exists()
        assert result["written"] == str(output_file)
        assert len(output_file.read_text()) > 0


class TestLivePromptWithContext:
    """Live tests for prompt_with_context() function."""

    def test_live_prompt_with_context(self, tmp_path):
        """Context assembly should work end-to-end."""
        from life_jobs.generate import prompt_with_context

        # Create context file
        context_file = tmp_path / "data.json"
        context_file.write_text(json.dumps({"name": "Alice", "role": "Developer"}))

        result = prompt_with_context(
            "What is the person's name in the context?",
            context_files=[str(context_file)],
            model="gpt-4o-mini",
        )

        assert result["output"]
        assert "Alice" in result["output"]
        assert str(context_file) in result["context_files"]

    def test_live_prompt_with_multiple_context_files(self, tmp_path):
        """Should handle multiple context files."""
        from life_jobs.generate import prompt_with_context

        file1 = tmp_path / "person.json"
        file1.write_text(json.dumps({"name": "Bob"}))

        file2 = tmp_path / "task.json"
        file2.write_text(json.dumps({"task": "Write tests"}))

        result = prompt_with_context(
            "Summarize: who is doing what task?",
            context_files=[str(file1), str(file2)],
            model="gpt-4o-mini",
        )

        assert result["output"]
        assert len(result["context_files"]) == 2


class TestLiveBatch:
    """Live tests for batch() function."""

    def test_live_batch_small(self, tmp_path):
        """2-3 item batch should complete with correct structure."""
        from life_jobs.generate import batch

        items_file = tmp_path / "items.json"
        items_file.write_text(
            json.dumps(
                [
                    {"id": 1, "question": "What is 1+1?"},
                    {"id": 2, "question": "What is 2+2?"},
                ]
            )
        )

        output_file = tmp_path / "results.json"

        result = batch(
            str(items_file),
            "Answer the question briefly.",
            output=str(output_file),
            model="gpt-4o-mini",
        )

        # Verify structure
        assert result["count"] == 2
        assert result["succeeded"] == 2
        assert result["failed"] == 0
        assert len(result["results"]) == 2

        # Verify each result has required fields
        for r in result["results"]:
            assert "call_id" in r
            assert r["status"] == "success"
            assert r["result"] is not None
            assert "tokens" in r
            assert r["model"] == "gpt-4o-mini"
            assert "duration_ms" in r

        # Verify output file
        assert output_file.exists()
        output_data = json.loads(output_file.read_text())
        assert len(output_data) == 2


class TestLiveHealthcheck:
    """Live test for the llm_healthcheck job."""

    def test_live_healthcheck(self):
        """Health check job should succeed."""
        from life_jobs.generate import prompt

        # Simulate what the healthcheck job does
        result = prompt(
            "Respond with exactly: OK",
            model="gpt-4o-mini",
        )

        assert result["output"]
        # The LLM should respond with something containing OK
        assert len(result["output"]) > 0
