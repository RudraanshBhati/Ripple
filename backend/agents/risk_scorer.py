"""
Agent 4 — Risk Scorer (claude-haiku-4-5-20251001)

Given affected_suppliers from Agent 3, this agent:
  1. Fetches SKU inventory data for each affected supplier
  2. Calculates runout date and gap_days (stock runway minus lead time)
  3. Pulls historical context from mem0 to calibrate confidence
  4. Produces a SKURisk entry for every at-risk SKU

Runout formula (from spec Section 7):
  available_stock = current_stock + in_transit_stock - safety_stock_threshold
  runout_days     = available_stock / daily_consumption_rate
  gap_days        = runout_days - current_lead_time_days   (negative = shortfall)
  risk_score      = clamp(1 - (runout_days / current_lead_time_days), 0, 1)
"""
import json
from datetime import datetime, timedelta
from anthropic import Anthropic
from langsmith import wrappers
from backend.storage import postgres_client
from backend.storage.mem0_client import search_memories
from backend.graph.state import SupplyChainState, SKURisk

client = wrappers.wrap_anthropic(Anthropic())
MODEL = "claude-haiku-4-5-20251001"

# --- Tool definitions ---

TOOLS = [
    {
        "name": "get_sku_data",
        "description": (
            "Fetch inventory and lead time data for all SKUs supplied by a given supplier. "
            "Returns current_stock, in_transit_stock, safety_stock_threshold, "
            "daily_consumption_rate, and current_lead_time_days."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "supplier_id": {
                    "type": "string",
                    "description": "Supplier ID (e.g. SUP-001)",
                }
            },
            "required": ["supplier_id"],
        },
    },
    {
        "name": "get_historical_context",
        "description": (
            "Search mem0 for historical disruption patterns relevant to this signal. "
            "Returns past event durations and outcomes to calibrate confidence."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query, e.g. 'Taiwan port strike lead time impact'",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "finish_scoring",
        "description": "Call this when all SKU risks have been calculated.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sku_risks": {
                    "type": "array",
                    "description": "List of SKURisk objects",
                    "items": {
                        "type": "object",
                        "properties": {
                            "sku_id": {"type": "string"},
                            "current_stock": {"type": "number"},
                            "daily_consumption": {"type": "number"},
                            "runout_days": {"type": "number"},
                            "lead_time_days": {"type": "number"},
                            "gap_days": {"type": "number"},
                            "risk_score": {"type": "number"},
                            "confidence": {"type": "number"},
                        },
                        "required": ["sku_id", "runout_days", "lead_time_days", "confidence"],
                    },
                },
                "disruption_days": {
                    "type": "number",
                    "description": (
                        "Additional lead time days caused by this disruption, extracted from "
                        "historical context (e.g. 14 if history says 'adds 14 days'). Use 0 if unknown."
                    ),
                },
                "historical_context": {
                    "type": "string",
                    "description": "Brief summary of relevant historical patterns found",
                },
            },
            "required": ["sku_risks", "disruption_days", "historical_context"],
        },
    },
]


# --- Tool execution ---

def _calculate_runout(row: dict) -> dict:
    """Apply the spec Section 7 runout formula."""
    stock = float(row.get("current_stock", 0))
    in_transit = float(row.get("in_transit_stock", 0))
    safety = float(row.get("safety_stock", row.get("safety_stock_threshold", 0)))
    rate = float(row.get("daily_consumption_rate", 1))
    lead_time = float(row.get("current_lead_time_days", row.get("standard_lead_time_days", 30)))

    available = stock + in_transit - safety
    runout_days = available / rate if rate > 0 else 999
    gap_days = runout_days - lead_time
    risk_score = max(0.0, min(1.0, 1.0 - (runout_days / lead_time))) if lead_time > 0 else 0.0

    return {
        "available_stock": available,
        "runout_days": round(runout_days, 1),
        "gap_days": round(gap_days, 1),
        "lead_time_days": lead_time,
        "risk_score": round(risk_score, 3),
    }


def _execute_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name == "get_sku_data":
        rows = postgres_client.get_skus_for_supplier(tool_input["supplier_id"])
        if not rows:
            return "[]"
        enriched = []
        for row in rows:
            calc = _calculate_runout(row)
            enriched.append({**row, **calc})
        return json.dumps(enriched, default=str)

    if tool_name == "get_historical_context":
        memories = search_memories(tool_input["query"], limit=3)
        if not memories:
            return "No historical context found."
        return json.dumps([m.get("memory", m.get("text", "")) for m in memories])

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


# --- Agent ---

def run(state: SupplyChainState) -> dict:
    affected_suppliers = state.get("affected_suppliers", [])
    raw_signal = state.get("raw_signal", "")
    trace = []

    if not affected_suppliers:
        trace.append("[Agent4] No affected suppliers — skipping risk scoring")
        return {
            "sku_risks": [],
            "historical_context": "",
            "risk_scored": True,
            "reasoning_trace": trace,
        }

    supplier_ids = [s["supplier_id"] for s in affected_suppliers if s.get("supplier_id")]
    trace.append(f"[Agent4] Scoring risk for suppliers: {supplier_ids}")

    system_prompt = (
        "You are a supply chain risk analyst calculating SKU runout risk.\n\n"
        "For each supplier:\n"
        "1. Call get_sku_data(supplier_id) to get inventory + lead time data\n"
        "2. Call get_historical_context with a relevant query to find past disruption patterns\n"
        "3. Call finish_scoring with all results\n\n"
        "From get_sku_data, use runout_days and lead_time_days — do NOT recalculate them.\n\n"
        "From get_historical_context, extract disruption_days: the number of additional days "
        "this type of disruption typically adds to lead times (e.g. if history says 'adds 14 days', "
        "disruption_days=14). Use 0 if no historical pattern found.\n\n"
        "Set confidence based on historical match quality: "
        "high (0.9) = strong historical match, medium (0.7) = partial, low (0.5) = no history.\n\n"
        "Pass runout_days, lead_time_days, confidence, and disruption_days to finish_scoring — "
        "gap_days and risk_score will be computed from these values in Python."
    )

    user_message = (
        f"Signal: {raw_signal}\n"
        f"Affected suppliers: {json.dumps(supplier_ids)}\n\n"
        "Calculate runout risk for all SKUs from these suppliers."
    )

    messages = [{"role": "user", "content": user_message}]
    finish_data = None
    iterations = 0

    while finish_data is None and iterations < 10:
        iterations += 1
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            break

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            if block.name == "finish_scoring":
                finish_data = block.input
                trace.append(
                    f"[Agent4] finish_scoring: {len(block.input.get('sku_risks', []))} SKUs at risk"
                )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": "Scoring recorded.",
                })
            else:
                result = _execute_tool(block.name, block.input)
                trace.append(f"[Agent4] {block.name}({block.input}) -> {result[:120]}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    # Build SKURisk list
    now = datetime.now()
    sku_risks: list[SKURisk] = []

    if finish_data:
        historical_context = finish_data.get("historical_context", "")
        disruption_days = float(finish_data.get("disruption_days", 0))
        trace.append(f"[Agent4] disruption_days from historical context: {disruption_days}")

        # Deduplicate: if same SKU appears from multiple suppliers, keep worst-case (highest risk_score)
        seen: dict[str, SKURisk] = {}
        for item in finish_data.get("sku_risks", []):
            runout_days = float(item.get("runout_days", 0))
            base_lead_time = float(item.get("lead_time_days", 0))
            effective_lead_time = base_lead_time + disruption_days
            gap_days = round(runout_days - effective_lead_time, 1)
            risk_score = round(max(0.0, min(1.0, 1.0 - runout_days / effective_lead_time)), 3) if effective_lead_time > 0 else 0.0
            runout_date = now + timedelta(days=runout_days)
            entry = SKURisk(
                sku_id=item["sku_id"],
                current_stock=int(item.get("current_stock", 0)),
                daily_consumption=float(item.get("daily_consumption", 0)),
                runout_date=runout_date,
                lead_time_days=int(effective_lead_time),
                gap_days=gap_days,
                risk_score=risk_score,
                confidence=float(item["confidence"]),
            )
            sku_id = item["sku_id"]
            if sku_id not in seen or risk_score > seen[sku_id]["risk_score"]:
                seen[sku_id] = entry

        sku_risks = list(seen.values())
        trace.append(f"[Agent4] Historical context: {historical_context[:100]}")
    else:
        historical_context = ""
        trace.append("[Agent4] WARNING: finish_scoring was never called")

    return {
        "sku_risks": sku_risks,
        "historical_context": historical_context,
        "risk_scored": True,
        "reasoning_trace": trace,
    }
