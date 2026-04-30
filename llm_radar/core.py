from typing import Optional, Callable

from .storage.db import LLMStorage
from .interceptors import patch_openai, patch_openai_async, patch_anthropic, patch_anthropic_async


class LLMRadar:
    """
    One-line LLM observability for FastAPI apps.

    Usage:
        radar = LLMRadar(app)

    Dashboard: http://localhost:8000/__llm_radar
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
        track_openai_async: bool = True,
        track_anthropic_async: bool = True,
    ):
        self.dashboard_path = dashboard_path
        self.storage = LLMStorage(db_path=db_path, max_calls=max_calls, retention_hours=retention_hours)

        if track_openai:
            patch_openai(self.storage)
        if track_openai_async:
            patch_openai_async(self.storage)
        if track_anthropic:
            patch_anthropic(self.storage)
        if track_anthropic_async:
            patch_anthropic_async(self.storage)

        if app is not None:
            self._mount(app, dashboard_path, auth_dependency)

    def _mount(self, app, dashboard_path: str, auth_dependency: Optional[Callable]):
        from .dashboard.router import create_router
        router = create_router(self.storage, dashboard_path=dashboard_path, auth_dependency=auth_dependency)
        app.include_router(router)

    def mount(self, app, dashboard_path: Optional[str] = None, auth_dependency: Optional[Callable] = None):
        """Mount dashboard on a FastAPI app after init."""
        path = dashboard_path or self.dashboard_path
        self._mount(app, path, auth_dependency)
