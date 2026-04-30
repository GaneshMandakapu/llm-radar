"""
fastapi-radar plugin integration.

When both llm-radar and fastapi-radar are installed, this mounts the LLM
dashboard alongside fastapi-radar so both panels are accessible from the
same FastAPI app.

Usage:
    from fastapi_radar import Radar
    from llm_radar import LLMRadarPlugin

    app = FastAPI()
    radar = Radar(app)          # fastapi-radar
    llm = LLMRadarPlugin(app)   # llm-radar sits alongside it

    # fastapi-radar dashboard:  http://localhost:8000/__radar/
    # llm-radar dashboard:      http://localhost:8000/__llm_radar
"""

from typing import Optional, Callable

from .base import BasePlugin


class LLMRadarPlugin(BasePlugin):
    """
    Drop-in companion to fastapi-radar.
    Mounts LLM observability dashboard on the same FastAPI app.
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
    ):
        from ..core import LLMRadar

        self._radar = LLMRadar(
            app=app,
            dashboard_path=dashboard_path,
            max_calls=max_calls,
            retention_hours=retention_hours,
            db_path=db_path,
            auth_dependency=auth_dependency,
            track_openai=track_openai,
            track_anthropic=track_anthropic,
        )
        self.storage = self._radar.storage
        self.dashboard_path = dashboard_path

        if app is not None:
            self._inject_link(app, dashboard_path)

    def _inject_link(self, app, dashboard_path: str):
        """Add a startup log so devs know the LLM dashboard URL."""
        import logging
        logger = logging.getLogger("llm_radar")

        @app.on_event("startup")
        async def _llm_radar_startup():
            logger.info(f"LLM Radar dashboard: {dashboard_path}")
            print(f"\n  📡 LLM Radar → {dashboard_path}\n")

    def mount(self, app, dashboard_path: Optional[str] = None):
        self._radar.mount(app, dashboard_path)
