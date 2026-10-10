"""Async SQLite alert log via aiosqlite."""

import aiosqlite
from pathlib import Path
from datetime import datetime
from backend.config import settings


DB_PATH = settings.db_path

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL,
    severity        TEXT    NOT NULL,
    ensemble_score  REAL    NOT NULL,
    top_feature     TEXT    NOT NULL,
    top_shap_value  REAL    NOT NULL,
    packet_rate     REAL    NOT NULL,
    data_volume     REAL    NOT NULL,
    requests_sm     REAL    NOT NULL,
    latency_ms      REAL    NOT NULL
)
"""


async def init_db() -> None:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_TABLE)
        await db.commit()


async def insert_alert(result: dict, record: dict) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO alerts
               (timestamp, severity, ensemble_score, top_feature, top_shap_value,
                packet_rate, data_volume, requests_sm, latency_ms)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                datetime.utcnow().isoformat(),
                result["severity"],
                result["ensemble_score"],
                result["top_feature"],
                result["top_shap_value"],
                record["Packet_Transmission_Rate_pps"],
                record["Data_Volume_KBps"],
                record["Requests_per_SM"],
                record["Network_Latency_ms"],
            ),
        )
        await db.commit()
        return cur.lastrowid


async def get_alerts(limit: int = 50, severity: str | None = None) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if severity:
            cur = await db.execute(
                "SELECT * FROM alerts WHERE severity=? ORDER BY id DESC LIMIT ?",
                (severity.upper(), limit),
            )
        else:
            cur = await db.execute(
                "SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)
            )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def count_alerts() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM alerts")
        row = await cur.fetchone()
        return row[0] if row else 0


async def clear_alerts() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM alerts")
        await db.commit()
        return cur.rowcount
