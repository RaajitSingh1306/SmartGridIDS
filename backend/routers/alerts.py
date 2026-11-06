from fastapi import APIRouter, Query
from backend import db

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
async def list_alerts(
    limit: int = Query(50, ge=1, le=500),
    severity: str | None = Query(None, description="Filter: LOW|MEDIUM|HIGH|CRITICAL"),
):
    return await db.get_alerts(limit=limit, severity=severity)


@router.get("/count")
async def alert_count():
    return {"count": await db.count_alerts()}


@router.delete("/clear")
@router.post("/clear")
async def clear_all():
    deleted = await db.clear_alerts()
    return {"deleted": deleted}
