from typing import Optional, Callable

from .storage.db import LLMStorage
from .interceptors import (
    patch_openai, patch_openai_async,
    patch_anthropic, patch_anthropic_async,
    patch_ollama, patch_ollama_async,
    patch_gemini, patch_gemini_async,
)
from .ab_testing import ABTestEngine


class LLMRadar:
    """
    One-line LLM observability for FastAPI apps.

    Usage:
        radar = LLMRadar(app)

    Dashboard: http://localhost:8000/__llm_radar

    A/B test:
        result = radar.ab_test(
            messages=[{"role": "user", "content": "Hello"}],
            variants=[
                {"model": "gpt-4o-mini", "provider": "openai"},
                {"model": "claude-haiku-4-5-20251001", "provider": "anthropic"},
            ],
        )
    """

    def __init__(
        self,
        app=None,
        dashboard_path: str = "/__llm_radar",
        max_calls: int = 1000,
        retention_hours: int = 24,
        db_path: Optional[str] = None,
        auth_dependency: Optional[Callable] = None,
        track_openai: bool = True,
        track_anthropic: bool = True,
        track_ollama: bool = True,
        track_gemini: bool = True,
    ):
        self.dashboard_path = dashboard_path
        self.storage = LLMStorage(db_path=db_path, max_calls=max_calls, retention_hours=retention_hours)
        self._ab = ABTestEngine(self.storage)

        if track_openai:
            patch_openai(self.storage)
            patch_openai_async(self.storage)
        if track_anthropic:
            patch_anthropic(self.storage)
            patch_anthropic_async(self.storage)
        if track_ollama:
            patch_ollama(self.storage)
            patch_ollama_async(self.storage)
        if track_gemini:
            patch_gemini(self.storage)
            patch_gemini_async(self.storage)

        if app is not None:
            self._mount(app, dashboard_path, auth_dependency)

    def ab_test(self, messages: list, variants: list, name: Optional[str] = None, max_tokens: int = 512, **kwargs):
        """Run a synchronous A/B test across multiple models/providers."""
        return self._ab.run(messages=messages, variants=variants, name=name, max_tokens=max_tokens, **kwargs)

    async def ab_test_async(self, messages: list, variants: list, name: Optional[str] = None, max_tokens: int = 512, **kwargs):
        """Run a parallel async A/B test across multiple models/providers."""
        return await self._ab.run_async(messages=messages, variants=variants, name=name, max_tokens=max_tokens, **kwargs)

    def _mount(self, app, dashboard_path: str, auth_dependency: Optional[Callable]):
        from .dashboard.router import create_router
        router = create_router(self.storage, dashboard_path=dashboard_path, auth_dependency=auth_dependency)
        app.include_router(router)

    def mount(self, app, dashboard_path: Optional[str] = None, auth_dependency: Optional[Callable] = None):
        """Mount dashboard on a FastAPI app after init."""
        path = dashboard_path or self.dashboard_path
        self._mount(app, path, auth_dependency)
