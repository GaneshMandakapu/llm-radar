"""Token pricing per 1M tokens (input_cost, output_cost) in USD."""

PRICING: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "o1": (15.00, 60.00),
    "o1-mini": (1.10, 4.40),
    "o3": (10.00, 40.00),
    "o3-mini": (1.10, 4.40),
    "o4-mini": (1.10, 4.40),
    # Anthropic
    "claude-opus-4": (15.00, 75.00),
    "claude-sonnet-4": (3.00, 15.00),
    "claude-haiku-4": (0.80, 4.00),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-5-haiku": (0.80, 4.00),
    "claude-3-opus": (15.00, 75.00),
    "claude-3-haiku": (0.25, 1.25),
    "claude-3-sonnet": (3.00, 15.00),
}


def calculate_cost_and_savings(model: str, input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> tuple[float, float]:
    model_lower = model.lower()

    input_cost, output_cost = 0.0, 0.0

    # Exact match
    if model_lower in PRICING:
        input_cost, output_cost = PRICING[model_lower]
    else:
        # Prefix match
        for key, (ic, oc) in PRICING.items():
            if model_lower.startswith(key):
                input_cost, output_cost = ic, oc
                break

    if input_cost == 0.0 and output_cost == 0.0:
        return 0.0, 0.0

    # Cache discount estimation
    # OpenAI is exactly 50% discount for cached input tokens
    # Anthropic is typically 90% discount for cached input tokens (e.g. $3.00 -> $0.30 for Sonnet)
    discount_factor = 0.9 if "claude" in model_lower else 0.5

    base_input_cost = (input_tokens + cached_tokens) * input_cost / 1_000_000
    base_output_cost = output_tokens * output_cost / 1_000_000

    savings = (cached_tokens * input_cost * discount_factor) / 1_000_000
    actual_cost = base_input_cost + base_output_cost - savings

    return actual_cost, savings

def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Legacy wrapper for backward compatibility."""
    cost, _ = calculate_cost_and_savings(model, input_tokens, output_tokens, 0)
    return cost
