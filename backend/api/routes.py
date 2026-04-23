import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.graph.pipeline import compile_graph
from backend.graph.state import SupplyChainState
from backend.agents import agent_4_chat
from backend.storage.mongo_client import (
    store_alert,
    list_alerts,
    list_news_articles,
    create_session,
    list_sessions,
    get_session_messages,
    clear_news_articles,
    clear_signal_hashes,
    clear_alerts,
    clear_irrelevant_alerts,
    delete_session_messages,
)
from backend.storage.postgres_client import get_sku
from backend.jobs.scrape_signals import scrape_and_ingest, scheduler_loop, job_state, fetch_all_port_weather


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(scheduler_loop())
    yield


app = FastAPI(title="Ripple API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        _graph = compile_graph()
    return _graph


# --- Request / response models ---

class AnalyzeRequest(BaseModel):
    signal: str
    user_id: str = "default"


class ChatRequest(BaseModel):
    session_id: str
    message: str


# --- Helpers ---

def _serialize(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Not serializable: {type(obj)}")


def _stream_pipeline(signal: str, session_id: str, user_id: str):
    try:
        graph = _get_graph()
    except Exception as exc:
        yield f"data: {json.dumps({'type': 'error', 'message': f'Graph init failed: {exc}'})}\n\n"
        return

    initial_state: SupplyChainState = {
        "raw_signal": signal,
        "signal_type": None,
        "severity_score": 0.0,
        "affected_entities": [],
        "affected_suppliers": [],
        "tier2_exposure": False,
        "invisible_risk": False,
        "supplier_mapping_done": False,
        "sku_risks": [],
        "historical_context": None,
        "risk_scored": False,
        "alternatives": [],
        "alternatives_found": False,
        "alternatives_requested": False,
        "alert_ready": False,
        "alert_type": "",
        "final_alert": None,
        "messages": [],
        "pending_user_question": None,
        "next_agent": None,
        "reasoning_trace": [],
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc),
    }

    config = {"configurable": {"thread_id": session_id}}
    yield f"data: {json.dumps({'type': 'start', 'session_id': session_id})}\n\n"

    accumulated_state = dict(initial_state)

    try:
        for chunk in graph.stream(initial_state, config=config):
            for node_name, updates in chunk.items():
                if "reasoning_trace" in updates:
                    accumulated_state["reasoning_trace"] = (
                        accumulated_state.get("reasoning_trace", []) + updates["reasoning_trace"]
                    )
                for k, v in updates.items():
                    if k != "reasoning_trace":
                        accumulated_state[k] = v

                event = {
                    "type": "agent_update",
                    "agent": node_name,
                    "data": {k: v for k, v in updates.items() if k != "reasoning_trace"},
                    "trace": updates.get("reasoning_trace", []),
                }
                yield f"data: {json.dumps(event, default=_serialize)}\n\n"

    except Exception as exc:
        yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
        return

    # Persist alert to Mongo so the alerts feed picks it up
    if accumulated_state.get("final_alert"):
        try:
            store_alert({
                "session_id": session_id,
                "user_id": user_id,
                "signal": signal,
                "signal_type": accumulated_state.get("signal_type"),
                "severity_score": accumulated_state.get("severity_score"),
                "alert_type": accumulated_state.get("alert_type"),
                "final_alert": accumulated_state.get("final_alert"),
                "affected_entities": accumulated_state.get("affected_entities", []),
                "affected_suppliers": accumulated_state.get("affected_suppliers", []),
                "sku_risks": [
                    {**r, "runout_date": r["runout_date"].isoformat() if isinstance(r.get("runout_date"), datetime) else r.get("runout_date")}
                    for r in accumulated_state.get("sku_risks", [])
                ],
                "alternatives": accumulated_state.get("alternatives", []),
                "tier2_exposure": accumulated_state.get("tier2_exposure"),
                "invisible_risk": accumulated_state.get("invisible_risk"),
            })
        except Exception as e:
            pass  # non-fatal — alert already streamed to client

    complete = {
        "type": "complete",
        "session_id": session_id,
        "final_alert": accumulated_state.get("final_alert"),
        "signal_type": accumulated_state.get("signal_type"),
        "severity_score": accumulated_state.get("severity_score"),
        "affected_suppliers": accumulated_state.get("affected_suppliers", []),
        "tier2_exposure": accumulated_state.get("tier2_exposure"),
        "invisible_risk": accumulated_state.get("invisible_risk"),
        "sku_risks": accumulated_state.get("sku_risks", []),
        "alternatives": accumulated_state.get("alternatives", []),
        "reasoning_trace": accumulated_state.get("reasoning_trace", []),
    }
    yield f"data: {json.dumps(complete, default=_serialize)}\n\n"


# --- Endpoints ---

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "ripple"}


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    session_id = str(uuid.uuid4())
    # Create a Mongo session so chat can attach to it later
    try:
        create_session(req.user_id)
    except Exception:
        pass
    return StreamingResponse(
        _stream_pipeline(req.signal, session_id, req.user_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/alerts")
def get_alerts(
    limit: int = Query(default=50, le=200),
    since: str | None = Query(default=None, description="ISO timestamp — return alerts after this time"),
):
    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid 'since' timestamp — use ISO format")
    alerts = list_alerts(limit=limit, since=since_dt)
    return {"alerts": alerts, "count": len(alerts)}


def _state_from_alert(alert: dict) -> dict:
    """Reconstruct a minimal SupplyChainState from a MongoDB alert document.
    Used as fallback when no LangGraph checkpoint exists (e.g. seeded demo alerts)."""
    return {
        "raw_signal": alert.get("signal", ""),
        "signal_type": alert.get("signal_type"),
        "severity_score": alert.get("severity_score", 0.0),
        "affected_entities": alert.get("affected_entities", []),
        "affected_suppliers": alert.get("affected_suppliers", []),
        "tier2_exposure": alert.get("tier2_exposure", False),
        "invisible_risk": alert.get("invisible_risk", False),
        "supplier_mapping_done": True,
        "sku_risks": alert.get("sku_risks", []),
        "historical_context": None,
        "risk_scored": bool(alert.get("sku_risks")),
        "alternatives": alert.get("alternatives", []),
        "alternatives_found": bool(alert.get("alternatives")),
        "alternatives_requested": False,
        "alert_ready": True,
        "alert_type": alert.get("alert_type", ""),
        "final_alert": alert.get("final_alert"),
        "messages": [],
        "pending_user_question": None,
        "next_agent": None,
        "reasoning_trace": [],
        "session_id": alert.get("session_id", ""),
        "timestamp": alert.get("created_at", datetime.now(timezone.utc)),
    }


@app.post("/api/chat")
def chat(req: ChatRequest):
    # Retrieve pipeline state from LangGraph checkpointer
    config = {"configurable": {"thread_id": req.session_id}}
    try:
        snapshot = _get_graph().get_state(config)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load session state: {exc}")

    if not snapshot or not snapshot.values:
        # Fallback: reconstruct state from the MongoDB alert (covers seeded demo alerts)
        from backend.storage.mongo_client import get_db
        alert_doc = get_db().alerts.find_one({"session_id": req.session_id})
        if not alert_doc:
            raise HTTPException(status_code=404, detail="Session not found — run /api/analyze first or select a seeded alert")
        state = _state_from_alert(alert_doc)
    else:
        state = dict(snapshot.values)
    state["pending_user_question"] = req.message
    # Strip Mongo metadata fields so Anthropic only sees role+content
    raw_msgs = get_session_messages(req.session_id, limit=50)
    state["messages"] = [
        {"role": m["role"], "content": m["content"]}
        for m in raw_msgs
        if m.get("role") and m.get("content") and isinstance(m.get("content"), str)
    ]

    try:
        result = agent_4_chat.run(state)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent 4 error: {exc}")

    # If Agent 4 flagged alternatives, run Agent 5 now and summarise
    if result.get("alternatives_requested"):
        from backend.agents import alt_sourcing
        state.update(result)
        state["alternatives_requested"] = True
        try:
            alt_result = alt_sourcing.run(state)
            state.update(alt_result)
            # Ask Agent 4 to present the alternatives that were just found
            state["pending_user_question"] = "Summarise the alternative suppliers just found and their scores."
            state["messages"] = [
                {"role": m["role"], "content": m["content"]}
                for m in get_session_messages(req.session_id, limit=50)
                if m.get("role") and m.get("content") and isinstance(m.get("content"), str)
            ]
            result = agent_4_chat.run(state)
        except Exception as exc:
            pass  # best-effort — original Agent 4 response still usable

    # Pull the latest assistant message from Mongo (agent_4_chat persists it there)
    msgs = get_session_messages(req.session_id, limit=10)
    assistant_msgs = [m for m in msgs if m["role"] == "assistant"]
    response_text = assistant_msgs[-1]["content"] if assistant_msgs else ""

    return {
        "session_id": req.session_id,
        "response": response_text,
        "alternatives_requested": result.get("alternatives_requested", False),
    }


@app.get("/api/sku/{sku_id}")
def get_sku_detail(sku_id: str):
    row = get_sku(sku_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"SKU {sku_id} not found")
    return row


@app.get("/api/sessions/{user_id}")
def get_user_sessions(user_id: str):
    sessions = list_sessions(user_id)
    return {"sessions": sessions, "count": len(sessions)}


@app.get("/api/sessions/{session_id}/messages")
def get_messages(session_id: str, limit: int = Query(default=50, le=200)):
    msgs = get_session_messages(session_id, limit=limit)
    return {"session_id": session_id, "messages": msgs, "count": len(msgs)}


@app.delete("/api/sessions/{session_id}/messages")
def clear_messages(session_id: str):
    """Clear visible chat history. mem0 semantic memory preserved for agent recall."""
    deleted = delete_session_messages(session_id)
    return {"session_id": session_id, "deleted": deleted}


_port_weather_cache: dict = {"data": [], "fetched_at": None}
_PORT_WEATHER_TTL = 600  # 10 minutes


@app.get("/api/port-weather")
async def get_port_weather():
    now = datetime.now(timezone.utc)
    cached_at = _port_weather_cache["fetched_at"]
    if cached_at and (now - cached_at).total_seconds() < _PORT_WEATHER_TTL:
        return {"ports": _port_weather_cache["data"], "cached": True, "fetched_at": cached_at.isoformat()}
    data = await fetch_all_port_weather()
    _port_weather_cache["data"] = data
    _port_weather_cache["fetched_at"] = now
    return {"ports": data, "cached": False, "fetched_at": now.isoformat()}


@app.get("/api/news")
def get_news(
    category: str | None = Query(default=None, description="weather | geopolitical | other"),
    limit: int = Query(default=50, le=200),
):
    if category and category not in ("weather", "geopolitical", "other"):
        raise HTTPException(status_code=400, detail="category must be weather, geopolitical, or other")
    articles = list_news_articles(category=category, limit=limit)
    return {"articles": articles, "count": len(articles), "category": category}


@app.post("/api/trigger-scrape")
async def trigger_scrape():
    """Manually kick off a signal scrape + ingestion cycle."""
    asyncio.create_task(scrape_and_ingest())
    return {"status": "triggered"}


@app.post("/api/clear-cache")
async def clear_cache(wipe_alerts: bool = Query(default=False, description="Also delete ALL alerts")):
    """Wipe news articles, signal hashes, and irrelevant alerts so next scrape re-fetches everything.
    Pass ?wipe_alerts=true to also delete every alert (including relevant ones)."""
    news_deleted = clear_news_articles()
    hashes_deleted = clear_signal_hashes()
    alerts_deleted = clear_alerts() if wipe_alerts else clear_irrelevant_alerts()
    _port_weather_cache["data"] = []
    _port_weather_cache["fetched_at"] = None
    asyncio.create_task(scrape_and_ingest())
    return {
        "status": "cleared",
        "news_articles_deleted": news_deleted,
        "signal_hashes_deleted": hashes_deleted,
        "alerts_deleted": alerts_deleted,
        "scrape": "triggered",
    }


@app.get("/api/scrape-status")
def scrape_status():
    return job_state
