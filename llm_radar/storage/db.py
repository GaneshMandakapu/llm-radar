import os
import uuid
import threading
from datetime import datetime, timedelta
from typing import Optional

import duckdb


CREATE_AB_TESTS_SQL = """
CREATE TABLE IF NOT EXISTS ab_tests (
    id          VARCHAR PRIMARY KEY,
    name        VARCHAR,
    variants    JSON NOT NULL,
    winner_cost VARCHAR,
    winner_latency VARCHAR,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS llm_calls (
    id          VARCHAR PRIMARY KEY,
    provider    VARCHAR NOT NULL,
    model       VARCHAR NOT NULL,
    input_tokens  INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    total_tokens  INTEGER DEFAULT 0,
    cost_usd    DOUBLE DEFAULT 0.0,
    latency_ms  DOUBLE DEFAULT 0.0,
    status      VARCHAR DEFAULT 'success',
    error_message VARCHAR,
    prompt_preview VARCHAR,
    response_preview VARCHAR,
    metadata    JSON,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class LLMStorage:
    def __init__(self, db_path: Optional[str] = None, max_calls: int = 1000, retention_hours: int = 24):
        self.max_calls = max_calls
        self.retention_hours = retention_hours
        self._lock = threading.Lock()

        if db_path is None:
            db_path = os.path.join(os.getcwd(), "llm_radar.duckdb")
        elif os.path.isdir(db_path):
            db_path = os.path.join(db_path, "llm_radar.duckdb")

        self.db_path = db_path

        # Use in-memory DB when auto-reload is active (avoids file locking)
        reload_env = os.environ.get("WEB_CONCURRENCY") or os.environ.get("WATCHFILES_FORCE_POLL")
        use_memory = bool(reload_env)

        try:
            self._conn = duckdb.connect(":memory:" if use_memory else db_path)
        except Exception:
            self._conn = duckdb.connect(":memory:")

        self._conn.execute(CREATE_TABLE_SQL)
        self._conn.execute(CREATE_AB_TESTS_SQL)

    def record(
        self,
        provider: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        latency_ms: float = 0.0,
        status: str = "success",
        error_message: Optional[str] = None,
        prompt_preview: Optional[str] = None,
        response_preview: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        import json
        call_id = str(uuid.uuid4())
        total_tokens = input_tokens + output_tokens

        with self._lock:
            self._conn.execute(
                """
                INSERT INTO llm_calls
                    (id, provider, model, input_tokens, output_tokens, total_tokens,
                     cost_usd, latency_ms, status, error_message,
                     prompt_preview, response_preview, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    call_id, provider, model, input_tokens, output_tokens, total_tokens,
                    cost_usd, latency_ms, status, error_message,
                    prompt_preview, response_preview,
                    json.dumps(metadata) if metadata else None,
                ],
            )
            self._enforce_limits()

        return call_id

    def _enforce_limits(self):
        cutoff = datetime.utcnow() - timedelta(hours=self.retention_hours)
        self._conn.execute("DELETE FROM llm_calls WHERE created_at < ?", [cutoff])

        count = self._conn.execute("SELECT COUNT(*) FROM llm_calls").fetchone()[0]
        if count > self.max_calls:
            excess = count - self.max_calls
            self._conn.execute(
                "DELETE FROM llm_calls WHERE id IN (SELECT id FROM llm_calls ORDER BY created_at ASC LIMIT ?)",
                [excess],
            )

    def get_calls(self, limit: int = 100, offset: int = 0, provider: Optional[str] = None, model: Optional[str] = None, status: Optional[str] = None):
        conditions = []
        params = []
        if provider:
            conditions.append("provider = ?")
            params.append(provider)
        if model:
            conditions.append("model = ?")
            params.append(model)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params.extend([limit, offset])

        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM llm_calls {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params,
            ).fetchall()
            cols = [d[0] for d in self._conn.description]

        return [dict(zip(cols, row)) for row in rows]

    def get_stats(self):
        with self._lock:
            totals = self._conn.execute(
                """
                SELECT
                    COUNT(*) as total_calls,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost_usd) as total_cost_usd,
                    AVG(latency_ms) as avg_latency_ms,
                    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error_count
                FROM llm_calls
                """
            ).fetchone()

            by_model = self._conn.execute(
                """
                SELECT model, provider,
                    COUNT(*) as calls,
                    SUM(total_tokens) as tokens,
                    SUM(cost_usd) as cost_usd,
                    AVG(latency_ms) as avg_latency_ms
                FROM llm_calls
                GROUP BY model, provider
                ORDER BY calls DESC
                """
            ).fetchall()

            timeline = self._conn.execute(
                """
                SELECT
                    strftime(created_at, '%Y-%m-%d %H:00:00') as hour,
                    COUNT(*) as calls,
                    SUM(cost_usd) as cost_usd
                FROM llm_calls
                WHERE created_at >= NOW() - INTERVAL 24 HOURS
                GROUP BY hour
                ORDER BY hour ASC
                """
            ).fetchall()

        return {
            "totals": {
                "calls": totals[0] or 0,
                "tokens": totals[1] or 0,
                "cost_usd": round(totals[2] or 0, 6),
                "avg_latency_ms": round(totals[3] or 0, 2),
                "errors": totals[4] or 0,
            },
            "by_model": [
                {"model": r[0], "provider": r[1], "calls": r[2], "tokens": r[3],
                 "cost_usd": round(r[4] or 0, 6), "avg_latency_ms": round(r[5] or 0, 2)}
                for r in by_model
            ],
            "timeline": [
                {"hour": str(r[0]), "calls": r[1], "cost_usd": round(r[2] or 0, 6)}
                for r in timeline
            ],
        }

    def record_ab_test(self, ab_result):
        import json
        winner_cost = ab_result.winner_by_cost
        winner_latency = ab_result.winner_by_latency
        with self._lock:
            self._conn.execute(
                "INSERT INTO ab_tests (id, name, variants, winner_cost, winner_latency) VALUES (?, ?, ?, ?, ?)",
                [
                    ab_result.test_id,
                    ab_result.name,
                    json.dumps([
                        {
                            "label": v.label, "provider": v.provider, "model": v.model,
                            "input_tokens": v.input_tokens, "output_tokens": v.output_tokens,
                            "cost_usd": v.cost_usd, "latency_ms": round(v.latency_ms, 2),
                            "status": v.status, "error": v.error_message,
                            "response_preview": v.response_text[:300] if v.response_text else None,
                        }
                        for v in ab_result.variants
                    ]),
                    winner_cost.label if winner_cost else None,
                    winner_latency.label if winner_latency else None,
                ],
            )

    def get_ab_tests(self, limit: int = 50, offset: int = 0):
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM ab_tests ORDER BY created_at DESC LIMIT ? OFFSET ?",
                [limit, offset],
            ).fetchall()
            cols = [d[0] for d in self._conn.description]
        result = []
        for row in rows:
            r = dict(zip(cols, row))
            r["created_at"] = str(r["created_at"])
            result.append(r)
        return result

    def export_calls(self, fmt: str = "json") -> str:
        import json, csv, io
        calls = self.get_calls(limit=10000)
        for c in calls:
            if c.get("created_at"):
                c["created_at"] = str(c["created_at"])
        if fmt == "json":
            return json.dumps(calls, indent=2)
        elif fmt == "csv":
            if not calls:
                return ""
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=calls[0].keys())
            writer.writeheader()
            writer.writerows(calls)
            return buf.getvalue()
        raise ValueError(f"Unknown format: {fmt}")
