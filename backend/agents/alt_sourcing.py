"""
Agent 5 — Hybrid Alternative Sourcing (claude-haiku-4-5-20251001)

Two retrieval paths:
  - RAG (pgvector): semantic similarity search via Ollama embeddings
  - Graph (Neo4j): shared-product traversal over SUPPLIES edges

Scores are normalized to [0,1] and blended:
  final_score = α·graph + (1-α)·rag
  (α from env ALT_GRAPH_ALPHA, default 0.5)

Suppliers found by only one source keep that source's weighted score.
"""
import json
import os
import httpx
from anthropic import Anthropic
from langsmith import wrappers
from backend.storage.postgres_client import vector_search_suppliers, get_sku
from backend.storage.neo4j_client import find_alternative_suppliers
from backend.graph.state import SupplyChainState, AlternativeSupplier

client = wrappers.wrap_anthropic(Anthropic())
MODEL = "claude-haiku-4-5-20251001"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
ALPHA = float(os.getenv("ALT_GRAPH_ALPHA", "0.5"))

LEAD_TIME_BY_REGION = {
    "vietnam": 14, "thailand": 14, "malaysia": 14, "indonesia": 15,
    "india": 18, "bangladesh": 16, "sri lanka": 18,
    "germany": 21, "netherlands": 21, "poland": 22, "france": 22,
    "united states": 25, "usa": 25, "mexico": 20, "canada": 24,
    "japan": 16, "south korea": 16, "taiwan": 14,
    "china": 18, "brazil": 28, "turkey": 22,
}


def _get_embedding(text: str) -> list[float]:
    response = httpx.post(
        f"{OLLAMA_BASE_URL}/api/embeddings",
        json={"model": EMBEDDING_MODEL, "prompt": text},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()["embedding"]


def _lead_time(country: str) -> int:
    key = (country or "").lower()
    for region, days in LEAD_TIME_BY_REGION.items():
        if region in key:
            return days
    return 30


def _normalize(scores: list[float]) -> list[float]:
    if not scores:
        return scores
    mx = max(scores)
    mn = min(scores)
    rng = mx - mn
    if rng == 0:
        return [1.0] * len(scores)
    return [(s - mn) / rng for s in scores]


def _blend(
    rag: list[dict],
    graph: list[dict],
    alpha: float,
) -> list[AlternativeSupplier]:
    """
    Merge RAG and graph candidates by supplier_id, compute blended score.
    rag items: {supplier_id, name, country, rag_score, estimated_lead_time, confidence}
    graph items: {supplier_id, name, country, reliability_score, ...}
    """
    # Normalize graph scores
    g_scores = [float(g.get("reliability_score", 0.5)) for g in graph]
    g_norm = _normalize(g_scores)
    graph_map: dict[str, dict] = {}
    for item, score in zip(graph, g_norm):
        sid = item["supplier_id"]
        graph_map[sid] = {**item, "graph_score_norm": score}

    # Normalize RAG scores
    r_scores = [float(r.get("rag_score", 0)) for r in rag]
    r_norm = _normalize(r_scores)
    rag_map: dict[str, dict] = {}
    for item, score in zip(rag, r_norm):
        sid = item["supplier_id"]
        rag_map[sid] = {**item, "rag_score_norm": score}

    all_ids = set(graph_map) | set(rag_map)
    results: list[AlternativeSupplier] = []

    for sid in all_ids:
        g = graph_map.get(sid)
        r = rag_map.get(sid)

        if g and r:
            final = alpha * g["graph_score_norm"] + (1 - alpha) * r["rag_score_norm"]
            name = g.get("name") or r.get("name", sid)
            country = g.get("country") or r.get("country", "Unknown")
            lead_time = r.get("estimated_lead_time") or _lead_time(country)
            confidence = 0.9 if final > 0.7 else (0.7 if final > 0.5 else 0.5)
        elif g:
            final = alpha * g["graph_score_norm"]
            name = g.get("name", sid)
            country = g.get("country", "Unknown")
            lead_time = _lead_time(country)
            confidence = 0.7
        else:
            final = (1 - alpha) * r["rag_score_norm"]
            name = r.get("name", sid)
            country = r.get("country", "Unknown")
            lead_time = r.get("estimated_lead_time") or _lead_time(country)
            confidence = 0.7 if final > 0.5 else 0.5

        results.append(AlternativeSupplier(
            supplier_id=sid,
            name=name,
            country=country,
            similarity_score=round(final, 4),
            estimated_lead_time=lead_time,
            confidence=confidence,
        ))

    results.sort(key=lambda x: x["similarity_score"], reverse=True)
    return results[:5]


# --- LLM tools ---

TOOLS = [
    {
        "name": "search_alternative_suppliers",
        "description": (
            "Vector similarity search for alternative suppliers via pgvector. "
            "Generates an embedding from your query and returns the closest matching "
            "suppliers by capability, excluding affected suppliers. "
            "Returns supplier_id, description, and rag_score."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Capability description, e.g. 'MCU semiconductor manufacturer Southeast Asia'",
                },
                "exclude_supplier_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Supplier IDs to exclude (the affected ones)",
                },
                "k": {"type": "integer", "description": "Results to return (default 5)"},
            },
            "required": ["query", "exclude_supplier_ids"],
        },
    },
    {
        "name": "find_graph_alternatives",
        "description": (
            "Graph traversal search for alternative suppliers via Neo4j. "
            "Finds suppliers connected to the same products/SKUs as the affected ones. "
            "Returns supplier_id, name, country, capabilities, reliability_score."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "affected_supplier_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "IDs of the affected suppliers",
                },
                "sku_id": {
                    "type": "string",
                    "description": "Optional: narrow search to a specific SKU",
                },
            },
            "required": ["affected_supplier_ids"],
        },
    },
    {
        "name": "finish_sourcing",
        "description": (
            "Report the interpreted alternative suppliers after searching both sources. "
            "Provide name, country, and lead_time inferred from descriptions. "
            "Call this once after running both search tools."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "alternatives": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "supplier_id": {"type": "string"},
                            "name": {"type": "string"},
                            "country": {"type": "string"},
                            "estimated_lead_time": {"type": "integer"},
                            "source": {
                                "type": "string",
                                "enum": ["rag", "graph", "both"],
                                "description": "Which retrieval source found this supplier",
                            },
                        },
                        "required": ["supplier_id", "name", "country", "estimated_lead_time", "source"],
                    },
                },
            },
            "required": ["alternatives"],
        },
    },
]


def _execute_tool(
    tool_name: str,
    tool_input: dict,
    trace: list,
    rag_candidates: list,
    graph_candidates: list,
) -> str:
    if tool_name == "search_alternative_suppliers":
        query = tool_input["query"]
        exclude_ids = set(tool_input.get("exclude_supplier_ids", []))
        k = int(tool_input.get("k", 5))
        try:
            embedding = _get_embedding(query)
        except Exception as e:
            return json.dumps({"error": f"Embedding failed: {e}"})

        rows = vector_search_suppliers(embedding, k=k + len(exclude_ids))
        filtered = [r for r in rows if r["supplier_id"] not in exclude_ids][:k]
        for r in filtered:
            rag_candidates.append({
                "supplier_id": r["supplier_id"],
                "description": r.get("description", ""),
                "rag_score": float(r.get("similarity_score", 0)),
                "name": "",
                "country": "",
                "estimated_lead_time": None,
            })
        return json.dumps([
            {"supplier_id": r["supplier_id"], "description": r.get("description", ""),
             "rag_score": round(float(r.get("similarity_score", 0)), 4)}
            for r in filtered
        ])

    if tool_name == "find_graph_alternatives":
        affected_ids = tool_input["affected_supplier_ids"]
        sku_id = tool_input.get("sku_id")
        try:
            results = find_alternative_suppliers(affected_ids, sku_id)
        except Exception as e:
            return json.dumps({"error": f"Neo4j query failed: {e}"})
        graph_candidates.extend(results)
        return json.dumps([
            {"supplier_id": r["supplier_id"], "name": r.get("name", ""),
             "country": r.get("country", ""), "reliability_score": r.get("reliability_score", 0.5),
             "shared_products": r.get("shared_products", 0)}
            for r in results
        ])

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


def run(state: SupplyChainState) -> dict:
    sku_risks = state.get("sku_risks", [])
    affected_suppliers = state.get("affected_suppliers", [])
    raw_signal = state.get("raw_signal", "")
    trace = []

    if not sku_risks:
        trace.append("[Agent5] No at-risk SKUs — skipping alt sourcing")
        return {"alternatives": [], "alternatives_found": True, "reasoning_trace": trace}

    affected_ids = [s["supplier_id"] for s in affected_suppliers if s.get("supplier_id")]

    at_risk_skus = []
    for r in sku_risks:
        sku_id = r["sku_id"]
        row = get_sku(sku_id)
        at_risk_skus.append({
            "sku_id": sku_id,
            "name": row["name"] if row else sku_id,
            "gap_days": r.get("gap_days", 0),
        })
    trace.append(f"[Agent5] Hybrid search for {[s['sku_id'] for s in at_risk_skus]}, excluding {affected_ids}")

    system_prompt = (
        "You are a supply chain sourcing analyst finding alternative suppliers.\n\n"
        "Steps:\n"
        "1. Call search_alternative_suppliers (RAG) for each at-risk SKU.\n"
        "2. Call find_graph_alternatives (Neo4j) once with all affected supplier IDs.\n"
        "3. From the RAG descriptions, infer name, country, and estimated lead time "
        "(Vietnam/SE Asia ~14d, India ~18d, Europe ~21d, US ~25d).\n"
        "4. Call finish_sourcing with the interpreted results.\n\n"
        "Verify RAG descriptions match the required component type before including them."
    )

    user_message = (
        f"Signal: {raw_signal}\n"
        f"At-risk SKUs: {json.dumps(at_risk_skus)}\n"
        f"Affected suppliers to exclude: {json.dumps(affected_ids)}\n\n"
        "Search both RAG and graph sources, then call finish_sourcing with your interpretations."
    )

    messages = [{"role": "user", "content": user_message}]
    rag_candidates: list[dict] = []
    graph_candidates: list[dict] = []
    finish_data: dict | None = None
    iterations = 0

    while finish_data is None and iterations < 10:
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
            if block.name == "finish_sourcing":
                finish_data = block.input
                trace.append(f"[Agent5] finish_sourcing: {len(block.input.get('alternatives', []))} entries")
                # Enrich rag_candidates with LLM-inferred name/country/lead_time
                interp = {a["supplier_id"]: a for a in block.input.get("alternatives", [])}
                for rc in rag_candidates:
                    sid = rc["supplier_id"]
                    if sid in interp:
                        rc["name"] = interp[sid].get("name", "")
                        rc["country"] = interp[sid].get("country", "")
                        rc["estimated_lead_time"] = interp[sid].get("estimated_lead_time")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": "Sourcing recorded.",
                })
            else:
                result = _execute_tool(block.name, block.input, trace, rag_candidates, graph_candidates)
                trace.append(f"[Agent5] {block.name} -> {result[:150]}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    if not finish_data:
        trace.append("[Agent5] WARNING: finish_sourcing not called — blending raw results")

    alternatives = _blend(rag_candidates, graph_candidates, ALPHA)
    trace.append(f"[Agent5] Blended (alpha={ALPHA}): {len(alternatives)} alternatives (rag={len(rag_candidates)}, graph={len(graph_candidates)})")

    return {
        "alternatives": alternatives,
        "alternatives_found": True,
        "alert_ready": True,
        "reasoning_trace": trace,
    }
