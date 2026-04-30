"""Tests for A/B testing data classes."""

from llm_radar.ab_testing import ABTestResult, VariantResult


class TestVariantResult:
    def test_success_variant(self):
        v = VariantResult(
            label="A", provider="openai", model="gpt-4o-mini",
            response_text="Hello world", input_tokens=100, output_tokens=50,
            cost_usd=0.001, latency_ms=250.0, status="success",
        )
        assert v.label == "A"
        assert v.status == "success"
        assert v.error_message is None

    def test_error_variant(self):
        v = VariantResult(
            label="B", provider="anthropic", model="claude-3-haiku",
            response_text="", input_tokens=0, output_tokens=0,
            cost_usd=0.0, latency_ms=50.0, status="error",
            error_message="API key invalid",
        )
        assert v.status == "error"
        assert v.error_message == "API key invalid"


class TestABTestResult:
    def _make_result(self):
        return ABTestResult(
            test_id="abc123",
            name="test-1",
            variants=[
                VariantResult(
                    label="A", provider="openai", model="gpt-4o-mini",
                    response_text="Fast", input_tokens=100, output_tokens=50,
                    cost_usd=0.002, latency_ms=100.0, status="success",
                ),
                VariantResult(
                    label="B", provider="anthropic", model="claude-3-haiku",
                    response_text="Cheap", input_tokens=100, output_tokens=50,
                    cost_usd=0.001, latency_ms=200.0, status="success",
                ),
            ],
        )

    def test_winner_by_cost(self):
        result = self._make_result()
        assert result.winner_by_cost.label == "B"

    def test_winner_by_latency(self):
        result = self._make_result()
        assert result.winner_by_latency.label == "A"

    def test_no_winner_all_errors(self):
        result = ABTestResult(
            test_id="err",
            name="failing",
            variants=[
                VariantResult(
                    label="A", provider="openai", model="gpt-4o",
                    response_text="", input_tokens=0, output_tokens=0,
                    cost_usd=0.0, latency_ms=50.0, status="error",
                    error_message="fail",
                ),
            ],
        )
        assert result.winner_by_cost is None
        assert result.winner_by_latency is None

    def test_summary(self):
        result = self._make_result()
        s = result.summary()
        assert s["test_id"] == "abc123"
        assert s["name"] == "test-1"
        assert len(s["variants"]) == 2
        assert s["winner_by_cost"] == "B"
        assert s["winner_by_latency"] == "A"
