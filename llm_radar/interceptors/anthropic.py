import time
import functools
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..storage.db import LLMStorage


def _extract_prompt_preview(messages: list) -> str:
    if not messages:
        return ""
    last_user = next((m for m in reversed(messages) if m.get("role") == "user"), messages[-1])
    content = last_user.get("content", "")
    if isinstance(content, list):
        content = " ".join(
            c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"
        )
    return str(content)[:500]


def patch_anthropic(storage: "LLMStorage"):
    try:
        import anthropic
    except ImportError:
        return

    original_create = anthropic.resources.messages.Messages.create

    @functools.wraps(original_create)
    def patched_create(self_client, *args, **kwargs):
        start = time.perf_counter()
        model = kwargs.get("model", "unknown")
        messages = kwargs.get("messages", [])
        prompt_preview = _extract_prompt_preview(messages)

        try:
            response = original_create(self_client, *args, **kwargs)
            latency_ms = (time.perf_counter() - start) * 1000

            usage = getattr(response, "usage", None)
            input_tokens = getattr(usage, "input_tokens", 0) or 0
            output_tokens = getattr(usage, "output_tokens", 0) or 0

            from ..pricing import calculate_cost
            cost = calculate_cost(model, input_tokens, output_tokens)

            response_preview = ""
            content = getattr(response, "content", [])
            if content:
                first = content[0]
                response_preview = str(getattr(first, "text", "") or "")[:500]

            storage.record(
                provider="anthropic",
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                latency_ms=latency_ms,
                status="success",
                prompt_preview=prompt_preview,
                response_preview=response_preview,
            )
            return response

        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            storage.record(
                provider="anthropic",
                model=model,
                latency_ms=latency_ms,
                status="error",
                error_message=str(exc)[:1000],
                prompt_preview=prompt_preview,
            )
            raise

    anthropic.resources.messages.Messages.create = patched_create


def patch_anthropic_async(storage: "LLMStorage"):
    try:
        import anthropic
    except ImportError:
        return

    original_create = anthropic.resources.messages.AsyncMessages.create

    @functools.wraps(original_create)
    async def patched_create(self_client, *args, **kwargs):
        start = time.perf_counter()
        model = kwargs.get("model", "unknown")
        messages = kwargs.get("messages", [])
        prompt_preview = _extract_prompt_preview(messages)

        try:
            response = await original_create(self_client, *args, **kwargs)
            latency_ms = (time.perf_counter() - start) * 1000

            usage = getattr(response, "usage", None)
            input_tokens = getattr(usage, "input_tokens", 0) or 0
            output_tokens = getattr(usage, "output_tokens", 0) or 0

            from ..pricing import calculate_cost
            cost = calculate_cost(model, input_tokens, output_tokens)

            response_preview = ""
            content = getattr(response, "content", [])
            if content:
                first = content[0]
                response_preview = str(getattr(first, "text", "") or "")[:500]

            storage.record(
                provider="anthropic",
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                latency_ms=latency_ms,
                status="success",
                prompt_preview=prompt_preview,
                response_preview=response_preview,
            )
            return response

        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            storage.record(
                provider="anthropic",
                model=model,
                latency_ms=latency_ms,
                status="error",
                error_message=str(exc)[:1000],
                prompt_preview=prompt_preview,
            )
            raise

    anthropic.resources.messages.AsyncMessages.create = patched_create
