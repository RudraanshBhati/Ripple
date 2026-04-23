# Ripple — Session Status
**Last updated: 2026-04-17**

---

## Where We Are

All infrastructure and seed data is complete. Two agents are written and verified.

### Done
| Step | Status |
|---|---|
| Step 1 — Scaffold + Config | DONE |
| Step 2 — Storage clients (Neo4j, Postgres, Mongo, Redis, mem0) | DONE |
| Step 3 — Seed data (Postgres, Neo4j, pgvector embeddings, mem0 memories) | DONE |
| Step 4 — State TypedDict + Orchestrator routing | DONE |
| Step 5 — Agent 3: Supplier Mapping | DONE + VERIFIED |
| Step 6 — Agent 4: Risk Scorer | DONE + VERIFIED |
| Step 7 — Agent 2: Signal Scraper | DONE + VERIFIED |
| Step 8 — Agent 5: Alt Sourcing RAG | DONE + VERIFIED |
| Step 9 — Agent 1: Conversation | DONE + VERIFIED |
| Step 10 — LangGraph pipeline wiring | DONE + VERIFIED (all 3 scenarios) |

### Pending
- Step 11 — FastAPI + SSE endpoint
- Step 12 — E2E demo verification (3 scenarios)
- Step 13 — React frontend

---

## First Thing Tomorrow

**Run Agent 4 checkpoint** — verify risk scorer works before building more agents:

```
cd d:/Ripple && uv run python -c "
from backend.agents.risk_scorer import run
from datetime import datetime

state = {
    'raw_signal': 'Severe flooding in Zhengzhou, Henan province',
    'affected_suppliers': [
        {'supplier_id': 'SUP-003', 'name': 'SinoRaw Ltd', 'country': 'CN', 'tier': 2, 'exposure_type': 'direct'},
        {'supplier_id': 'SUP-002', 'name': 'DutchParts BV', 'country': 'NL', 'tier': 1, 'exposure_type': 'tier2'},
    ],
    'reasoning_trace': [],
    'session_id': 'test',
    'timestamp': datetime.now(),
}

result = run(state)
for risk in result['sku_risks']:
    print(f\"{risk['sku_id']}: gap_days={risk['gap_days']}, risk_score={risk['risk_score']}, confidence={risk['confidence']}\")
print()
for t in result['reasoning_trace']:
    print(t)
"
```

**Expected output:**
- `SKU-MCU-03: gap_days=-13.3, risk_score=0.476, confidence=0.9` (risk_score = stockout_days/lead_time)

---

## Services to Start

Before any work, make sure these are running:

```
docker start ripple-postgres ripple-neo4j ripple-mongo ripple-redis
ollama serve   # in a separate terminal (needed for embeddings)
```

Verify containers: `docker ps`

---

## Key Files

| File | Purpose |
|---|---|
| `backend/agents/supplier_mapping.py` | Agent 3 — finds tier-2 invisible risk via Neo4j traversal |
| `backend/agents/risk_scorer.py` | Agent 4 — calculates SKU runout dates and gap_days |
| `backend/agents/orchestrator.py` | Routing logic, SEVERITY_THRESHOLD=0.2 (hardcoded, never change) |
| `backend/graph/state.py` | SupplyChainState TypedDict shared across all agents |
| `backend/storage/neo4j_client.py` | traverse_tier2_suppliers() — the demo wow-moment query |
| `backend/storage/postgres_client.py` | get_skus_for_supplier(), vector_search_suppliers() |
| `backend/storage/mem0_client.py` | search_memories(), add_memory() — uses filters= not user_id= |
| `backend/seeds/run_all.py` | Reruns all seeds if needed |

---

## Agent 3 Checkpoint (already verified)

Input: `affected_entities: ["Zhengzhou"]`

Output:
```
tier2_exposure: True
invisible_risk: True
suppliers found: 2
 - SUP-003 SinoRaw Ltd (CN, direct)
 - SUP-002 DutchParts BV (NL, tier2)  ← the wow moment
```

---

## 3 Demo Scenarios (verification targets for Step 12)

```
Scenario 1 — Taiwan Port Strike
Input:  {"content": "Taiwan port workers strike, Keelung port disrupted"}
Expect: severity~0.85, SKU-MCU-01 gap_days=-11, CRITICAL
        Alternatives: VN-FAB-03 (14d), IN-CHIP-01 (18d)

Scenario 2 — Zhengzhou Flooding (WOW MOMENT)
Input:  {"content": "Severe flooding in Zhengzhou, Henan province"}
Expect: DutchParts BV flagged via tier-2 chain (SinoRaw Ltd in Zhengzhou)
        invisible_risk=True, tier2_exposure=True, SKU-MCU-03 gap_days=-14
        Alert: "Invisible tier-2 risk detected — your 'safe' Dutch supplier..."

Scenario 3 — Rotterdam Fog (false positive prevention)
Input:  {"content": "Fog at Rotterdam port, reduced visibility"}
Expect: severity=0.18 -> no_alert branch
        "Below threshold. Rotterdam fog historically resolves in ~6hrs."
```

---

## Known Issues / Notes

- mem0 `get_all()` and `search()` use `filters={"user_id": "..."}` not `user_id=` (API changed in recent version)
- mem0 vector table is `mem0` in public schema (not `vecs.mem0`)
- spaCy warnings from mem0 are harmless — ignore them
- Docker container names: `ripple-postgres`, `ripple-neo4j`, `ripple-mongo`, `ripple-redis`
- Ollama runs outside Docker — start with `ollama serve`
- Embedding model: `nomic-embed-text` (768-dim) — mem0 config has `embedding_model_dims: 768`
