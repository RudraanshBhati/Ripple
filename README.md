# Ripple — Supply Chain Intelligence Platform

Multi-agent early warning system for supply chain disruptions. Monitors weather, geopolitical events, and port conditions in real-time, maps supplier exposure, and suggests alternative sourcing — all through a conversational interface.

## Architecture

```
Orchestrator (LangGraph supervisor)
├── Signal Scraper      — scrapes & classifies news/disaster feeds via Claude
├── Supplier Mapping    — traverses Neo4j supplier graph (tier-1/2/3)
├── Alt Sourcing        — hybrid graph + RAG re-scoring of alternatives
├── Agent 4 Chat        — memory-aware chat (mem0 + MongoDB + pgvector)
└── Report Compiler     — assembles final risk report
```

**Stack:** FastAPI · LangGraph · Anthropic Claude · MongoDB · PostgreSQL (pgvector) · Neo4j · Redis · Ollama

---

## Prerequisites

Install these before cloning:

| Tool | Mac install |
|---|---|
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Download from docker.com |
| [uv](https://docs.astral.sh/uv/) | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| [Node.js 20+](https://nodejs.org/) | `brew install node` |
| [Ollama](https://ollama.com/) | `brew install ollama` |

---

## Setup

### 1. Clone & configure environment

```bash
git clone https://github.com/RudraanshBhati/Ripple.git
cd Ripple
cp .env.example .env
```

Open `.env` and fill in your API keys:

```
ANTHROPIC_API_KEY=sk-ant-...       # required — all LLM calls
NEWS_API_KEY=...                   # newsapi.org free tier
OPENWEATHER_API_KEY=...            # openweathermap.org free tier
LANGCHAIN_API_KEY=...              # optional — LangSmith tracing
```

Everything else (DB passwords, ports) can stay as the defaults in `.env.example`.

### 2. Start infrastructure

```bash
docker compose up -d
```

This starts MongoDB, PostgreSQL (pgvector), Neo4j, and Redis. Wait ~30 seconds for Neo4j to be ready (it's the slowest to start).

Check they're all healthy:

```bash
docker compose ps
```

### 3. Pull the embedding model

```bash
ollama serve &          # start ollama in background (or open a new terminal)
ollama pull nomic-embed-text
```

### 4. Install Python dependencies

```bash
uv sync
```

### 5. Seed the database

```bash
uv run python backend/seeds/run_all.py
```

This seeds the Neo4j supplier graph, PostgreSQL SKU inventory, pgvector embeddings, and demo memories. Takes ~2–3 minutes on first run.

### 6. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

---

## Running

Open three terminals:

```bash
# Terminal 1 — backend (port 8001)
uv run python main.py

# Terminal 2 — frontend (port 5173)
cd frontend && npm run dev

# Terminal 3 — expose via ngrok (optional, for demo on other devices)
ngrok http 5173
```

Open [http://localhost:5173](http://localhost:5173).

---

## Project Structure

```
Ripple/
├── main.py                    # FastAPI entry point (port 8001)
├── backend/
│   ├── agents/                # 6 LangGraph agents
│   ├── api/routes.py          # REST + SSE endpoints
│   ├── graph/                 # LangGraph pipeline wiring
│   ├── jobs/scrape_signals.py # News + disaster feed scraper
│   ├── seeds/                 # DB seed scripts
│   └── storage/               # DB clients (mongo, neo4j, postgres, redis)
├── frontend/
│   └── src/
│       ├── components/        # React UI components
│       └── hooks/             # API hooks (useChat, useAlerts, etc.)
├── docker-compose.yml
└── pyproject.toml
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/alerts` | Fetch current alerts feed |
| POST | `/api/analyze` | Run full pipeline (SSE stream) |
| POST | `/api/chat` | Chat with Agent 4 |
| GET | `/api/news` | News by category (weather/geopolitical/other) |
| POST | `/api/trigger-scrape` | Manually trigger news scrape |
| POST | `/api/clear-cache` | Wipe cache + rescrape |
| GET | `/api/port-weather` | Port weather (10-min cache) |
| GET | `/api/health` | Health check |

---

## Troubleshooting

**Neo4j won't connect** — it takes ~30s to start. Run `docker compose logs neo4j` to check.

**Ollama embeddings fail** — make sure `ollama serve` is running and `nomic-embed-text` is pulled (`ollama list`).

**Port 8001 already in use** — find and kill the process: `lsof -i :8001 | grep LISTEN` then `kill <PID>`.

**Seed script fails on pgvector** — the pgvector extension is auto-enabled in the Docker image. If you see `extension not found`, run: `docker compose down -v && docker compose up -d` to reset volumes.
