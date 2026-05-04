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
        stream = kwargs.get("stream", False)

        try:
            response = original_create(self_client, *args, **kwargs)
            
            if stream:
                def stream_wrapper():
                    response_text = ""
                    input_tokens = output_tokens = cached_tokens = 0
                    try:
                        for chunk in response:
                            ctype = getattr(chunk, "type", None)
                            
                            if ctype == "message_start":
                                msg = getattr(chunk, "message", None)
                                usage = getattr(msg, "usage", None) if msg else None
                                if usage:
                                    input_tokens = getattr(usage, "input_tokens", input_tokens)
                                    # cache_read_input_tokens represents prompt caching discount
                                    cached_tokens = getattr(usage, "cache_read_input_tokens", cached_tokens)
                            
                            elif ctype == "content_block_delta":
                                delta = getattr(chunk, "delta", None)
                                if delta and getattr(delta, "text", None):
                                    response_text += delta.text
                                    
                            elif ctype == "message_delta":
                                usage = getattr(chunk, "usage", None)
                                if usage:
                                    output_tokens = getattr(usage, "output_tokens", output_tokens)
                                    
                            yield chunk
                    finally:
                        latency_ms = (time.perf_counter() - start) * 1000
                        from ..pricing import calculate_cost_and_savings
                        cost, savings = calculate_cost_and_savings(model, input_tokens, output_tokens, cached_tokens)
                        storage.record(
                            provider="anthropic", model=model,
                            input_tokens=input_tokens, output_tokens=output_tokens, cached_tokens=cached_tokens,
                            cost_usd=cost, savings_usd=savings, latency_ms=latency_ms, status="success",
                            prompt_preview=prompt_preview, response_preview=response_text[:500]
                        )
                return stream_wrapper()

            # Non-streaming
            latency_ms = (time.perf_counter() - start) * 1000
            usage = getattr(response, "usage", None)
            input_tokens = getattr(usage, "input_tokens", 0) if usage else 0
            output_tokens = getattr(usage, "output_tokens", 0) if usage else 0
            cached_tokens = getattr(usage, "cache_read_input_tokens", 0) if usage else 0

            from ..pricing import calculate_cost_and_savings
            cost, savings = calculate_cost_and_savings(model, input_tokens, output_tokens, cached_tokens)

            response_preview = ""
            content = getattr(response, "content", [])
            if content:
                first = content[0]
                response_preview = str(getattr(first, "text", "") or "")[:500]

            storage.record(
                provider="anthropic", model=model,
                input_tokens=input_tokens, output_tokens=output_tokens, cached_tokens=cached_tokens,
                cost_usd=cost, savings_usd=savings, latency_ms=latency_ms, status="success",
                prompt_preview=prompt_preview, response_preview=response_preview,
            )
            return response

        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            storage.record(
                provider="anthropic", model=model, latency_ms=latency_ms, status="error",
                error_message=str(exc)[:1000], prompt_preview=prompt_preview,
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
        stream = kwargs.get("stream", False)

        try:
            response = await original_create(self_client, *args, **kwargs)
            
            if stream:
                async def stream_wrapper():
                    response_text = ""
                    input_tokens = output_tokens = cached_tokens = 0
                    try:
                        async for chunk in response:
                            ctype = getattr(chunk, "type", None)
                            
                            if ctype == "message_start":
                                msg = getattr(chunk, "message", None)
                                usage = getattr(msg, "usage", None) if msg else None
                                if usage:
                                    input_tokens = getattr(usage, "input_tokens", input_tokens)
                                    cached_tokens = getattr(usage, "cache_read_input_tokens", cached_tokens)
                            
                            elif ctype == "content_block_delta":
                                delta = getattr(chunk, "delta", None)
                                if delta and getattr(delta, "text", None):
                                    response_text += delta.text
                                    
                            elif ctype == "message_delta":
                                usage = getattr(chunk, "usage", None)
                                if usage:
                                    output_tokens = getattr(usage, "output_tokens", output_tokens)
                                    
                            yield chunk
                    finally:
                        latency_ms = (time.perf_counter() - start) * 1000
                        from ..pricing import calculate_cost_and_savings
                        cost, savings = calculate_cost_and_savings(model, input_tokens, output_tokens, cached_tokens)
                        storage.record(
                            provider="anthropic", model=model,
                            input_tokens=input_tokens, output_tokens=output_tokens, cached_tokens=cached_tokens,
                            cost_usd=cost, savings_usd=savings, latency_ms=latency_ms, status="success",
                            prompt_preview=prompt_preview, response_preview=response_text[:500]
                        )
                return stream_wrapper()

            # Non-streaming
            latency_ms = (time.perf_counter() - start) * 1000
            usage = getattr(response, "usage", None)
            input_tokens = getattr(usage, "input_tokens", 0) if usage else 0
            output_tokens = getattr(usage, "output_tokens", 0) if usage else 0
            cached_tokens = getattr(usage, "cache_read_input_tokens", 0) if usage else 0

            from ..pricing import calculate_cost_and_savings
            cost, savings = calculate_cost_and_savings(model, input_tokens, output_tokens, cached_tokens)

            response_preview = ""
            content = getattr(response, "content", [])
            if content:
                first = content[0]
                response_preview = str(getattr(first, "text", "") or "")[:500]

            storage.record(
                provider="anthropic", model=model,
                input_tokens=input_tokens, output_tokens=output_tokens, cached_tokens=cached_tokens,
                cost_usd=cost, savings_usd=savings, latency_ms=latency_ms, status="success",
                prompt_preview=prompt_preview, response_preview=response_preview,
            )
            return response

        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            storage.record(
                provider="anthropic", model=model, latency_ms=latency_ms, status="error",
                error_message=str(exc)[:1000], prompt_preview=prompt_preview,
            )
            raise

    anthropic.resources.messages.AsyncMessages.create = patched_create
