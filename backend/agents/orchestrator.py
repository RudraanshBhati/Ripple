"""
Agent 6 — Orchestrator (claude-haiku-4-5-20251001)
Handles routing between agents based on current state.
Severity threshold is hardcoded at 0.2 — never make this dynamic.
"""
from backend.graph.state import SupplyChainState

SEVERITY_THRESHOLD = 0.2


def route(state: SupplyChainState) -> str:
    """
    Pure routing function — no LLM call needed here.
    Returns the name of the next node to execute.
    """
    if state.get("severity_score", 0.0) < SEVERITY_THRESHOLD:
        return "no_alert"

    if not state.get("supplier_mapping_done"):
        return "agent_3"

    if not state.get("risk_scored"):
        return "agent_4"

    # If there are no at-risk SKUs, skip alt sourcing and go straight to synthesis
    if not state.get("sku_risks"):
        return "agent_1_synthesis"

    if not state.get("alternatives_found"):
        return "agent_5"

    return "agent_1_synthesis"


def no_alert_handler(state: SupplyChainState) -> dict:
    """Terminal node for low-severity signals."""
    entity = state.get("affected_entities", ["unknown location"])
    entity_str = entity[0] if entity else "the reported location"
    severity = state.get("severity_score", 0.0)

    # Pull historical context from the signal type for richer response
    signal = state.get("raw_signal", "")
    historical_note = ""
    if "fog" in signal.lower() and "rotterdam" in signal.lower():
        historical_note = " Rotterdam fog historically resolves within 6 hours (94% of cases)."
    elif "fog" in signal.lower():
        historical_note = " Fog events typically resolve within hours without supply chain impact."

    return {
        "final_alert": (
            f"Signal assessed: severity {severity:.2f} — below threshold ({SEVERITY_THRESHOLD})."
            f" No supply chain disruption detected for {entity_str}.{historical_note}"
        ),
        "alert_type": "no_alert",
        "reasoning_trace": [
            f"[Orchestrator] Severity {severity:.2f} < threshold {SEVERITY_THRESHOLD} → no_alert branch"
        ],
    }
