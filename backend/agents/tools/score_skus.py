"""
Pure-Python SKU runout scorer — no LLM.
Applies the spec Section 7 formula across all affected suppliers.
"""
import re
from datetime import datetime, timedelta

from backend.storage import postgres_client
from backend.storage.mem0_client import search_memories
from backend.graph.state import SKURisk


def _calculate_runout(row: dict, disruption_days: float = 0.0) -> dict:
    stock = float(row.get("current_stock", 0))
    in_transit = float(row.get("in_transit_stock", 0))
    safety = float(row.get("safety_stock", row.get("safety_stock_threshold", 0)))
    rate = float(row.get("daily_consumption_rate", 1))
    base_lead = float(row.get("current_lead_time_days", row.get("standard_lead_time_days", 30)))
    effective_lead = base_lead + disruption_days

    available = stock + in_transit - safety
    runout_days = round(available / rate, 1) if rate > 0 else 999.0
    gap_days = round(runout_days - effective_lead, 1)
    risk_score = round(max(0.0, min(1.0, 1.0 - runout_days / effective_lead)), 3) if effective_lead > 0 else 0.0

    return {
        "runout_days": runout_days,
        "gap_days": gap_days,
        "lead_time_days": effective_lead,
        "risk_score": risk_score,
    }


def _extract_disruption_days(text: str) -> float:
    """Heuristic: find the largest 'N days' mention in historical context."""
    matches = re.findall(r"(\d+)\s*days?", text, re.IGNORECASE)
    return float(max((int(d) for d in matches), default=0))


def score_skus(affected_suppliers: list[dict], raw_signal: str) -> tuple[list[SKURisk], str]:
    """
    Score SKU runout risk for all affected suppliers.
    Returns (sku_risks, historical_context_summary).
    """
    now = datetime.now()

    memories = search_memories(raw_signal[:200], limit=3)
    historical_context = ""
    disruption_days = 0.0

    if memories:
        snippets = [m.get("memory", m.get("text", "")) for m in memories if m.get("memory") or m.get("text")]
        historical_context = " | ".join(snippets)
        disruption_days = _extract_disruption_days(historical_context)
        confidence = 0.9 if disruption_days > 0 else 0.7
    else:
        confidence = 0.5

    seen: dict[str, SKURisk] = {}

    for supplier in affected_suppliers:
        supplier_id = supplier.get("supplier_id")
        if not supplier_id:
            continue

        rows = postgres_client.get_skus_for_supplier(supplier_id)
        for row in rows:
            calc = _calculate_runout(row, disruption_days)
            sku_id = row["sku_id"]
            entry = SKURisk(
                sku_id=sku_id,
                current_stock=int(row.get("current_stock", 0)),
                daily_consumption=float(row.get("daily_consumption_rate", 0)),
                runout_date=now + timedelta(days=calc["runout_days"]),
                lead_time_days=int(calc["lead_time_days"]),
                gap_days=calc["gap_days"],
                risk_score=calc["risk_score"],
                confidence=confidence,
            )
            if sku_id not in seen or calc["risk_score"] > seen[sku_id]["risk_score"]:
                seen[sku_id] = entry

    return list(seen.values()), historical_context
