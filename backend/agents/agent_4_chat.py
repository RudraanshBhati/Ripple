"""
Agent 4 — Memory-aware Conversation Agent (claude-haiku-4-5-20251001)

Primary operator touchpoint. On first run it auto-scores SKUs. On subsequent
calls (pending_user_question set) it answers questions using its tool suite.
It only invokes Agent 5 when the operator explicitly asks for alternatives.
"""
import json
from anthropic import Anthropic
from langsmith import wrappers
from dotenv import load_dotenv

from backend.graph.state import SupplyChainState
from backend.storage import postgres_client
from backend.storage.mem0_client import search_memories
from backend.storage.mongo_client import get_session_messages, append_message
from backend.agents.tools.score_skus import score_skus

load_dotenv()

client = wrappers.wrap_anthropic(Anthropic())
MODEL = "claude-haiku-4-5-20251001"

TOOLS = [
    {
        "name": "get_sku_status",
        "description": "Fetch current inventory and lead-time data for a specific SKU from Postgres.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sku_id": {"type": "string", "description": "SKU identifier, e.g. SKU-001"}
            },
            "required": ["sku_id"],
        },
    },
    {
        "name": "search_history",
        "description": "Search mem0 for historical disruption patterns relevant to a query.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language search query"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "score_at_risk_skus",
        "description": (
            "Score all SKUs for the current affected suppliers and return a risk summary. "
            "Call this once per session before answering risk questions."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "request_alternatives",
        "description": (
            "Signal that the operator wants alternative suppliers found. "
            "Only call this when the operator explicitly asks for alternatives."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "recall_past_session",
        "description": "Search prior messages from this chat session stored in MongoDB.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to look for in past messages"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_analysis_details",
        "description": (
            "Return the full pipeline reasoning trace, SKU risk breakdown with raw numbers "
            "(stock_on_hand, daily_usage, gap_days), scoring methodology, and affected supplier list. "
            "Call this when the operator asks WHY a SKU is at risk, HOW a risk score was calculated, "
            "HOW the pipeline works, or wants a detailed breakdown of any figure in the alert."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "simulate_scenario",
        "description": (
            "Run a what-if simulation on the current disruption. Computes how SKU gap_days, "
            "stockout timelines, and risk scores change under different assumptions — without "
            "altering real state. Call this for ANY question containing 'what if', 'what would "
            "happen if', 'suppose', 'scenario where', 'if the disruption lasts', 'if we air "
            "freight', 'if demand spikes', or any hypothetical variation of the current situation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "scenario_description": {
                    "type": "string",
                    "description": "Plain English description of the hypothetical (e.g. 'disruption lasts 60 days', 'demand spikes 40%', 'we use air freight cutting lead time to 7 days')",
                },
                "disruption_extension_days": {
                    "type": "integer",
                    "description": "Add N extra days to current supplier lead times to model extended disruption",
                },
                "demand_multiplier": {
                    "type": "number",
                    "description": "Multiply daily SKU consumption by this factor (e.g. 1.5 = +50% demand spike, 0.7 = -30% demand reduction)",
                },
                "lead_time_override_days": {
                    "type": "integer",
                    "description": "Override lead time to this fixed value for all affected SKUs (e.g. 7 for air freight, 3 for local safety stock)",
                },
            },
            "required": ["scenario_description"],
        },
    },
]


def _execute_tool(name: str, tool_input: dict, state: SupplyChainState, scoring_results: dict) -> str:
    if name == "get_sku_status":
        sku_id = tool_input["sku_id"]
        row = postgres_client.get_sku(sku_id)
        if not row:
            return json.dumps({"error": f"SKU {sku_id} not found"})
        return json.dumps(dict(row), default=str)

    if name == "search_history":
        memories = search_memories(tool_input["query"], limit=3)
        if not memories:
            return "No historical records found."
        return json.dumps([m.get("memory", m.get("text", "")) for m in memories])

    if name == "score_at_risk_skus":
        affected = state.get("affected_suppliers", [])
        signal = state.get("raw_signal", "")
        sku_risks, hist = score_skus(affected, signal)
        scoring_results["sku_risks"] = sku_risks
        scoring_results["historical_context"] = hist
        summary = [
            f"{r['sku_id']}: risk={r['risk_score']:.3f} gap={r['gap_days']:.1f}d"
            for r in sku_risks
        ]
        return json.dumps({"scored": len(sku_risks), "skus": summary, "historical_context": hist[:200]})

    if name == "request_alternatives":
        scoring_results["alternatives_requested"] = True
        return "Alternatives request flagged — Agent 5 will run next."

    if name == "recall_past_session":
        session_id = state.get("session_id", "")
        if not session_id:
            return "No session ID in state."
        msgs = get_session_messages(session_id, limit=50)
        query = tool_input["query"].lower()
        # Simple keyword filter over stored messages
        hits = [m for m in msgs if query in m.get("content", "").lower()]
        if not hits:
            return "No matching messages found in session history."
        return json.dumps([{"role": m["role"], "content": m["content"][:300]} for m in hits[:5]])

    if name == "simulate_scenario":
        sku_risks = state.get("sku_risks", [])
        if not sku_risks:
            return json.dumps({"error": "No SKU risk data available. Run score_at_risk_skus first."})

        description = tool_input.get("scenario_description", "")
        extension_days = int(tool_input.get("disruption_extension_days") or 0)
        demand_mult = float(tool_input.get("demand_multiplier") or 1.0)
        lead_override = tool_input.get("lead_time_override_days")

        impacts = []
        for sku in sku_risks:
            sku_id = sku.get("sku_id", "?")
            stock = sku.get("stock_on_hand") or sku.get("current_stock") or 0
            daily = sku.get("daily_usage") or sku.get("daily_consumption") or 1
            current_lead = sku.get("lead_time_days") or sku.get("lead_time") or 21
            current_gap = sku.get("gap_days") or 0

            sim_daily = daily * demand_mult
            sim_lead = int(lead_override) if lead_override is not None else current_lead + extension_days
            sim_days_of_stock = (stock / sim_daily) if sim_daily > 0 else 999
            sim_gap = round(sim_days_of_stock - sim_lead, 1)
            sim_risk = round(max(0.0, min(1.0, 0.5 + (-sim_gap / 30))), 3)
            delta = round(sim_gap - current_gap, 1)

            impacts.append({
                "sku_id": sku_id,
                "current": {
                    "gap_days": round(current_gap, 1),
                    "lead_time_days": current_lead,
                    "daily_usage": round(daily, 1),
                    "risk_score": round(sku.get("risk_score", 0), 3),
                },
                "simulated": {
                    "gap_days": sim_gap,
                    "lead_time_days": sim_lead,
                    "daily_usage": round(sim_daily, 1),
                    "risk_score": sim_risk,
                },
                "delta_gap_days": delta,
                "verdict": (
                    "WORSE — stockout window widens" if delta < -2
                    else "BETTER — gap improves" if delta > 2
                    else "MARGINAL — minimal change"
                ),
            })

        still_at_risk = sum(1 for r in impacts if r["simulated"]["gap_days"] < 0)
        return json.dumps({
            "scenario": description,
            "parameters_applied": {
                "disruption_extension_days": extension_days,
                "demand_multiplier": demand_mult,
                "lead_time_override_days": lead_override,
            },
            "sku_impacts": impacts,
            "summary": f"{still_at_risk} of {len(impacts)} SKUs still in stockout range under this scenario",
        })

    if name == "get_analysis_details":
        sku_risks = state.get("sku_risks", [])
        trace = state.get("reasoning_trace", [])
        historical_context = state.get("historical_context", "")
        affected_suppliers = state.get("affected_suppliers", [])

        sku_details = [
            {
                "sku_id": r.get("sku_id"),
                "risk_score": r.get("risk_score"),
                "gap_days": r.get("gap_days"),
                "confidence": r.get("confidence"),
                "stock_on_hand": r.get("stock_on_hand"),
                "daily_usage": r.get("daily_usage"),
                "supplier_id": r.get("supplier_id"),
                "runout_date": str(r.get("runout_date", "")),
            }
            for r in sku_risks
        ]

        methodology = (
            "Risk score = weighted combination of: supplier exposure (tier + country risk), "
            "inventory gap (days of stock vs. lead time), and historical disruption frequency from mem0 memory. "
            "gap_days = (stock_on_hand / daily_usage) - supplier_lead_time. "
            "Negative gap_days = stockout expected before new supply arrives."
        )

        return json.dumps({
            "methodology": methodology,
            "sku_risk_breakdown": sku_details,
            "affected_suppliers": [
                {
                    "id": s.get("supplier_id"), "name": s.get("name"),
                    "country": s.get("country"), "tier": s.get("tier"),
                    "exposure_type": s.get("exposure_type"),
                }
                for s in affected_suppliers
            ],
            "pipeline_trace": trace[-20:],
            "historical_context_snapshot": (
                historical_context[:500] if historical_context
                else "None in state — call search_history to query mem0 long-term memory."
            ),
        })

    return json.dumps({"error": f"Unknown tool: {name}"})


def run(state: SupplyChainState) -> dict:
    affected_suppliers = state.get("affected_suppliers", [])
    raw_signal = state.get("raw_signal", "")
    pending_question = state.get("pending_user_question")
    already_scored = state.get("risk_scored", False)
    session_id = state.get("session_id", "")
    chat_history = state.get("messages", [])
    trace = []

    scoring_results: dict = {}

    # Build system prompt
    supplier_ids = [s.get("supplier_id", "") for s in affected_suppliers if s.get("supplier_id")]
    alternatives = state.get("alternatives", [])
    alt_summary = ""
    if alternatives:
        alt_summary = "\nAlternative suppliers already found:\n" + "\n".join(
            f"  - {a.get('name', a.get('supplier_id', '?'))} ({a.get('country', '?')}) "
            f"score={a.get('similarity_score', 0):.2f} lead={a.get('estimated_lead_time', '?')}d"
            for a in alternatives[:5]
        )

    final_alert = state.get("final_alert") or ""
    final_alert_section = f"\nCompiled alert (from Agent 6):\n{final_alert}\n" if final_alert else ""

    system_prompt = (
        "You are Ripple — an AI supply chain analyst embedded in SAP. "
        "You are the operator's primary contact for questions about disruption alerts.\n\n"
        f"Current signal: {raw_signal}\n"
        f"Affected suppliers: {', '.join(supplier_ids) or 'none identified yet'}\n"
        f"SKUs scored: {'yes' if already_scored else 'no'}\n"
        f"{alt_summary}\n"
        f"{final_alert_section}\n"
        "RULES:\n"
        "- The compiled alert above was written by Agent 6 and is the authoritative risk summary. "
        "When asked about recommendations or alternatives, present and elaborate on the alert — do not contradict it.\n"
        "- NEVER invent supplier names, SKU IDs, scores, lead times, countries, or numbers not in your context or tool results.\n"
        "- If you don't have enough data to answer a question, say exactly that: "
        "'I don't have enough information to answer that confidently.' Do not speculate or guess.\n"
        "- If a tool returns 'not found' or 'no records', say so clearly and don't fill the gap with assumptions.\n"
        "- Be concise and operational — one direct answer, then supporting details if needed.\n\n"
        "HOW TO HANDLE QUESTION TYPES:\n"
        "- WHY is a SKU at risk / WHY this score? → call get_analysis_details for the raw breakdown, "
        "then call search_history with the supplier/region to check if this pattern has occurred before.\n"
        "- HOW does the scoring work / HOW was this calculated? → call get_analysis_details for the methodology.\n"
        "- WHAT happened / WHAT is the disruption? → use the signal + compiled alert above; "
        "call search_history if you need historical context on the event type.\n"
        "- WHAT SHOULD WE DO / recommendations? → present the compiled alert's recommended action.\n"
        "- WHAT IF / hypotheticals? → call simulate_scenario with the appropriate parameters. "
        "Map the question: 'lasts X days longer' → disruption_extension_days=X; "
        "'demand spikes Y%' → demand_multiplier=1+Y/100; "
        "'air freight / cut lead time to Z days' → lead_time_override_days=Z. "
        "After the tool returns, interpret the delta_gap_days and verdict fields in plain language — "
        "tell the operator concretely which SKUs get worse, which improve, and by how many days.\n"
        "- Questions about earlier conversation → call recall_past_session.\n\n"
        "TOOLS (when to call each):\n"
        "- score_at_risk_skus: call first if SKUs are not yet scored.\n"
        "- get_sku_status: live inventory for a specific SKU (use when asked about current stock levels).\n"
        "- search_history: ALWAYS call for 'why', 'has this happened before', or historical pattern questions. "
        "Uses long-term mem0 memory across past sessions.\n"
        "- get_analysis_details: call for 'how', 'why this score', 'explain the numbers', or pipeline trace questions.\n"
        "- simulate_scenario: call for ALL what-if, hypothetical, or 'what would happen if' questions.\n"
        "- request_alternatives: ONLY when operator explicitly asks to find alternative suppliers.\n"
        "- recall_past_session: look up what was said earlier in this chat session."
    )

    # Build a valid alternating user/assistant history for Anthropic.
    # MongoDB may have orphaned user messages (from failed calls) — strip them.
    clean: list[dict] = []
    for m in chat_history:
        role = m.get("role") if isinstance(m, dict) else getattr(m, "role", None)
        content = m.get("content") if isinstance(m, dict) else getattr(m, "content", None)
        if not role or not content or not isinstance(content, str):
            continue
        # Enforce alternation: drop consecutive same-role messages, keeping the last
        if clean and clean[-1]["role"] == role:
            clean[-1] = {"role": role, "content": content}
        else:
            clean.append({"role": role, "content": content})
    # Must start with user message
    while clean and clean[0]["role"] != "user":
        clean.pop(0)
    # Keep only the last 10 turns to stay within context limits
    messages = clean[-10:]

    if not already_scored and not pending_question:
        # Auto-score mode: first pipeline run, no question yet
        messages.append({
            "role": "user",
            "content": (
                f"A new disruption signal has arrived: {raw_signal}\n"
                f"Affected suppliers: {json.dumps(supplier_ids)}\n"
                "Please score the at-risk SKUs and summarise the findings."
            ),
        })
        trace.append("[Agent4] Auto-score mode — scoring SKUs for pipeline run")
    elif pending_question:
        messages.append({"role": "user", "content": pending_question})
        if session_id:
            append_message(session_id, "user", pending_question)
        trace.append(f"[Agent4] Chat mode — answering: {pending_question[:80]}")
    else:
        # Already scored, no question — nothing to do
        trace.append("[Agent4] Already scored, no pending question — passing through")
        return {"reasoning_trace": trace}

    # Tool loop
    iterations = 0
    final_text = ""

    while iterations < 10:
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
            for block in response.content:
                if hasattr(block, "text"):
                    final_text = block.text.strip()
            break

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result = _execute_tool(block.name, block.input, state, scoring_results)
            trace.append(f"[Agent4] {block.name}({block.input}) → {result[:120]}")
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    # Persist assistant reply to Mongo if this was a chat turn
    if pending_question and final_text and session_id:
        append_message(session_id, "assistant", final_text)

    # Build state update
    update: dict = {"reasoning_trace": trace, "messages": messages}

    if scoring_results.get("sku_risks") is not None:
        update["sku_risks"] = scoring_results["sku_risks"]
        update["historical_context"] = scoring_results.get("historical_context", "")
        update["risk_scored"] = True

    if scoring_results.get("alternatives_requested"):
        update["alternatives_requested"] = True

    if final_text:
        update["pending_user_question"] = None

    return update
