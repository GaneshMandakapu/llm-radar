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
        content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
    return str(content)[:500]


def patch_openai(storage: "LLMStorage"):
    try:
        import openai
    except ImportError:
        return

    original_create = openai.resources.chat.completions.Completions.create

    @functools.wraps(original_create)
    def patched_create(self_client, *args, **kwargs):
        start = time.perf_counter()
        model = kwargs.get("model", "unknown")
        messages = kwargs.get("messages", [])
        prompt_preview = _extract_prompt_preview(messages)
        stream = kwargs.get("stream", False)

        # Force usage info for streams
        if stream and "stream_options" not in kwargs:
            kwargs["stream_options"] = {"include_usage": True}

        try:
            response = original_create(self_client, *args, **kwargs)
            
            if stream:
                def stream_wrapper():
                    response_text = ""
                    input_tokens = output_tokens = cached_tokens = 0
                    try:
                        for chunk in response:
                            # Extract text
                            if getattr(chunk, "choices", None):
                                delta = getattr(chunk.choices[0], "delta", None)
                                if delta and getattr(delta, "content", None):
                                    response_text += delta.content
                            # Extract usage
                            usage = getattr(chunk, "usage", None)
                            if usage:
                                input_tokens = getattr(usage, "prompt_tokens", input_tokens)
                                output_tokens = getattr(usage, "completion_tokens", output_tokens)
                                details = getattr(usage, "prompt_tokens_details", None)
                                if details:
                                    cached_tokens = getattr(details, "cached_tokens", cached_tokens)
                            yield chunk
                    finally:
                        latency_ms = (time.perf_counter() - start) * 1000
                        from ..pricing import calculate_cost_and_savings
                        cost, savings = calculate_cost_and_savings(model, input_tokens, output_tokens, cached_tokens)
                        storage.record(
                            provider="openai", model=model,
                            input_tokens=input_tokens, output_tokens=output_tokens, cached_tokens=cached_tokens,
                            cost_usd=cost, savings_usd=savings, latency_ms=latency_ms, status="success",
                            prompt_preview=prompt_preview, response_preview=response_text[:500]
                        )
                return stream_wrapper()

            # Non-streaming
            latency_ms = (time.perf_counter() - start) * 1000
            usage = getattr(response, "usage", None)
            input_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
            output_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
            cached_tokens = 0
            
            if usage:
                details = getattr(usage, "prompt_tokens_details", None)
                if details:
                    cached_tokens = getattr(details, "cached_tokens", 0)

            from ..pricing import calculate_cost_and_savings
            cost, savings = calculate_cost_and_savings(model, input_tokens, output_tokens, cached_tokens)

            response_preview = ""
            choices = getattr(response, "choices", [])
            if choices:
                msg = getattr(choices[0], "message", None)
                if msg:
                    response_preview = str(getattr(msg, "content", "") or "")[:500]

            storage.record(
                provider="openai", model=model,
                input_tokens=input_tokens, output_tokens=output_tokens, cached_tokens=cached_tokens,
                cost_usd=cost, savings_usd=savings, latency_ms=latency_ms, status="success",
                prompt_preview=prompt_preview, response_preview=response_preview,
            )
            return response

        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            storage.record(
                provider="openai", model=model, latency_ms=latency_ms, status="error",
                error_message=str(exc)[:1000], prompt_preview=prompt_preview,
            )
            raise

    openai.resources.chat.completions.Completions.create = patched_create


def patch_openai_async(storage: "LLMStorage"):
    try:
        import openai
    except ImportError:
        return

    original_create = openai.resources.chat.completions.AsyncCompletions.create

    @functools.wraps(original_create)
    async def patched_create(self_client, *args, **kwargs):
        start = time.perf_counter()
        model = kwargs.get("model", "unknown")
        messages = kwargs.get("messages", [])
        prompt_preview = _extract_prompt_preview(messages)
        stream = kwargs.get("stream", False)

        if stream and "stream_options" not in kwargs:
            kwargs["stream_options"] = {"include_usage": True}

        try:
            response = await original_create(self_client, *args, **kwargs)
            
            if stream:
                async def stream_wrapper():
                    response_text = ""
                    input_tokens = output_tokens = cached_tokens = 0
                    try:
                        async for chunk in response:
                            if getattr(chunk, "choices", None):
                                delta = getattr(chunk.choices[0], "delta", None)
                                if delta and getattr(delta, "content", None):
                                    response_text += delta.content
                            usage = getattr(chunk, "usage", None)
                            if usage:
                                input_tokens = getattr(usage, "prompt_tokens", input_tokens)
                                output_tokens = getattr(usage, "completion_tokens", output_tokens)
                                details = getattr(usage, "prompt_tokens_details", None)
                                if details:
                                    cached_tokens = getattr(details, "cached_tokens", cached_tokens)
                            yield chunk
                    finally:
                        latency_ms = (time.perf_counter() - start) * 1000
                        from ..pricing import calculate_cost_and_savings
                        cost, savings = calculate_cost_and_savings(model, input_tokens, output_tokens, cached_tokens)
                        storage.record(
                            provider="openai", model=model,
                            input_tokens=input_tokens, output_tokens=output_tokens, cached_tokens=cached_tokens,
                            cost_usd=cost, savings_usd=savings, latency_ms=latency_ms, status="success",
                            prompt_preview=prompt_preview, response_preview=response_text[:500]
                        )
                return stream_wrapper()

            # Non-streaming
            latency_ms = (time.perf_counter() - start) * 1000
            usage = getattr(response, "usage", None)
            input_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
            output_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
            cached_tokens = 0
            
            if usage:
                details = getattr(usage, "prompt_tokens_details", None)
                if details:
                    cached_tokens = getattr(details, "cached_tokens", 0)

            from ..pricing import calculate_cost_and_savings
            cost, savings = calculate_cost_and_savings(model, input_tokens, output_tokens, cached_tokens)

            response_preview = ""
            choices = getattr(response, "choices", [])
            if choices:
                msg = getattr(choices[0], "message", None)
                if msg:
                    response_preview = str(getattr(msg, "content", "") or "")[:500]

            storage.record(
                provider="openai", model=model,
                input_tokens=input_tokens, output_tokens=output_tokens, cached_tokens=cached_tokens,
                cost_usd=cost, savings_usd=savings, latency_ms=latency_ms, status="success",
                prompt_preview=prompt_preview, response_preview=response_preview,
            )
            return response

        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            storage.record(
                provider="openai", model=model, latency_ms=latency_ms, status="error",
                error_message=str(exc)[:1000], prompt_preview=prompt_preview,
            )
            raise

    openai.resources.chat.completions.AsyncCompletions.create = patched_create
