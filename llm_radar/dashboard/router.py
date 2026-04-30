import os
from typing import Optional, Callable

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


def create_router(storage, dashboard_path: str = "/__llm_radar", auth_dependency: Optional[Callable] = None) -> APIRouter:
    deps = [Depends(auth_dependency)] if auth_dependency else []
    router = APIRouter(dependencies=deps)

    @router.get(dashboard_path, response_class=HTMLResponse, include_in_schema=False)
    async def dashboard():
        html_path = os.path.join(STATIC_DIR, "index.html")
        with open(html_path, "r") as f:
            return HTMLResponse(content=f.read())

    @router.get(dashboard_path + "/api/stats")
    async def get_stats():
        return JSONResponse(storage.get_stats())

    @router.get(dashboard_path + "/api/calls")
    async def get_calls(
        limit: int = Query(default=50, le=500),
        offset: int = Query(default=0),
        provider: Optional[str] = Query(default=None),
        model: Optional[str] = Query(default=None),
        status: Optional[str] = Query(default=None),
    ):
        calls = storage.get_calls(limit=limit, offset=offset, provider=provider, model=model, status=status)
        # Convert datetime objects to strings for JSON serialization
        for call in calls:
            if call.get("created_at"):
                call["created_at"] = str(call["created_at"])
        return JSONResponse({"calls": calls, "limit": limit, "offset": offset})

    @router.get(dashboard_path + "/api/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    return router
