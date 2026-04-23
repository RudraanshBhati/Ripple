"""
Agent 3 — Supplier Mapping (claude-haiku-4-5-20251001)

Given a list of affected_entities (locations/names) from the signal scraper,
this agent:
  1. Finds tier-1 suppliers at the affected location
  2. Traverses SOURCES_FROM*1..3 to surface invisible tier-2/3 exposure
  3. Checks port risk for suppliers that ship through affected ports
  4. Populates affected_suppliers, tier2_exposure, invisible_risk

The SOURCES_FROM traversal is the demo wow moment — a Dutch supplier
(DutchParts BV) is flagged as at-risk because its tier-2 sub-supplier
(SinoRaw Ltd) is in Zhengzhou.
"""
import json
from anthropic import Anthropic
from langsmith import wrappers
from backend.storage import neo4j_client
from backend.graph.state import SupplyChainState

client = wrappers.wrap_anthropic(Anthropic())
MODEL = "claude-haiku-4-5-20251001"

# --- Tool definitions ---

TOOLS = [
    {
        "name": "find_direct_suppliers",
        "description": (
            "Find tier-1 suppliers directly located at or associated with a given "
            "city, country, or entity name. Use this first for any affected location."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "City, country, or supplier name to search for",
                }
            },
            "required": ["entity_name"],
        },
    },
    {
        "name": "traverse_tier2_suppliers",
        "description": (
            "Traverse the supplier graph up to 3 hops via SOURCES_FROM edges to find "
            "all downstream suppliers that depend on the given supplier as a sub-supplier. "
            "Use this for every supplier found at an affected location to uncover "
            "invisible tier-2 and tier-3 risk exposure."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "supplier_name": {
                    "type": "string",
                    "description": "Exact name of the supplier to traverse from",
                }
            },
            "required": ["supplier_name"],
        },
    },
    {
        "name": "check_port_risk",
        "description": (
            "Check for active risk events affecting a named port. "
            "Use this when the signal mentions a port disruption."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "port_name": {
                    "type": "string",
                    "description": "Name of the port to check (e.g. 'Keelung', 'Rotterdam')",
                }
            },
            "required": ["port_name"],
        },
    },
    {
        "name": "finish_mapping",
        "description": (
            "Call this when you have completed supplier mapping. "
            "Provide the full list of affected suppliers and your assessment."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "affected_suppliers": {
                    "type": "array",
                    "description": "List of affected supplier objects with fields: supplier_id, name, country, tier, exposure_type (direct|tier2|tier3|port)",
                    "items": {"type": "object"},
                },
                "tier2_exposure": {
                    "type": "boolean",
                    "description": "True if any tier-2 or deeper invisible risk was found",
                },
                "invisible_risk": {
                    "type": "boolean",
                    "description": "True if a supplier appears safe but is exposed via sub-supplier",
                },
                "reasoning": {
                    "type": "string",
                    "description": "One-sentence summary of the mapping finding",
                },
            },
            "required": ["affected_suppliers", "tier2_exposure", "invisible_risk", "reasoning"],
        },
    },
]


# --- Tool execution ---

def _execute_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name == "find_direct_suppliers":
        results = neo4j_client.find_direct_suppliers(tool_input["entity_name"])
        return json.dumps(results) if results else "[]"

    if tool_name == "traverse_tier2_suppliers":
        results = neo4j_client.traverse_tier2_suppliers(tool_input["supplier_name"])
        return json.dumps(results) if results else "[]"

    if tool_name == "check_port_risk":
        results = neo4j_client.get_port_risk(tool_input["port_name"])
        return json.dumps(results) if results else "[]"

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


# --- Agent ---

def run(state: SupplyChainState) -> dict:
    entities = state.get("affected_entities", [])
    raw_signal = state.get("raw_signal", "")
    trace = []

    if not entities:
        trace.append("[Agent3] No affected entities — skipping supplier mapping")
        return {
            "affected_suppliers": [],
            "tier2_exposure": False,
            "invisible_risk": False,
            "supplier_mapping_done": True,
            "reasoning_trace": trace,
        }

    system_prompt = (
        "You are a supply chain analyst mapping which suppliers are exposed to a disruption signal. "
        "Your job:\n"
        "1. Call find_direct_suppliers for each affected location/entity\n"
        "2. For every supplier found, call traverse_tier2_suppliers to uncover hidden tier-2/3 exposure\n"
        "3. If the signal mentions a port, call check_port_risk for that port\n"
        "4. Call finish_mapping with your complete findings\n\n"
        "Be thorough — the most important finding is INVISIBLE risk: a supplier that looks unaffected "
        "but sources components from a supplier IN the affected zone."
    )

    user_message = (
        f"Signal: {raw_signal}\n"
        f"Affected entities: {json.dumps(entities)}\n\n"
        "Map all supplier exposure. Check tier-2 chains for every direct supplier you find."
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

        # Append assistant turn
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            break

        # Process tool calls
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            if block.name == "finish_mapping":
                finish_data = block.input
                trace.append(
                    f"[Agent3] finish_mapping called: tier2={block.input.get('tier2_exposure')}, "
                    f"invisible={block.input.get('invisible_risk')}, "
                    f"suppliers={len(block.input.get('affected_suppliers', []))}"
                )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": "Mapping recorded.",
                })
            else:
                result = _execute_tool(block.name, block.input)
                trace.append(f"[Agent3] {block.name}({block.input}) -> {result[:120]}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    # Build output
    if finish_data:
        raw_suppliers = finish_data.get("affected_suppliers", [])
        # Guard: drop any entry where supplier_id looks like a name rather than an ID
        # Real IDs follow the SUP-xxx pattern; LLMs occasionally write the name instead
        affected_suppliers = [
            s for s in raw_suppliers
            if s.get("supplier_id") and str(s["supplier_id"]).upper().startswith("SUP")
        ]
        if len(affected_suppliers) < len(raw_suppliers):
            trace.append(f"[Agent3] WARNING: dropped {len(raw_suppliers) - len(affected_suppliers)} supplier(s) with invalid supplier_id")
        tier2_exposure = finish_data.get("tier2_exposure", False)
        invisible_risk = finish_data.get("invisible_risk", False)
        reasoning = finish_data.get("reasoning", "")
        trace.append(f"[Agent3] {reasoning}")
    else:
        affected_suppliers = []
        tier2_exposure = False
        invisible_risk = False
        trace.append("[Agent3] WARNING: finish_mapping was never called")

    return {
        "affected_suppliers": affected_suppliers,
        "tier2_exposure": tier2_exposure,
        "invisible_risk": invisible_risk,
        "supplier_mapping_done": True,
        "reasoning_trace": trace,
    }
