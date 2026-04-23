"""
Agent 2 — Signal Scraper (claude-haiku-4-5-20251001)

Given raw_signal text, this agent:
  1. Classifies the signal type (port_strike, flooding, weather, geopolitical, etc.)
  2. Extracts affected geographic entities (cities, ports, regions, countries)
  3. Scores severity 0-1 using disruption type, scale, and historical mem0 patterns
  4. Populates state so the orchestrator can route to agent_3 or no_alert

Severity guidance:
  - Temporary weather (fog, light rain, short delays) → 0.05-0.18
  - Moderate weather / minor disruption                → 0.20-0.40
  - Flooding / infrastructure damage                   → 0.50-0.75
  - Port/labour strikes at major hubs                  → 0.70-0.90
  - Geopolitical closure / force majeure               → 0.80-1.00
"""
import json
from anthropic import Anthropic
from langsmith import wrappers
from backend.storage.mem0_client import search_memories
from backend.graph.state import SupplyChainState

client = wrappers.wrap_anthropic(Anthropic())
MODEL = "claude-haiku-4-5-20251001"

TOOLS = [
    {
        "name": "search_historical_signals",
        "description": (
            "Search mem0 for historical disruption events similar to this signal. "
            "Use this to calibrate severity — e.g. if history shows Rotterdam fog "
            "resolves in 6hrs with no supply impact, that informs a low score."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query, e.g. 'Rotterdam fog port delay historical impact'",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "finish_analysis",
        "description": "Report the final signal classification. Call once after searching historical context.",
        "input_schema": {
            "type": "object",
            "properties": {
                "signal_type": {
                    "type": "string",
                    "description": "Event category: port_strike | flooding | weather | geopolitical | fire | earthquake | other",
                },
                "severity_score": {
                    "type": "number",
                    "description": (
                        "0.0-1.0. Must reflect both disruption type AND historical resolution patterns. "
                        "Temporary weather that resolves in hours must stay below 0.20."
                    ),
                },
                "affected_entities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific place names: cities, ports, regions, countries (e.g. ['Zhengzhou', 'Henan', 'China'])",
                },
                "reasoning": {
                    "type": "string",
                    "description": "One sentence explaining the severity score.",
                },
            },
            "required": ["signal_type", "severity_score", "affected_entities", "reasoning"],
        },
    },
]


def _execute_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name == "search_historical_signals":
        memories = search_memories(tool_input["query"], limit=3)
        if not memories:
            return "No historical signal data found."
        return json.dumps([m.get("memory", m.get("text", "")) for m in memories])
    return json.dumps({"error": f"Unknown tool: {tool_name}"})


def run(state: SupplyChainState) -> dict:
    raw_signal = state.get("raw_signal", "")
    trace = []

    if not raw_signal:
        trace.append("[Agent2] No raw_signal in state — skipping")
        return {
            "signal_type": "unknown",
            "severity_score": 0.0,
            "affected_entities": [],
            "reasoning_trace": trace,
        }

    system_prompt = (
        "You are a supply chain signal analyst. Your job is to classify disruption signals "
        "and score their severity so downstream agents know whether to act.\n\n"
        "Steps:\n"
        "1. Call search_historical_signals to find past events of this type — "
        "use the results to calibrate your severity score against real precedent.\n"
        "2. Call finish_analysis with your final classification.\n\n"
        "Severity must be grounded in disruption impact on supply chains:\n"
        "- Short-lived weather (fog, light rain) that historically resolves in hours "
        "with no cargo impact → MUST score below 0.20\n"
        "- Infrastructure damage, strikes at major hubs, flooding → 0.50-0.90\n"
        "- Be specific about entities: extract city, region, AND country where possible."
    )

    messages = [{"role": "user", "content": f"Analyse this supply chain signal:\n\n{raw_signal}"}]
    finish_data = None
    iterations = 0

    while finish_data is None and iterations < 6:
        iterations += 1
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
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

            if block.name == "finish_analysis":
                finish_data = block.input
                trace.append(
                    f"[Agent2] classified: type={block.input['signal_type']} "
                    f"severity={block.input['severity_score']} "
                    f"entities={block.input['affected_entities']}"
                )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": "Analysis recorded.",
                })
            else:
                result = _execute_tool(block.name, block.input)
                trace.append(f"[Agent2] {block.name}({block.input}) -> {result[:120]}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    if finish_data:
        trace.append(f"[Agent2] reasoning: {finish_data.get('reasoning', '')}")
        return {
            "signal_type": finish_data["signal_type"],
            "severity_score": max(0.0, min(1.0, float(finish_data["severity_score"]))),
            "affected_entities": finish_data["affected_entities"],
            "reasoning_trace": trace,
        }

    trace.append("[Agent2] WARNING: finish_analysis was never called")
    return {
        "signal_type": "unknown",
        "severity_score": 0.0,
        "affected_entities": [],
        "reasoning_trace": trace,
    }
