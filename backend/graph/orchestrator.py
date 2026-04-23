"""
Orchestrator — LLM supervisor node (claude-haiku-4-5-20251001)

Decides which agent to run next based on current pipeline state.
Severity < 0.2 short-circuits to no_alert without an LLM call.
"""
import json
from anthropic import Anthropic
from langsmith import wrappers
from dotenv import load_dotenv

from backend.graph.state import SupplyChainState

load_dotenv()

client = wrappers.wrap_anthropic(Anthropic())
MODEL = "claude-haiku-4-5-20251001"
SEVERITY_THRESHOLD = 0.2

VALID_AGENTS = {
    "signal_scraper",
    "supplier_mapping",
    "agent_4",
    "agent_5",
    "report_compiler",
    "no_alert",
    "END",
}

ROUTE_TOOL = {
    "name": "route",
    "description": "Choose the next agent to run in the supply chain pipeline.",
    "input_schema": {
        "type": "object",
        "properties": {
            "next_agent": {
                "type": "string",
                "enum": sorted(VALID_AGENTS),
                "description": "The next agent to invoke.",
            },
            "reason": {
                "type": "string",
                "description": "One-sentence reason for this routing decision.",
            },
        },
        "required": ["next_agent", "reason"],
    },
}

SYSTEM_PROMPT = """You are the routing supervisor for a supply chain intelligence pipeline.
Based on the current state, call the route tool with the next agent to run.

Routing rules (apply in order):
1. If raw_signal is empty or signal not yet parsed → route to signal_scraper
2. If severity_score > 0 and < 0.2 → route to no_alert
3. If supplier_mapping_done is false → route to supplier_mapping
4. If risk_scored is false → route to agent_4
5. If alternatives_requested is true and alternatives_found is false → route to agent_5
6. If final_alert is not set → route to report_compiler
7. Otherwise → END

Never skip a step. Always call the route tool — no prose response."""


def _build_state_summary(state: SupplyChainState) -> str:
    return json.dumps({
        "raw_signal": (state.get("raw_signal") or "")[:120],
        "severity_score": state.get("severity_score", 0.0),
        "signal_type": state.get("signal_type"),
        "affected_entities": state.get("affected_entities", []),
        "supplier_mapping_done": state.get("supplier_mapping_done", False),
        "affected_suppliers_count": len(state.get("affected_suppliers", [])),
        "risk_scored": state.get("risk_scored", False),
        "sku_risks_count": len(state.get("sku_risks", [])),
        "alternatives_requested": state.get("alternatives_requested", False),
        "alternatives_found": state.get("alternatives_found", False),
        "alternatives_count": len(state.get("alternatives", [])),
        "final_alert_set": bool(state.get("final_alert")),
        "pending_user_question": state.get("pending_user_question"),
    }, indent=2)


def orchestrate(state: SupplyChainState) -> dict:
    severity = state.get("severity_score", 0.0)

    # Pre-LLM severity guard
    if 0 < severity < SEVERITY_THRESHOLD:
        return {
            "next_agent": "no_alert",
            "reasoning_trace": [f"[Orchestrator] Severity {severity:.2f} < threshold — short-circuit to no_alert"],
        }

    state_summary = _build_state_summary(state)
    trace = []

    response = client.messages.create(
        model=MODEL,
        max_tokens=256,
        system=SYSTEM_PROMPT,
        tools=[ROUTE_TOOL],
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": f"Current pipeline state:\n{state_summary}"}],
    )

    next_agent = "END"
    for block in response.content:
        if block.type == "tool_use" and block.name == "route":
            chosen = block.input.get("next_agent", "END")
            reason = block.input.get("reason", "")
            next_agent = chosen if chosen in VALID_AGENTS else "END"
            trace.append(f"[Orchestrator] -> {next_agent}: {reason}")
            break

    if not trace:
        next_agent = "END"
        trace.append("[Orchestrator] No route tool call — defaulting to END")

    return {"next_agent": next_agent, "reasoning_trace": trace}


def no_alert_handler(state: SupplyChainState) -> dict:
    """Terminal node for low-severity signals."""
    entity = state.get("affected_entities", ["unknown location"])
    entity_str = entity[0] if entity else "the reported location"
    severity = state.get("severity_score", 0.0)

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
            f"[Orchestrator] Severity {severity:.2f} < threshold {SEVERITY_THRESHOLD} → no_alert"
        ],
    }
