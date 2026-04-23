"""
LangGraph pipeline — orchestrator-centric topology.

Flow:
  orchestrator (LLM supervisor)
    → signal_scraper → orchestrator
    → supplier_mapping → orchestrator
    → agent_4 (chat) → orchestrator
    → agent_5 (alt sourcing) → orchestrator
    → report_compiler → orchestrator
    → no_alert (terminal) → END
    → END
"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.mongodb import MongoDBSaver

from backend.graph.state import SupplyChainState
from backend.agents import signal_scraper, supplier_mapping, alt_sourcing, report_compiler
from backend.agents import agent_4_chat
from backend.graph.orchestrator import orchestrate, no_alert_handler
from backend.storage.mongo_client import get_client


def _safe_run(agent_name: str, fn, state: SupplyChainState) -> dict:
    try:
        return fn(state)
    except Exception as exc:
        return {"reasoning_trace": [f"[{agent_name}] ERROR: {exc}"]}


# --- Node wrappers ---

def node_orchestrator(state: SupplyChainState) -> dict:
    return _safe_run("Orchestrator", orchestrate, state)

def node_signal_scraper(state: SupplyChainState) -> dict:
    return _safe_run("Agent2", signal_scraper.run, state)

def node_supplier_mapping(state: SupplyChainState) -> dict:
    return _safe_run("Agent3", supplier_mapping.run, state)

def node_agent_4_chat(state: SupplyChainState) -> dict:
    return _safe_run("Agent4", agent_4_chat.run, state)

def node_alt_sourcing(state: SupplyChainState) -> dict:
    return _safe_run("Agent5", alt_sourcing.run, state)

def node_report_compiler(state: SupplyChainState) -> dict:
    return _safe_run("Agent6", report_compiler.run, state)

def node_no_alert(state: SupplyChainState) -> dict:
    return no_alert_handler(state)


# --- Orchestrator dispatch map ---
DISPATCH = {
    "signal_scraper":   "agent_2",
    "supplier_mapping": "agent_3",
    "agent_4":          "agent_4",
    "agent_5":          "agent_5",
    "report_compiler":  "agent_1_synthesis",
    "no_alert":         "no_alert",
    "END":              END,
}


def _dispatch(state: SupplyChainState) -> str:
    return state.get("next_agent", "END")


def build_graph() -> StateGraph:
    graph = StateGraph(SupplyChainState)

    graph.add_node("orchestrator",    node_orchestrator)
    graph.add_node("agent_2",         node_signal_scraper)
    graph.add_node("agent_3",         node_supplier_mapping)
    graph.add_node("agent_4",         node_agent_4_chat)
    graph.add_node("agent_5",         node_alt_sourcing)
    graph.add_node("agent_1_synthesis", node_report_compiler)
    graph.add_node("no_alert",        node_no_alert)

    graph.set_entry_point("orchestrator")

    # Orchestrator fans out to whichever agent it picks
    graph.add_conditional_edges("orchestrator", _dispatch, DISPATCH)

    # Every agent loops back to orchestrator
    for node in ("agent_2", "agent_3", "agent_4", "agent_5", "agent_1_synthesis"):
        graph.add_edge(node, "orchestrator")

    # Terminal nodes
    graph.add_edge("no_alert", END)

    return graph


def compile_graph():
    checkpointer = MongoDBSaver(get_client())
    return build_graph().compile(checkpointer=checkpointer)
