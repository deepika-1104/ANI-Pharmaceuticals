"""
Quality dashboard summary endpoint.

GET /api/quality-dashboard/summary
  Returns aggregated quality metrics for today, yesterday, and the last 9
  days, read directly from the `quality_dashboard` MongoDB collection.
  This mirrors the aggregation logic in useQualityData.js so the frontend
  no longer needs to ship or fetch the CSV.
"""

from datetime import date as _date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from database.mongodb import get_db

router = APIRouter()

_COLLECTION = "quality_dashboard"


# ── aggregation helper (mirrors useQualityData.js aggregateQualityDay) ─────────

def _aggregate_day(docs: list[dict]) -> dict | None:
    if not docs:
        return None

    first = docs[0]
    total  = len(docs)
    passes = sum(1 for d in docs if d.get("inspection_result") == "Pass")

    audits = []
    for n in (1, 2, 3):
        name = first.get(f"audit{n}_name", "")
        if name and name not in ("", "undefined", None):
            audits.append({
                "name":     name,
                "dept":     first.get(f"audit{n}_department", ""),
                "date":     first.get(f"audit{n}_date", ""),
                "priority": first.get(f"audit{n}_priority", ""),
            })

    return {
        "qualityPassRate":    passes / total * 100 if total else 0,
        "avgInspectionScore": sum(d.get("inspection_score", 0) for d in docs) / total,
        "totalInspected":     total,
        "passCount":          passes,
        "failCount":          total - passes,
        "openNcrs":           first.get("open_ncrs_count", 0),
        "capaPending":        first.get("capa_pending_count", 0),
        "capaCritical":       first.get("capa_critical_count", 0),
        "capaMajor":          first.get("capa_major_count", 0),
        "auditScore":         first.get("audit_score_pct", 0),
        "prevAuditScore":     first.get("previous_audit_score_pct", 0),
        "deviationCritical":  first.get("deviation_critical_count", 0),
        "deviationMajor":     first.get("deviation_major_count", 0),
        "deviationMinor":     first.get("deviation_minor_count", 0),
        "upcomingAudits":     audits,
    }


async def _fetch_day(coll, date_key: str) -> list[dict]:
    docs = []
    async for doc in coll.find({"record_date": date_key}, {"_id": 0}):
        docs.append(doc)
    return docs


# ── endpoint ────────────────────────────────────────────────────────────────────

@router.get("/quality-dashboard/summary")
async def quality_dashboard_summary(
    target_date: Optional[str] = Query(None, description="YYYY-MM-DD; defaults to today or latest available"),
):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    coll = db[_COLLECTION]

    # Get all distinct sorted dates present in the collection
    pipeline = [{"$group": {"_id": "$record_date"}}, {"$sort": {"_id": 1}}]
    dates: list[str] = [doc["_id"] async for doc in coll.aggregate(pipeline)]

    if not dates:
        raise HTTPException(status_code=404, detail=f"No documents found in '{_COLLECTION}'")

    today_str = _date.today().isoformat()

    if target_date:
        if target_date not in dates:
            raise HTTPException(status_code=404, detail=f"Date {target_date} not found in dataset")
        today_key = target_date
    elif today_str in dates:
        today_key = today_str
    else:
        today_key = dates[-1]

    today_idx     = dates.index(today_key)
    yesterday_key = dates[today_idx - 1] if today_idx > 0 else None
    last9_keys    = dates[max(0, today_idx - 8): today_idx + 1]

    # Fetch and aggregate
    today_docs     = await _fetch_day(coll, today_key)
    yesterday_docs = await _fetch_day(coll, yesterday_key) if yesterday_key else []

    last9 = []
    for dk in last9_keys:
        docs = await _fetch_day(coll, dk)
        agg  = _aggregate_day(docs)
        if agg:
            last9.append({**agg, "date": dk})

    return {
        "today":      _aggregate_day(today_docs),
        "yesterday":  _aggregate_day(yesterday_docs) if yesterday_docs else None,
        "last9":      last9,
        "latestDate": today_key,
    }


@router.get("/quality-dashboard/recent-inspections")
async def quality_recent_inspections(
    limit: int = Query(5, ge=1, le=50),
    reference_date: Optional[str] = Query(None, description="Return records on or before this date (YYYY-MM-DD). Defaults to today or latest available."),
):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    coll = db[_COLLECTION]

    if not reference_date:
        today_str = _date.today().isoformat()
        # Use the latest date that is <= today, matching the summary endpoint behaviour
        pipeline = [{"$group": {"_id": "$record_date"}}, {"$sort": {"_id": 1}}]
        dates: list[str] = [doc["_id"] async for doc in coll.aggregate(pipeline)]
        if dates:
            reference_date = today_str if today_str in dates else dates[-1]

    query = {"record_date": {"$lte": reference_date}} if reference_date else {}
    fields = {"_id": 0, "batch_id": 1, "product_name": 1, "inspection_stage": 1,
              "inspection_score": 1, "inspection_result": 1, "record_date": 1}
    docs = []
    async for doc in coll.find(query, fields).sort(
        [("record_date", -1), ("batch_id", 1)]
    ).limit(limit):
        docs.append(doc)
    return docs
