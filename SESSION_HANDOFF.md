# Ripple — New Session Handoff

Use this file to get up to speed quickly. It covers: signal scraper internals, all 4 demo scenarios, and the Mac dashboard issue.

---

## How to Run

```bash
# Terminal 1 — backend (port 8001)
uv run python main.py

# Terminal 2 — frontend (port 5173)
cd frontend && npm run dev
```

Docker must be running first: `docker compose up -d`  
Ollama must be running: `ollama serve` + `ollama pull nomic-embed-text`

---

## Signal Scraper — How It Works

**File:** `backend/jobs/scrape_signals.py`  
**Triggered by:** FastAPI lifespan on startup, then every 15 minutes. Also manually via `POST /api/trigger-scrape` or `POST /api/clear-cache`.

### 3 parallel fetch sources

| Source | What it fetches | API key needed |
|---|---|---|
| `fetch_news_signals()` | NewsAPI — 5 OR-syntax queries across earthquake, typhoon, port strikes, supply chain, trade war | `NEWS_API_KEY` |
| `fetch_weather_signals()` | OpenWeatherMap — current weather at 18 tracked ports, filters for disruptive conditions only | `OPENWEATHER_API_KEY` |
| `fetch_disaster_signals()` | USGS (significant earthquakes past 24h) + GDACS RSS (all global disasters) — **no API key** | none |

### LLM classification step (NewsAPI articles only)

After fetching, NewsAPI articles go through **Claude Haiku batch classification**:
- Prompt asks: keep true/false + category (weather / geopolitical / other)
- Drops sports, entertainment, celebrity, lifestyle
- Falls back to keyword matching if LLM call fails
- USGS and GDACS articles skip this step — pre-categorised as `weather`

### Deduplication

Two layers:
1. **URL dedup** — before LLM call, articles with URLs already in MongoDB are skipped (`get_existing_article_urls`)
2. **Signal hash dedup** — SHA-256 first 300 chars of signal text, stored in `signal_hashes` collection. Prevents re-running the pipeline on the same event.

### IMPORTANT: Dashboard load vs. pipeline processing are separate

**The news dashboard loads instantly.** `GET /api/news` reads directly from MongoDB.
Articles are stored to MongoDB after the batch LLM classification step — before any pipeline runs.
If you see 45 novel signals, the dashboard still loads immediately.

The pipeline running 45 times is a background job that populates the **alerts feed**, not the news columns.
Do not conflate scraper processing time with dashboard load time — they are independent.

### Pipeline invocation (per novel signal)

Each new, unseen signal runs through the full LangGraph pipeline synchronously via `_invoke_pipeline_sync()`:
```
Orchestrator → Agent 2 (classify) → Agent 3 (supplier map) → Agent 4 (SKU score) → Agent 5 (alt sourcing, if severity ≥ 0.5) → Agent 6 (report compile) → END
```
Result stored to `alerts` collection in MongoDB.

### Port weather (separate from scraper)

`GET /api/port-weather` fetches all 18 ports in parallel (semaphore-limited to 5 concurrent) and caches for 10 minutes. This powers the port weather strip in the news dashboard. It is NOT a signal — it is display-only weather data.

### Tracked ports (18 total)

Asia-Pacific: Shanghai, Singapore, Busan, Hong Kong, Keelung, Yokohama, Osaka, Jakarta  
Middle East: Jebel Ali  
India: JNPT Nhava Sheva, Mundra, Chennai, Cochin  
Europe: Rotterdam, Hamburg, Antwerp  
Americas: Los Angeles, New York

---

## Agent 2 — Signal Classifier

**File:** `backend/agents/signal_scraper.py`

Given `raw_signal` text, it:
1. Calls `search_historical_signals` (mem0) to calibrate severity against past events
2. Calls `finish_analysis` with: `signal_type`, `severity_score` (0–1), `affected_entities`, `reasoning`

Severity thresholds:
- `< 0.2` → Orchestrator short-circuits to `no_alert`
- `0.2–0.5` → pipeline runs but Agent 5 skipped
- `>= 0.5` → full pipeline including Agent 5 (alt sourcing)

---

## Demo Scenarios (4 pre-seeded)

Seeded via: `uv run python scripts/seed_demo.py --clear`  
Stored in MongoDB `alerts` collection with `user_id: "demo"`.

### Scenario 1 — US-China Tariff War (CRITICAL 0.92)

**Signal:** US imposes 145% tariffs on Chinese electronics. China retaliates with gallium/germanium/antimony export halt. Shenzhen + Dongguan export lines suspended. Indian assembly plants (Tata Hosur, Foxconn Chennai) report PCB shortfalls.

**Affected suppliers:** TaiwanChipCo (SUP-001, Taiwan, tier-1), SinoBoard Ltd (SUP-003, China, tier-1), DutchParts BV (SUP-002, Netherlands, **tier-2 invisible risk** — sources PCBs from SinoRaw Ltd Zhengzhou)

**At-risk SKUs:**
- `SKU-MCU-01`: gap −11 days, risk 0.976 — stockout in 10 days, lead time 21 days
- `SKU-PCB-02`: gap −10 days, risk 0.843

**Alternatives:** Dixon Technologies India (16d, 0.88 sim), Kaynes Technology India (18d, 0.83), Vietronics Vietnam (14d, 0.79)

**Key talking point:** India-sourced alternatives qualify for US tariff exemptions under the Indo-US bilateral trade framework.

---

### Scenario 2 — Cyclone Remal: Chennai Port Closure (HIGH 0.81)

**Signal:** Category 4 cyclone over Bay of Bengal. Chennai Port suspended (72h+ minimum). Cochin Port on Alert Level 2. Tata Motors, Hyundai India, Foxconn Chennai halting inbound logistics.

**Affected suppliers:** Chennai Auto Parts Co. (SUP-006), Tata Electronic Components (SUP-007), Sundaram Fasteners (SUP-008), Cochin Chemical Works (SUP-009, tier-2)

**At-risk SKUs:**
- `SKU-AUTO-05` (wiring harnesses): gap −14 days, risk 0.875
- `SKU-PCB-02`: gap −10 days, risk 0.843
- `SKU-CHEM-03`: gap −10 days, risk 0.817

**Alternatives:** Sona BLW Precision Gujarat (10d, 0.85), Motherson Sumi Wiring Pune (12d, 0.82), Perodua Auto Parts Malaysia (14d, 0.74)

**Key talking point:** Reroute via Mundra (Gujarat) as bridge port + pre-position safety stock at Singapore.

---

### Scenario 3 — Red Sea / Suez Suspended: Houthi Escalation (HIGH 0.78)

**Signal:** Coordinated Houthi drone strikes on 3 vessels. MSC, Maersk, CMA CGM suspend ALL Suez transits. Cape rerouting adds 18–22 days. JNPT and Mundra face delays from Jebel Ali congestion.

**Affected suppliers:** DutchParts BV (SUP-002, Netherlands, tier-1), Hamburg Chemicals GmbH (SUP-010), Antwerp Auto Electronics (SUP-011, Belgium)

**At-risk SKUs:**
- `SKU-MCU-03`: gap −29 days, risk 0.867 — runout in 14 days, new lead time 43 days
- `SKU-CHEM-03`: gap −19 days, risk 0.791

**Alternatives:** Divi's Laboratories Hyderabad (7d, 0.87), Bosch India Nashik (9d, 0.80), Warsaw Precision Parts Poland (21d, 0.72)

**Key talking point:** Rotterdam → Jebel Ali → JNPT transshipment breaks at Jebel Ali. Domestic Indian bridge suppliers available in 7–9 days vs 43.

---

### Scenario 4 — Taiwan Earthquake: Semiconductor Collapse (CRITICAL 0.95) ⭐ RECOMMENDED FOR DEMO

**Signal:** 7.6 magnitude, Hualien. TSMC Fab 18 (3nm/5nm) suspended. Keelung Port structural inspection — container handling suspended. TaiwanChipCo force majeure. Strong aftershocks expected 72h.

**Affected suppliers:** TaiwanChipCo (SUP-001, Taiwan, tier-1), SinoBoard Ltd (SUP-003, China, **tier-2 — supplies TSMC packaging materials**, blocked by US export controls), Keelung PCB Works (SUP-004, Taiwan, tier-1 port exposure)

**At-risk SKUs:**
- `SKU-MCU-01`: gap −15 days, risk 0.987, stockout in **6 days**
- `SKU-MCU-03`: gap −14 days, risk 0.951, stockout in 14 days
- `SKU-PCB-02`: gap −18 days, risk 0.918

**Alternatives:** Renesas Electronics Japan (14d, 0.91 sim — **immediate bridge**), Samsung Foundry Pyeongtaek (16d, 0.84), Micron Sanand India Semiconductor Mission (18d, 0.76 — medium-term Q3 2026)

**Key talking point:** Invisible tier-2 risk — SinoBoard's overflow capacity blocked by US export controls. 340+ global OEMs affected. Renesas Japan immediate action; fast-track Micron Sanand vendor onboarding for Q3 capacity.

---

## What-If Simulation (Agent 4 Chat)

As of latest commit, Agent 4 has a `simulate_scenario` tool. Ask any what-if in chat:

| Question type | Parameters used |
|---|---|
| "What if disruption lasts 45 more days?" | `disruption_extension_days: 45` |
| "What if demand spikes 50%?" | `demand_multiplier: 1.5` |
| "What if we air freight — 5 day lead time?" | `lead_time_override_days: 5` |

Returns: per-SKU `delta_gap_days`, `verdict` (WORSE / BETTER / MARGINAL), and simulated risk scores. Does not modify state.

---

## Mac Dashboard Issue — Known Context

The dashboard (`/news` tab) works on Windows but has issues on Mac. Things to check:

### 1. Port weather strip shows "No weather data"
**Cause:** `OPENWEATHER_API_KEY` missing or not loaded from `.env`.  
**Check:** `curl http://localhost:8001/api/port-weather` — if returns `{"ports": []}`, the key is missing.  
**Fix:** Copy `.env` from Windows repo (or set the key in the Mac `.env`).

### 2. News columns all empty after seeding
**Cause:** The news articles require `NEWS_API_KEY`. Without it, `fetch_news_signals()` returns empty.  
USGS and GDACS articles ARE fetched without any key — but they'll only appear if a scrape has run.  
**Fix:** Hit `POST /api/trigger-scrape` (or "Scan Now" button) after backend starts. Wait 10–20 seconds, then click Refresh.

### 3. Dashboard height layout looks wrong / columns too short or too tall
**Cause:** The news grid uses `height: calc(100vh - 380px)` — if Mac browser has different toolbar height or zoom level, this can clip the columns.  
**File:** `frontend/src/components/NewsDashboard.tsx` line 233.  
**Quick fix:** Change `380px` to `420px` or use `minHeight: 480` only without the fixed height.

### 4. Articles show but port weather strip is missing
**Cause:** On Mac + Safari, `overflowX: "auto"` on the port strip sometimes collapses to zero height if flex children have `flexShrink: 0` without explicit container height.  
**File:** `NewsDashboard.tsx` — `PortWeatherStrip` component.  
**Fix:** Add `height: 180` or `minHeight: 160` to the inner scroll container div.

### 5. API calls failing (CORS / proxy)
**Cause:** Vite proxies `/api` to `http://localhost:8001`. On Mac, if backend isn't running, all API calls silently fail.  
**Check:** `curl http://localhost:8001/api/health` should return `{"status": "ok"}`.  
If that fails — backend isn't running or is on a different port. Check `main.py` — should be `uvicorn.run(app, host="0.0.0.0", port=8001)`.

### 6. Ollama not found (alt sourcing / chat breaks, not dashboard)
**Mac install:** `brew install ollama` then `ollama serve` (separate terminal) then `ollama pull nomic-embed-text`.  
If `ollama serve` isn't running, Agent 5 and mem0 embeddings fail silently — chat still works but alt sourcing returns empty.

---

## Key File Locations

| Component | File |
|---|---|
| Scraper job | `backend/jobs/scrape_signals.py` |
| Signal classifier (Agent 2) | `backend/agents/signal_scraper.py` |
| Supplier mapping (Agent 3) | `backend/agents/supplier_mapping.py` |
| Chat + what-if (Agent 4) | `backend/agents/agent_4_chat.py` |
| Alt sourcing (Agent 5) | `backend/agents/alt_sourcing.py` |
| Report compiler (Agent 6) | `backend/agents/report_compiler.py` |
| Orchestrator routing | `backend/graph/orchestrator.py` |
| LangGraph pipeline wiring | `backend/graph/pipeline.py` |
| All API endpoints | `backend/api/routes.py` |
| News dashboard component | `frontend/src/components/NewsDashboard.tsx` |
| Demo scenarios seed | `scripts/seed_demo.py` |
| Demo presentation script | `DEMO_SCRIPT.md` |
