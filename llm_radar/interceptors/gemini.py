import time
import functools
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..storage.db import LLMStorage


# Gemini pricing per 1M tokens (input, output) in USD
GEMINI_PRICING = {
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash": (0.075, 0.30),
    "gemini-2.0-flash": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-1.0-pro": (0.50, 1.50),
}


def _gemini_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    model_lower = model.lower()
    for key, (in_cost, out_cost) in GEMINI_PRICING.items():
        if model_lower.startswith(key) or key in model_lower:
            return (input_tokens * in_cost + output_tokens * out_cost) / 1_000_000
    return 0.0


def patch_gemini(storage: "LLMStorage"):
    try:
        import google.generativeai as genai
    except ImportError:
        return

    original_generate = genai.GenerativeModel.generate_content

    @functools.wraps(original_generate)
    def patched_generate(self_model, *args, **kwargs):
        start = time.perf_counter()
        model_name = getattr(self_model, "model_name", "gemini-unknown")

        prompt_text = ""
        if args:
            content = args[0]
            if isinstance(content, str):
                prompt_text = content[:500]
            elif isinstance(content, list):
                prompt_text = str(content[0])[:500]

        try:
            response = original_generate(self_model, *args, **kwargs)
            latency_ms = (time.perf_counter() - start) * 1000

            usage = getattr(response, "usage_metadata", None)
            input_tokens = getattr(usage, "prompt_token_count", 0) or 0
            output_tokens = getattr(usage, "candidates_token_count", 0) or 0

            response_text = ""
            try:
                response_text = response.text[:500]
            except Exception:
                pass

            cost = _gemini_cost(model_name, input_tokens, output_tokens)

            storage.record(
                provider="gemini",
                model=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                latency_ms=latency_ms,
                status="success",
                prompt_preview=prompt_text,
                response_preview=response_text,
            )
            return response

        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            storage.record(
                provider="gemini",
                model=model_name,
                latency_ms=latency_ms,
                status="error",
                error_message=str(exc)[:1000],
                prompt_preview=prompt_text,
            )
            raise

    genai.GenerativeModel.generate_content = patched_generate


def patch_gemini_async(storage: "LLMStorage"):
    try:
        import google.generativeai as genai
    except ImportError:
        return

    original_generate_async = genai.GenerativeModel.generate_content_async

    @functools.wraps(original_generate_async)
    async def patched_generate_async(self_model, *args, **kwargs):
        start = time.perf_counter()
        model_name = getattr(self_model, "model_name", "gemini-unknown")

        prompt_text = ""
        if args:
            content = args[0]
            if isinstance(content, str):
                prompt_text = content[:500]
            elif isinstance(content, list):
                prompt_text = str(content[0])[:500]

        try:
            response = await original_generate_async(self_model, *args, **kwargs)
            latency_ms = (time.perf_counter() - start) * 1000

            usage = getattr(response, "usage_metadata", None)
            input_tokens = getattr(usage, "prompt_token_count", 0) or 0
            output_tokens = getattr(usage, "candidates_token_count", 0) or 0

            response_text = ""
            try:
                response_text = response.text[:500]
            except Exception:
                pass

            cost = _gemini_cost(model_name, input_tokens, output_tokens)

            storage.record(
                provider="gemini",
                model=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                latency_ms=latency_ms,
                status="success",
                prompt_preview=prompt_text,
                response_preview=response_text,
            )
            return response

        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            storage.record(
                provider="gemini",
                model=model_name,
                latency_ms=latency_ms,
                status="error",
                error_message=str(exc)[:1000],
                prompt_preview=prompt_text,
            )
            raise

    genai.GenerativeModel.generate_content_async = patched_generate_async
