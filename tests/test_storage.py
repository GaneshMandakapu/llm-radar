"""Tests for LLMStorage (DuckDB backend)."""

import pytest
from llm_radar.storage.db import LLMStorage


@pytest.fixture
def storage(tmp_path):
    """Create a fresh in-memory storage for each test."""
    return LLMStorage(db_path=str(tmp_path / "test.duckdb"))


class TestRecord:
    def test_record_returns_id(self, storage):
        call_id = storage.record(provider="openai", model="gpt-4o-mini")
        assert isinstance(call_id, str)
        assert len(call_id) > 0

    def test_record_stores_call(self, storage):
        storage.record(
            provider="openai",
            model="gpt-4o-mini",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.001,
            latency_ms=250.0,
            status="success",
            prompt_preview="Hello world",
            response_preview="Hi there",
        )
        calls = storage.get_calls(limit=10)
        assert len(calls) == 1
        c = calls[0]
        assert c["provider"] == "openai"
        assert c["model"] == "gpt-4o-mini"
        assert c["input_tokens"] == 100
        assert c["output_tokens"] == 50
        assert c["total_tokens"] == 150
        assert c["cost_usd"] == pytest.approx(0.001)
        assert c["status"] == "success"

    def test_record_error_status(self, storage):
        storage.record(
            provider="anthropic",
            model="claude-3-haiku",
            status="error",
            error_message="Rate limit exceeded",
        )
        calls = storage.get_calls()
        assert calls[0]["status"] == "error"
        assert calls[0]["error_message"] == "Rate limit exceeded"


class TestGetCalls:
    def test_get_calls_empty(self, storage):
        calls = storage.get_calls()
        assert calls == []

    def test_get_calls_limit(self, storage):
        for i in range(5):
            storage.record(provider="openai", model=f"model-{i}")
        calls = storage.get_calls(limit=3)
        assert len(calls) == 3

    def test_get_calls_filter_by_provider(self, storage):
        storage.record(provider="openai", model="gpt-4o-mini")
        storage.record(provider="anthropic", model="claude-3-haiku")
        storage.record(provider="openai", model="gpt-4o")
        calls = storage.get_calls(provider="openai")
        assert len(calls) == 2
        assert all(c["provider"] == "openai" for c in calls)

    def test_get_calls_filter_by_model(self, storage):
        storage.record(provider="openai", model="gpt-4o-mini")
        storage.record(provider="openai", model="gpt-4o")
        calls = storage.get_calls(model="gpt-4o")
        assert len(calls) == 1
        assert calls[0]["model"] == "gpt-4o"

    def test_get_calls_filter_by_status(self, storage):
        storage.record(provider="openai", model="gpt-4o", status="success")
        storage.record(provider="openai", model="gpt-4o", status="error")
        calls = storage.get_calls(status="error")
        assert len(calls) == 1
        assert calls[0]["status"] == "error"


class TestGetStats:
    def test_stats_empty(self, storage):
        stats = storage.get_stats()
        assert stats["totals"]["calls"] == 0
        assert stats["totals"]["tokens"] == 0
        assert stats["by_model"] == []

    def test_stats_aggregated(self, storage):
        storage.record(provider="openai", model="gpt-4o-mini", input_tokens=100, output_tokens=50, cost_usd=0.001, latency_ms=200)
        storage.record(provider="openai", model="gpt-4o-mini", input_tokens=200, output_tokens=100, cost_usd=0.002, latency_ms=300)
        stats = storage.get_stats()
        assert stats["totals"]["calls"] == 2
        assert stats["totals"]["tokens"] == 450  # (100+50) + (200+100)
        assert stats["totals"]["cost_usd"] == pytest.approx(0.003)
        assert len(stats["by_model"]) == 1


class TestExportCalls:
    def test_export_json(self, storage):
        import json
        storage.record(provider="openai", model="gpt-4o-mini", input_tokens=10)
        data = storage.export_calls(fmt="json")
        parsed = json.loads(data)
        assert len(parsed) == 1
        assert parsed[0]["provider"] == "openai"

    def test_export_csv(self, storage):
        storage.record(provider="openai", model="gpt-4o-mini")
        data = storage.export_calls(fmt="csv")
        assert "provider" in data
        assert "openai" in data

    def test_export_empty_csv(self, storage):
        data = storage.export_calls(fmt="csv")
        assert data == ""

    def test_export_invalid_format(self, storage):
        with pytest.raises(ValueError, match="Unknown format"):
            storage.export_calls(fmt="xml")


class TestABTestStorage:
    def test_record_and_get_ab_test(self, storage):
        from llm_radar.ab_testing import ABTestResult, VariantResult
        result = ABTestResult(
            test_id="test123",
            name="comparison-1",
            variants=[
                VariantResult(
                    label="A", provider="openai", model="gpt-4o-mini",
                    response_text="Hello", input_tokens=10, output_tokens=5,
                    cost_usd=0.001, latency_ms=100.0, status="success",
                ),
                VariantResult(
                    label="B", provider="anthropic", model="claude-3-haiku",
                    response_text="Hi", input_tokens=10, output_tokens=5,
                    cost_usd=0.0005, latency_ms=150.0, status="success",
                ),
            ],
        )
        storage.record_ab_test(result)
        tests = storage.get_ab_tests()
        assert len(tests) == 1
        assert tests[0]["name"] == "comparison-1"
        assert tests[0]["winner_cost"] == "B"
        assert tests[0]["winner_latency"] == "A"
