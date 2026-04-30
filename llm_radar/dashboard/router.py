import os
from typing import Optional, Callable

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


def create_router(storage, dashboard_path: str = "/__llm_radar", auth_dependency: Optional[Callable] = None) -> APIRouter:
    deps = [Depends(auth_dependency)] if auth_dependency else []
    router = APIRouter(dependencies=deps)

    @router.get(dashboard_path, response_class=HTMLResponse, include_in_schema=False)
    async def dashboard():
        with open(os.path.join(STATIC_DIR, "index.html"), "r") as f:
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
        for call in calls:
            if call.get("created_at"):
                call["created_at"] = str(call["created_at"])
        return JSONResponse({"calls": calls, "limit": limit, "offset": offset})

    @router.get(dashboard_path + "/api/ab-tests")
    async def get_ab_tests(
        limit: int = Query(default=20, le=100),
        offset: int = Query(default=0),
    ):
        return JSONResponse({"tests": storage.get_ab_tests(limit=limit, offset=offset)})

    @router.get(dashboard_path + "/api/export")
    async def export_calls(fmt: str = Query(default="json", alias="format")):
        if fmt == "csv":
            data = storage.export_calls(fmt="csv")
            return PlainTextResponse(
                content=data,
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=llm_calls.csv"},
            )
        data = storage.export_calls(fmt="json")
        return PlainTextResponse(
            content=data,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=llm_calls.json"},
        )

    @router.post(dashboard_path + "/api/ingest")
    async def ingest_call(payload: dict):
        """Receive calls forwarded from Chrome extension."""
        storage.record(
            provider=payload.get("provider", "unknown"),
            model=payload.get("model", "unknown"),
            input_tokens=payload.get("inputTokens", 0),
            output_tokens=payload.get("outputTokens", 0),
            cost_usd=payload.get("costUsd", 0.0),
            latency_ms=payload.get("latencyMs", 0.0),
            status=payload.get("status", "success"),
            error_message=payload.get("errorMessage"),
            prompt_preview=payload.get("promptPreview"),
            response_preview=payload.get("responsePreview"),
            metadata={"source": "chrome-extension"},
        )
        return {"ok": True}

    @router.get(dashboard_path + "/api/health")
    async def health():
        return {"status": "ok", "version": "0.2.0"}

    return router
