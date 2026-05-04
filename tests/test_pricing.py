"""Tests for the pricing module."""

import pytest
from llm_radar.pricing import calculate_cost, PRICING


class TestCalculateCost:
    def test_exact_match_openai(self):
        # gpt-4o-mini: $0.15/1M input, $0.60/1M output
        cost = calculate_cost("gpt-4o-mini", input_tokens=1_000_000, output_tokens=0)
        assert cost == pytest.approx(0.15)

    def test_exact_match_output(self):
        cost = calculate_cost("gpt-4o-mini", input_tokens=0, output_tokens=1_000_000)
        assert cost == pytest.approx(0.60)

    def test_combined_cost(self):
        cost = calculate_cost("gpt-4o-mini", input_tokens=1000, output_tokens=500)
        expected = (1000 * 0.15 + 500 * 0.60) / 1_000_000
        assert cost == pytest.approx(expected)

    def test_anthropic_model(self):
        cost = calculate_cost("claude-3-haiku", input_tokens=1_000_000, output_tokens=1_000_000)
        assert cost == pytest.approx(0.25 + 1.25)

    def test_prefix_match_versioned_model(self):
        # "gpt-4o-2024-11-20" should match "gpt-4o" via prefix
        cost = calculate_cost("gpt-4o-2024-11-20", input_tokens=1_000_000, output_tokens=0)
        assert cost == pytest.approx(2.50)

    def test_unknown_model_returns_zero(self):
        cost = calculate_cost("unknown-model-xyz", input_tokens=1000, output_tokens=500)
        assert cost == 0.0

    def test_zero_tokens(self):
        cost = calculate_cost("gpt-4o", input_tokens=0, output_tokens=0)
        assert cost == 0.0

    def test_case_insensitive(self):
        cost = calculate_cost("GPT-4O-MINI", input_tokens=1_000_000, output_tokens=0)
        assert cost == pytest.approx(0.15)

    def test_all_models_in_pricing_table(self):
        """Ensure every model in the pricing table returns a non-zero cost for non-zero tokens."""
        for model in PRICING:
            cost = calculate_cost(model, input_tokens=1000, output_tokens=1000)
            assert cost > 0, f"Expected non-zero cost for model {model}"

    def test_prompt_caching_savings(self):
        from llm_radar.pricing import calculate_cost_and_savings
        
        # OpenAI discount is 50%
        # gpt-4o input cost is $2.50
        # 1M total input tokens, all cached. Should cost $1.25, and save $1.25
        cost, savings = calculate_cost_and_savings("gpt-4o", input_tokens=1_000_000, output_tokens=0, cached_tokens=1_000_000)
        assert cost == pytest.approx(1.25)
        assert savings == pytest.approx(1.25)

        # Anthropic discount is 90%
        # claude-3-5-sonnet input cost is $3.00
        # 1M total input tokens, all cached. Should cost $0.30, and save $2.70
        cost, savings = calculate_cost_and_savings("claude-3-5-sonnet", input_tokens=1_000_000, output_tokens=0, cached_tokens=1_000_000)
        assert cost == pytest.approx(0.30)
        assert savings == pytest.approx(2.70)
