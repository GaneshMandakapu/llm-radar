import time
import functools
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..storage.db import LLMStorage


def patch_ollama(storage: "LLMStorage"):
    try:
        import ollama
    except ImportError:
        return

    original_chat = ollama.chat

    @functools.wraps(original_chat)
    def patched_chat(*args, **kwargs):
        start = time.perf_counter()
        model = kwargs.get("model") or (args[0] if args else "unknown")
        messages = kwargs.get("messages", [])
        prompt_preview = ""
        if messages:
            last = next((m for m in reversed(messages) if m.get("role") == "user"), messages[-1])
            prompt_preview = str(last.get("content", ""))[:500]

        try:
            response = original_chat(*args, **kwargs)
            latency_ms = (time.perf_counter() - start) * 1000

            # Ollama returns eval_count (output tokens) and prompt_eval_count (input tokens)
            input_tokens = response.get("prompt_eval_count", 0) or 0
            output_tokens = response.get("eval_count", 0) or 0
            response_text = ""
            msg = response.get("message", {})
            if isinstance(msg, dict):
                response_text = str(msg.get("content", ""))[:500]

            from ..pricing import calculate_cost
            cost = calculate_cost(model, input_tokens, output_tokens)

            storage.record(
                provider="ollama",
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                latency_ms=latency_ms,
                status="success",
                prompt_preview=prompt_preview,
                response_preview=response_text,
            )
            return response

        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            storage.record(
                provider="ollama",
                model=model,
                latency_ms=latency_ms,
                status="error",
                error_message=str(exc)[:1000],
                prompt_preview=prompt_preview,
            )
            raise

    ollama.chat = patched_chat


def patch_ollama_async(storage: "LLMStorage"):
    try:
        import ollama
    except ImportError:
        return

    # Ollama async client
    original_achat = getattr(ollama.AsyncClient, "chat", None)
    if not original_achat:
        return

    @functools.wraps(original_achat)
    async def patched_achat(self_client, *args, **kwargs):
        start = time.perf_counter()
        model = kwargs.get("model") or (args[0] if args else "unknown")
        messages = kwargs.get("messages", [])
        prompt_preview = ""
        if messages:
            last = next((m for m in reversed(messages) if m.get("role") == "user"), messages[-1])
            prompt_preview = str(last.get("content", ""))[:500]

        try:
            response = await original_achat(self_client, *args, **kwargs)
            latency_ms = (time.perf_counter() - start) * 1000

            input_tokens = response.get("prompt_eval_count", 0) or 0
            output_tokens = response.get("eval_count", 0) or 0
            msg = response.get("message", {})
            response_text = str(msg.get("content", "") if isinstance(msg, dict) else "")[:500]

            from ..pricing import calculate_cost
            cost = calculate_cost(model, input_tokens, output_tokens)

            storage.record(
                provider="ollama",
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                latency_ms=latency_ms,
                status="success",
                prompt_preview=prompt_preview,
                response_preview=response_text,
            )
            return response

        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            storage.record(
                provider="ollama",
                model=model,
                latency_ms=latency_ms,
                status="error",
                error_message=str(exc)[:1000],
                prompt_preview=prompt_preview,
            )
            raise

    ollama.AsyncClient.chat = patched_achat
