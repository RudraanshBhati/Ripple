# Ripple — 6-Agent Restructure

_Written 2026-04-18, execution order added 2026-04-19. No code has been changed yet — this plan is the starting point for the next session._

## Next Session Execution Order

Execute in this order — each step leaves the system runnable so we can stop any time:

**Step 1 — Foundation (Phase A)**
Mongo sessions/messages/alerts functions + `MongoDBSaver` checkpointer wired in `compile_graph()` + new state fields (`messages`, `pending_user_question`, `next_agent`, `alternatives_requested`). Smoke-test: create session, append messages, restart process, resume thread.

**Step 2 — Rename + strip synthesis (Phase E, trivial)**
Rename `backend/agents/conversation.py` → `report_compiler.py`, update imports in `backend/graph/pipeline.py`, drop the "Recommended actions: list alternative suppliers" line from the prompt. This is the edit paused on last time — do first so it's settled.

**Step 3 — Agent 4 rebuild (Phase C)**
Extract SKU scoring loop out of `risk_scorer.py` into `backend/agents/tools/score_skus.py`. Build new chat agent with tools `get_sku_status`, `search_history`, `score_at_risk_skus`, `request_alternatives`, `recall_past_session`. Leaves Agent 5 untouched for now.

**Step 4 — LLM Orchestrator (Phase D)**
Rewrite `backend/graph/orchestrator.py` as an LLM supervisor (Haiku, single `route` tool). Re-wire `pipeline.py`: entry → orchestrator → fan-out → back to orchestrator. Keep severity-<0.2 short-circuit as a pre-orchestrator guard.

**Step 5 — Hybrid Agent 5 (Phase B)**
Add `find_alternative_suppliers` to `neo4j_client.py`. Add second tool + blender to `alt_sourcing.py` using `α·graph + (1-α)·rag`, α from env, default 0.5.

**Step 6 — API surface (Phase F)**
Add `GET /api/alerts`, `POST /api/chat`, `GET /api/sku/{sku_id}`, `GET /api/sessions/*`. Make `/api/analyze` call `mongo.store_alert(...)` at the end.

**Step 7 — Frontend dashboard (Phase H)**
3-pane layout: alerts feed (left, polls `/api/alerts`) / alert detail (center, reuses `ResultsDashboard`+`PipelineTimeline`) / chat panel (right, hits `/api/chat`). Remove logo.

**Step 8 — Scheduler (Phase G, last)**
APScheduler job with one or two stub RSS/NewsAPI fetchers, gated by a feature flag. Startup hook in `routes.py`.

**Don't do in this session:** real live news ingestion (Phase G beyond stub), anything not in the list above.

---

## Context

The current backend works but is structured as a one-shot linear pipeline: signal → mapping → risk → alts → synthesis. The real intent is:

- An **agentic system with 6 roles**, not a 5-step pipeline.
- **Agent 4 (Risk/Memory) is the primary user touchpoint** — it owns memory across sessions, has DB-search tools, answers SKU/event questions, and *invokes Agent 5 only when asked*.
- **Agent 5 must be hybrid** — Neo4j graph (SOURCES_FROM, alternative-supplier edges) + pgvector RAG, blended.
- **Agent 6 is a report-compiler** — takes the accumulated state and produces the operator-facing alert. The current `agent_1_synthesis` is essentially this.
- Need a real **LLM Orchestrator** that decides what to run next (chat vs. invoke Agent 5 vs. re-run mapping etc.), instead of the current pure rule-based router.
- New signals should come from **manual entry + a scheduled scraper job** writing alerts into Mongo; the UI surfaces them.

**Resolved decisions:**
- Memory: **MongoDB chat history + LangGraph MongoDBSaver checkpointer**
- Orchestrator: **LLM supervisor** that picks the next agent
- Ingestion: **manual + scheduled job** (no live webhooks yet)
- Hybrid score (Agent 5): **weighted blend `α·graph + (1-α)·rag`**, α tunable, default 0.5

## Current → Target Mapping

| # | Role | Current file | Action |
|----|---|---|---|
| 1 | Orchestrator | `backend/graph/orchestrator.py` (rule-based) | **Rewrite as LLM supervisor node** |
| 2 | Signal Scraper | `backend/agents/signal_scraper.py` | Keep. Add scheduled-job entry point |
| 3 | Supplier Mapping | `backend/agents/supplier_mapping.py` | Keep as-is |
| 4 | Memory-aware Conversation | `backend/agents/risk_scorer.py` | **Split: keep risk-scoring as a tool, build new chat agent on top** |
| 5 | Alt Supplier (Hybrid) | `backend/agents/alt_sourcing.py` | **Add Neo4j candidate retrieval + blended scoring** |
| 6 | Report Compiler | `backend/agents/conversation.py` | **Rename → `report_compiler.py`**; remove "recommend alternatives" from prompt |

## Detailed Phases

### Phase A — Persistence layer (foundation)

1. **Mongo: chat sessions** — add to `backend/storage/mongo_client.py`:
   - `create_session(user_id) -> session_id`
   - `append_message(session_id, role, content, metadata)`
   - `get_session_messages(session_id, limit=50)`
   - `list_sessions(user_id)`
   - `list_alerts(limit=50, since=None)` (for the alerts feed)
   - `store_alert(alert_dict)` — called at end of pipeline

2. **LangGraph MongoDB checkpointer** — install `langgraph-checkpoint-mongodb`; wire `MongoDBSaver` in `backend/graph/pipeline.py` `compile_graph()`. Threads keyed by `session_id`.

3. **State additions** — in `backend/graph/state.py`: add `messages: list[dict]` (chat history), `pending_user_question: str | None`, `next_agent: str | None` (orchestrator output), `alternatives_requested: bool`.

### Phase B — Agent 5 hybrid

4. **Neo4j: alternative-supplier query** — add to `backend/storage/neo4j_client.py`:
   - `find_alternative_suppliers(affected_supplier_ids: list[str], sku_id: str | None) -> list[dict]` — returns suppliers connected to the same parts/SKUs/categories as the affected ones, excluding the affected ones themselves. Score = shared-component overlap / path proximity.

5. **Hybrid blender** — in `backend/agents/alt_sourcing.py`:
   - Add second tool `find_graph_alternatives` wrapping the Neo4j query above
   - After both tools run, normalize each list's scores to [0,1], join by `supplier_id`, compute `final_score = α·graph + (1-α)·rag` (α from env, default 0.5), sort, return top-K
   - Suppliers found by only one source keep that source's score weighted by its α-share

### Phase C — Agent 4 conversation rebuild

6. **Risk-scoring stays a callable tool** — extract the per-SKU scoring loop from current `backend/agents/risk_scorer.py` into `backend/agents/tools/score_skus.py` so the new chat agent can invoke it.

7. **New conversation agent** — replace `backend/agents/risk_scorer.py` (or new `backend/agents/agent_4_chat.py`) with an Anthropic tool-using agent. Tools:
   - `get_sku_status(sku_id)` → postgres
   - `search_history(query)` → mem0
   - `score_at_risk_skus()` → wraps step 6 (auto-runs first time per session)
   - `request_alternatives()` → flips `alternatives_requested=True` so orchestrator routes to Agent 5
   - `recall_past_session(query)` → search prior chat messages in Mongo

   System prompt: it is the operator-facing analyst. Has the current alert state, can answer questions about SKUs/events, only suggests alternatives when explicitly asked.

### Phase D — LLM Orchestrator

8. **Replace `route()` with an LLM supervisor node** — new `backend/graph/orchestrator.py`:
   - Inputs: current state (signal, severity, affected_suppliers, sku_risks, alternatives, latest user message, alternatives_requested flag)
   - Output: `next_agent` ∈ {`signal_scraper`, `supplier_mapping`, `agent_4`, `agent_5`, `report_compiler`, `END`}
   - Use Haiku, single tool `route(next_agent, reason)`
   - Conditional edge from orchestrator dispatches to the chosen node; every agent loops back to orchestrator

9. **Re-wire graph** — in `backend/graph/pipeline.py`: entry → orchestrator → fan-out, every agent → orchestrator. Fixed safety rails: severity < 0.2 short-circuits to `END` before orchestrator wastes a call.

### Phase E — Report Compiler (Agent 6)

10. **Rename + retune** `backend/agents/conversation.py` → `report_compiler.py`:
    - Drop the "Recommended actions: list alternative suppliers" line from the prompt
    - Output stored on state as `final_alert`; orchestrator hands control back to Agent 4 for delivery

### Phase F — API surface

11. **New endpoints** in `backend/api/routes.py`:
    - `POST /api/analyze` — keep (manual signal entry); now also `mongo.store_alert(...)` at the end
    - `GET /api/alerts?since=…` — list recent alerts (UI feed polls this)
    - `POST /api/chat` — `{session_id, message}` → SSE; runs the graph with the chat checkpointer thread for that session; agent_4 produces the response
    - `GET /api/sessions/{user_id}` and `GET /api/sessions/{session_id}/messages`
    - `GET /api/sku/{sku_id}` — direct postgres read for UI hover cards

### Phase G — Scheduled ingestion

12. **APScheduler job** — new `backend/jobs/scrape_signals.py`:
    - Every N minutes, pull a small set of news/weather sources (start with one or two stub fetchers — RSS or NewsAPI behind a feature flag)
    - For each new candidate signal, run the orchestrator graph with a fresh `session_id`; alerts auto-land in Mongo via step 11
    - Wire startup hook in `backend/api/routes.py` (`@app.on_event("startup")`) to start the scheduler

### Phase H — Frontend

13. Convert `frontend/src/App.tsx` into a 3-pane dashboard: left = alerts feed (polls `/api/alerts`), center = selected alert detail (current `ResultsDashboard` reused), right = chat panel hitting `/api/chat`. Remove logo references. New `ChatPanel.tsx` and `AlertsFeed.tsx`. Keep `PipelineTimeline` for the running-pipeline view inside the alert detail.

## Critical Files

- `backend/graph/pipeline.py` — re-wire to orchestrator-centric topology, add checkpointer
- `backend/graph/state.py` — add chat/orchestrator fields
- `backend/graph/orchestrator.py` — full rewrite (LLM supervisor)
- `backend/agents/risk_scorer.py` — split into chat agent + scoring tool
- `backend/agents/alt_sourcing.py` — add hybrid
- `backend/agents/conversation.py` → `report_compiler.py`
- `backend/storage/mongo_client.py` — sessions, messages, alerts list
- `backend/storage/neo4j_client.py` — alt-supplier query
- `backend/api/routes.py` — chat, alerts, sku, sessions endpoints + scheduler hook
- `backend/jobs/scrape_signals.py` — new
- `frontend/src/App.tsx` + new `ChatPanel.tsx`, `AlertsFeed.tsx`

## Reuse (don't rebuild)

- `find_direct_suppliers`, `traverse_tier2_suppliers` in `backend/storage/neo4j_client.py` — Agent 3 keeps using these
- `vector_search_suppliers`, `get_sku`, `get_supplier_sku` in `backend/storage/postgres_client.py` — used by hybrid Agent 5 and Agent 4 tools
- `mem0_client.search_memories` — used by signal_scraper and the new Agent 4 history tool
- Anthropic tool-loop pattern from existing agents — copy structure for new Agent 4 chat and orchestrator
- `RiskGauge`, `PipelineTimeline`, `ResultsDashboard` — reused inside the new dashboard layout

## Verification

1. **Unit-ish smoke tests** (run after each phase via `.venv/Scripts/python -m`):
   - Phase A: open a session, append messages, list them; checkpointer survives a process restart with the same `session_id`
   - Phase B: feed a known affected supplier; assert hybrid returns suppliers sourced from both Neo4j and pgvector with blended scores
   - Phase C: chat agent answers "what's the status of SKU X" without invoking Agent 5; explicitly asking "what are alternatives?" sets `alternatives_requested=True`
   - Phase D: orchestrator routes a fresh signal through 2→3→4→6 by default; user prompt "find me alternatives" causes a 4→5→6 detour
   - Phase G: scheduler tick produces an alert visible via `GET /api/alerts`

2. **End-to-end**: start backend (`.venv/Scripts/python main.py`) + `npm run dev`. Submit a signal → confirm alert appears in feed → open alert → chat "is SKU SKU-001 still safe?" → chat "what alternatives do we have?" → confirm Agent 5 runs and lists hybrid results.

3. **LangSmith**: every orchestrator decision and every Agent 4 tool call shows up as a traced span with reasoning visible.
