"""
A/B testing engine for LLM calls.

Usage:
    result = radar.ab_test(
        messages=[{"role": "user", "content": "Explain quantum computing"}],
        variants=[
            {"model": "gpt-4o-mini", "provider": "openai"},
            {"model": "claude-haiku-4-5-20251001", "provider": "anthropic"},
        ],
        name="model-comparison-1",
    )
    print(result.winner_by_cost)
    print(result.winner_by_latency)
"""

import time
import uuid
from dataclasses import dataclass
from typing import Optional


@dataclass
class VariantResult:
    label: str
    provider: str
    model: str
    response_text: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float
    status: str
    error_message: Optional[str] = None
    call_id: Optional[str] = None


@dataclass
class ABTestResult:
    test_id: str
    name: str
    variants: list[VariantResult]

    @property
    def winner_by_cost(self) -> Optional[VariantResult]:
        successful = [v for v in self.variants if v.status == "success"]
        if not successful:
            return None
        return min(successful, key=lambda v: v.cost_usd)

    @property
    def winner_by_latency(self) -> Optional[VariantResult]:
        successful = [v for v in self.variants if v.status == "success"]
        if not successful:
            return None
        return min(successful, key=lambda v: v.latency_ms)

    def summary(self) -> dict:
        return {
            "test_id": self.test_id,
            "name": self.name,
            "variants": [
                {
                    "label": v.label,
                    "provider": v.provider,
                    "model": v.model,
                    "input_tokens": v.input_tokens,
                    "output_tokens": v.output_tokens,
                    "cost_usd": v.cost_usd,
                    "latency_ms": round(v.latency_ms, 2),
                    "status": v.status,
                    "error": v.error_message,
                    "response_preview": v.response_text[:300] if v.response_text else None,
                }
                for v in self.variants
            ],
            "winner_by_cost": self.winner_by_cost.label if self.winner_by_cost else None,
            "winner_by_latency": self.winner_by_latency.label if self.winner_by_latency else None,
        }


class ABTestEngine:
    def __init__(self, storage):
        self.storage = storage

    def run(
        self,
        messages: list,
        variants: list[dict],
        name: Optional[str] = None,
        max_tokens: int = 512,
        **shared_kwargs,
    ) -> ABTestResult:
        test_id = str(uuid.uuid4())[:8]
        name = name or f"ab-test-{test_id}"
        results = []

        for i, variant in enumerate(variants):
            label = variant.get("label") or chr(ord("A") + i)
            provider = variant.get("provider", "openai")
            model = variant.get("model", "gpt-4o-mini")

            result = self._run_variant(
                label=label,
                provider=provider,
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                extra_kwargs={k: v for k, v in variant.items() if k not in ("label", "provider", "model")},
                shared_kwargs=shared_kwargs,
            )
            results.append(result)

        ab_result = ABTestResult(test_id=test_id, name=name, variants=results)

        # Persist to storage
        self.storage.record_ab_test(ab_result)

        return ab_result

    async def run_async(
        self,
        messages: list,
        variants: list[dict],
        name: Optional[str] = None,
        max_tokens: int = 512,
        **shared_kwargs,
    ) -> ABTestResult:
        import asyncio

        test_id = str(uuid.uuid4())[:8]
        name = name or f"ab-test-{test_id}"

        tasks = []
        for i, variant in enumerate(variants):
            label = variant.get("label") or chr(ord("A") + i)
            provider = variant.get("provider", "openai")
            model = variant.get("model", "gpt-4o-mini")
            tasks.append(
                self._run_variant_async(
                    label=label,
                    provider=provider,
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    extra_kwargs={k: v for k, v in variant.items() if k not in ("label", "provider", "model")},
                    shared_kwargs=shared_kwargs,
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=False)
        ab_result = ABTestResult(test_id=test_id, name=name, variants=list(results))
        self.storage.record_ab_test(ab_result)
        return ab_result

    def _run_variant(self, label, provider, model, messages, max_tokens, extra_kwargs, shared_kwargs) -> VariantResult:
        from .pricing import calculate_cost

        start = time.perf_counter()
        try:
            if provider == "openai":
                import openai
                client = openai.OpenAI()
                resp = client.chat.completions.create(
                    model=model, messages=messages, max_tokens=max_tokens,
                    **extra_kwargs, **shared_kwargs
                )
                latency_ms = (time.perf_counter() - start) * 1000
                usage = resp.usage
                input_tokens = usage.prompt_tokens or 0
                output_tokens = usage.completion_tokens or 0
                response_text = resp.choices[0].message.content or ""

            elif provider == "anthropic":
                import anthropic
                client = anthropic.Anthropic()
                resp = client.messages.create(
                    model=model, messages=messages, max_tokens=max_tokens,
                    **extra_kwargs, **shared_kwargs
                )
                latency_ms = (time.perf_counter() - start) * 1000
                input_tokens = resp.usage.input_tokens or 0
                output_tokens = resp.usage.output_tokens or 0
                response_text = resp.content[0].text if resp.content else ""

            elif provider == "ollama":
                import ollama as ol
                resp = ol.chat(model=model, messages=messages, **extra_kwargs)
                latency_ms = (time.perf_counter() - start) * 1000
                input_tokens = resp.get("prompt_eval_count", 0)
                output_tokens = resp.get("eval_count", 0)
                response_text = resp["message"]["content"]

            else:
                raise ValueError(f"Unsupported provider: {provider}")

            cost = calculate_cost(model, input_tokens, output_tokens)
            return VariantResult(
                label=label, provider=provider, model=model,
                response_text=response_text, input_tokens=input_tokens,
                output_tokens=output_tokens, cost_usd=cost,
                latency_ms=latency_ms, status="success",
            )

        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            return VariantResult(
                label=label, provider=provider, model=model,
                response_text="", input_tokens=0, output_tokens=0,
                cost_usd=0.0, latency_ms=latency_ms,
                status="error", error_message=str(exc)[:500],
            )

    async def _run_variant_async(self, label, provider, model, messages, max_tokens, extra_kwargs, shared_kwargs) -> VariantResult:
        from .pricing import calculate_cost

        start = time.perf_counter()
        try:
            if provider == "openai":
                import openai
                client = openai.AsyncOpenAI()
                resp = await client.chat.completions.create(
                    model=model, messages=messages, max_tokens=max_tokens,
                    **extra_kwargs, **shared_kwargs
                )
                latency_ms = (time.perf_counter() - start) * 1000
                input_tokens = resp.usage.prompt_tokens or 0
                output_tokens = resp.usage.completion_tokens or 0
                response_text = resp.choices[0].message.content or ""

            elif provider == "anthropic":
                import anthropic
                client = anthropic.AsyncAnthropic()
                resp = await client.messages.create(
                    model=model, messages=messages, max_tokens=max_tokens,
                    **extra_kwargs, **shared_kwargs
                )
                latency_ms = (time.perf_counter() - start) * 1000
                input_tokens = resp.usage.input_tokens or 0
                output_tokens = resp.usage.output_tokens or 0
                response_text = resp.content[0].text if resp.content else ""

            else:
                raise ValueError(f"Async not supported for provider: {provider}")

            cost = calculate_cost(model, input_tokens, output_tokens)
            return VariantResult(
                label=label, provider=provider, model=model,
                response_text=response_text, input_tokens=input_tokens,
                output_tokens=output_tokens, cost_usd=cost,
                latency_ms=latency_ms, status="success",
            )

        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            return VariantResult(
                label=label, provider=provider, model=model,
                response_text="", input_tokens=0, output_tokens=0,
                cost_usd=0.0, latency_ms=latency_ms,
                status="error", error_message=str(exc)[:500],
            )
