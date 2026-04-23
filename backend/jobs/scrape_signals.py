"""
Scheduled ingestion job — fetches live supply-chain signals from NewsAPI and
OpenWeatherMap, deduplicates against MongoDB, and runs each novel signal through
the Ripple pipeline so alerts land in the DB automatically.
"""
import asyncio
import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone

import httpx
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("ripple.jobs")

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
WEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
SCRAPE_INTERVAL_MINUTES = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "15"))

NEWS_QUERIES = [
    "earthquake OR tsunami OR volcanic eruption",
    "typhoon OR hurricane OR cyclone OR flood disaster",
    "port closure OR port strike OR shipping disruption",
    "supply chain shortage OR factory shutdown",
    "trade war OR sanctions OR tariff embargo",
]

_WEATHER_KW = {
    "flood", "typhoon", "hurricane", "earthquake", "storm", "blizzard",
    "drought", "wildfire", "cyclone", "tornado", "tsunami", "snowstorm",
    "heatwave", "monsoon", "volcanic", "eruption",
    "seismic", "aftershock", "landslide", "avalanche",
}
_GEO_KW = {
    "tariff", "sanction", "war", "conflict", "strike", "ban",
    "embargo", "trade war", "port closure", "blockade", "military", "geopolit",
}

_llm_client = Anthropic()


def _keyword_categorise(title: str, description: str) -> tuple[bool, str]:
    """Fallback: keyword-based relevance + category. Returns (is_relevant, category)."""
    text = (title + " " + description).lower()
    if any(k in text for k in _WEATHER_KW):
        return True, "weather"
    if any(k in text for k in _GEO_KW):
        return True, "geopolitical"
    supply_kw = {"port", "shipping", "supply chain", "factory", "manufacturing",
                 "logistics", "freight", "cargo", "semiconductor", "shortage", "disruption"}
    if any(k in text for k in supply_kw):
        return True, "other"
    return False, "other"


def _classify_articles_sync(articles: list[dict]) -> list[dict]:
    """
    Use Claude Haiku to filter out irrelevant articles (sports, entertainment, etc.)
    and assign correct categories. Falls back to keyword matching on LLM error.
    """
    if not articles:
        return []

    lines = "\n".join(
        f"{i}: {a['title']} | {(a.get('description') or '')[:180]}"
        for i, a in enumerate(articles)
    )

    prompt = (
        "You are a supply chain news classifier.\n"
        "For each article decide:\n"
        "- keep: true ONLY if about supply chains, trade, manufacturing, ports, shipping, "
        "natural disasters (earthquake, tsunami, flood, typhoon, cyclone, volcano, landslide), "
        "or geopolitical events affecting commerce. "
        "false for sports, entertainment, celebrity, lifestyle, politics unrelated to trade.\n"
        "- category: 'weather' for natural disasters/extreme weather; "
        "'geopolitical' for trade wars/sanctions/conflict/port strikes; "
        "'other' for relevant but neither.\n\n"
        f"Articles:\n{lines}\n\n"
        "Return a JSON array ONLY: "
        '[{"i":0,"keep":true,"category":"weather"},{"i":1,"keep":false,"category":"other"},...]\n'
        "No explanation, no markdown."
    )

    try:
        resp = _llm_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        classifications = json.loads(raw.strip())

        result = []
        for c in classifications:
            idx = c.get("i")
            if idx is None or not isinstance(idx, int) or idx >= len(articles):
                continue
            if not c.get("keep", False):
                continue
            article = dict(articles[idx])
            article["category"] = c.get("category", "other")
            result.append(article)
        log.info("LLM classified %d/%d articles as relevant", len(result), len(articles))
        return result

    except Exception as exc:
        log.warning("LLM article classification failed, using keyword fallback: %s", exc)
        result = []
        for a in articles:
            is_rel, cat = _keyword_categorise(a["title"], a.get("description", ""))
            if is_rel:
                article = dict(a)
                article["category"] = cat
                result.append(article)
        return result

PORTS = [
    # Asia-Pacific
    {"name": "Shanghai",    "label": "Port of Shanghai",          "region": "China",        "lat": 31.2304, "lon": 121.4737},
    {"name": "Singapore",   "label": "Port of Singapore",         "region": "Singapore",    "lat":  1.2897, "lon": 103.8501},
    {"name": "Busan",       "label": "Port of Busan",             "region": "South Korea",  "lat": 35.1028, "lon": 129.0403},
    {"name": "Hong Kong",   "label": "Port of Hong Kong",         "region": "Hong Kong",    "lat": 22.3193, "lon": 114.1694},
    {"name": "Keelung",     "label": "Port of Keelung",           "region": "Taiwan",       "lat": 25.1276, "lon": 121.7392},
    {"name": "Yokohama",    "label": "Port of Yokohama",          "region": "Japan",        "lat": 35.4437, "lon": 139.6380},
    {"name": "Osaka",       "label": "Port of Osaka",             "region": "Japan",        "lat": 34.6573, "lon": 135.4345},
    {"name": "Jakarta",     "label": "Port of Tanjung Priok",     "region": "Indonesia",    "lat": -6.1045, "lon": 106.8750},
    # Middle East
    {"name": "Jebel Ali",   "label": "Jebel Ali Port",            "region": "UAE",          "lat": 24.9857, "lon":  55.0272},
    # India
    {"name": "JNPT",        "label": "JNPT Nhava Sheva",          "region": "India",        "lat": 18.9500, "lon":  72.9500},
    {"name": "Mundra",      "label": "Port of Mundra",            "region": "India",        "lat": 22.8390, "lon":  69.7210},
    {"name": "Chennai",     "label": "Port of Chennai",           "region": "India",        "lat": 13.0827, "lon":  80.2707},
    {"name": "Cochin",      "label": "Port of Cochin",            "region": "India",        "lat":  9.9312, "lon":  76.2673},
    # Europe
    {"name": "Rotterdam",   "label": "Port of Rotterdam",         "region": "Netherlands",  "lat": 51.9244, "lon":   4.4777},
    {"name": "Hamburg",     "label": "Port of Hamburg",           "region": "Germany",      "lat": 53.5753, "lon":   9.9948},
    {"name": "Antwerp",     "label": "Port of Antwerp",           "region": "Belgium",      "lat": 51.2213, "lon":   4.4051},
    # Americas
    {"name": "Los Angeles", "label": "Port of Los Angeles",       "region": "USA",          "lat": 33.7701, "lon":-118.1937},
    {"name": "New York",    "label": "Port of New York",          "region": "USA",          "lat": 40.6840, "lon": -74.0440},
]

# OWM condition codes that imply port disruption
_DISRUPTIVE_IDS: set[int] = (
    set(range(200, 300))   # thunderstorm
    | set(range(502, 532)) # heavy rain / showers
    | set(range(600, 623)) # snow / sleet
    | set(range(701, 782)) # mist, smoke, haze, fog, dust, ash, squall, tornado
    | set(range(900, 903)) # extreme
    | {781}                # tornado (duplicate safety)
)


def _weather_text(port: dict, data: dict) -> str | None:
    cond_id  = (data.get("weather") or [{}])[0].get("id", 800)
    wind     = data.get("wind", {}).get("speed", 0.0)
    vis      = data.get("visibility", 10000)
    desc     = (data.get("weather") or [{}])[0].get("description", "clear")
    temp     = data.get("main", {}).get("temp", 20.0)

    if cond_id not in _DISRUPTIVE_IDS and wind <= 15 and vis >= 1000:
        return None

    notes: list[str] = []
    if cond_id in _DISRUPTIVE_IDS:
        notes.append(desc)
    if wind > 15:
        notes.append(f"wind {wind:.0f} m/s")
    if vis < 1000:
        notes.append(f"visibility {vis}m")

    return (
        f"Weather alert at {port['label']}: {', '.join(notes)}. "
        f"Temperature {temp:.0f}°C. Potential impact on port operations and cargo handling."
    )


async def fetch_news_signals() -> list[str]:
    if not NEWS_API_KEY:
        log.warning("NEWS_API_KEY not set — skipping news fetch")
        return []

    raw_articles: list[dict] = []
    async with httpx.AsyncClient(timeout=12) as client:
        for query in NEWS_QUERIES:
            try:
                resp = await client.get(
                    "https://newsapi.org/v2/everything",
                    params={
                        "q": query,
                        "apiKey": NEWS_API_KEY,
                        "pageSize": 10,
                        "sortBy": "publishedAt",
                        "language": "en",
                    },
                )
                resp.raise_for_status()
                for art in resp.json().get("articles", []):
                    title = (art.get("title") or "").strip()
                    desc  = (art.get("description") or "").strip()
                    src   = art.get("source", {}).get("name", "News")
                    if not title or "[Removed]" in title:
                        continue
                    raw_articles.append({
                        "title": title,
                        "description": desc,
                        "url": art.get("url") or "",
                        "source": src,
                        "image": art.get("urlToImage") or "",
                        "content": (art.get("content") or "").strip(),
                        "published_at": art.get("publishedAt") or datetime.now(timezone.utc).isoformat(),
                    })
            except Exception as exc:
                log.warning("NewsAPI error (query=%r): %s", query, exc)

    if not raw_articles:
        return []

    # Skip URLs already in MongoDB — avoid wasting LLM tokens re-classifying stored articles
    from backend.storage.mongo_client import get_existing_article_urls, store_news_articles
    known_urls = get_existing_article_urls([a["url"] for a in raw_articles if a.get("url")])
    new_articles = [a for a in raw_articles if a.get("url") not in known_urls]
    log.info("Scraper: %d fetched, %d already stored, %d new → LLM", len(raw_articles), len(known_urls), len(new_articles))

    if not new_articles:
        log.info("No new articles — skipping LLM classification")
        return []

    # LLM batch-classifies only NEW articles: filters noise and assigns category
    loop = asyncio.get_event_loop()
    articles_to_store = await loop.run_in_executor(None, _classify_articles_sync, new_articles)

    signals = [
        f"[{a['source']}] {a['title']}. {a.get('description', '')}".strip(". ")
        for a in articles_to_store
    ]

    try:
        store_news_articles(articles_to_store)
    except Exception as exc:
        log.warning("Failed to store news articles: %s", exc)

    return signals


async def fetch_disaster_signals() -> tuple[list[str], list[dict]]:
    """Real-time disaster feeds (no API key, no 24h delay):
    - USGS significant earthquakes (past 24h)
    - GDACS RSS (earthquakes, tsunamis, cyclones, floods, volcanoes)
    Returns (signal_strings_for_pipeline, article_dicts_for_news_feed).
    Articles are pre-categorised as 'weather' — bypass LLM classification.
    """
    signals: list[str] = []
    articles: list[dict] = []

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        # --- USGS: significant earthquakes past 24h ---
        try:
            r = await client.get(
                "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_day.geojson"
            )
            r.raise_for_status()
            for feat in r.json().get("features", []):
                p = feat.get("properties", {}) or {}
                mag = p.get("mag")
                place = p.get("place") or "unknown location"
                title = p.get("title") or f"M{mag} earthquake near {place}"
                url = p.get("url") or ""
                time_ms = p.get("time")
                published_at = (
                    datetime.fromtimestamp(time_ms / 1000, tz=timezone.utc).isoformat()
                    if time_ms else datetime.now(timezone.utc).isoformat()
                )
                tsunami = bool(p.get("tsunami"))
                desc = f"Magnitude {mag} earthquake near {place}."
                if tsunami:
                    desc += " Tsunami warning issued — coastal ports at risk."
                signals.append(f"[USGS] {title}. {desc}")
                articles.append({
                    "title":        title,
                    "description":  desc,
                    "url":          url,
                    "source":       "USGS",
                    "image":        "",
                    "content":      desc,
                    "published_at": published_at,
                    "category":     "weather",
                })
        except Exception as exc:
            log.warning("USGS fetch error: %s", exc)

        # --- GDACS: current global disaster alerts (RSS) ---
        try:
            import feedparser
            from time import mktime
            r = await client.get("https://www.gdacs.org/xml/rss.xml")
            r.raise_for_status()
            feed = feedparser.parse(r.text)
            for entry in feed.entries[:25]:
                title = (getattr(entry, "title", "") or "").strip()
                desc  = (getattr(entry, "summary", "") or "").strip()[:500]
                url   = getattr(entry, "link", "") or ""
                # Normalise to ISO 8601 so Mongo string-sort on published_at works across USGS+GDACS+NewsAPI
                parsed_time = getattr(entry, "published_parsed", None)
                if parsed_time:
                    published = datetime.fromtimestamp(mktime(parsed_time), tz=timezone.utc).isoformat()
                else:
                    published = datetime.now(timezone.utc).isoformat()
                if not title:
                    continue
                signals.append(f"[GDACS] {title}. {desc}")
                articles.append({
                    "title":        title,
                    "description":  desc,
                    "url":          url,
                    "source":       "GDACS",
                    "image":        "",
                    "content":      desc,
                    "published_at": published,
                    "category":     "weather",
                })
        except Exception as exc:
            log.warning("GDACS fetch error: %s", exc)

    log.info("Disaster feeds: %d signals from USGS+GDACS", len(signals))
    return signals, articles


async def fetch_weather_signals() -> list[str]:
    if not WEATHER_API_KEY:
        log.warning("OPENWEATHER_API_KEY not set — skipping weather fetch")
        return []
    signals: list[str] = []
    async with httpx.AsyncClient(timeout=12) as client:
        for port in PORTS:
            try:
                resp = await client.get(
                    "https://api.openweathermap.org/data/2.5/weather",
                    params={
                        "lat": port["lat"], "lon": port["lon"],
                        "appid": WEATHER_API_KEY, "units": "metric",
                    },
                )
                resp.raise_for_status()
                text = _weather_text(port, resp.json())
                if text:
                    signals.append(text)
                    log.info("Disruptive weather at %s", port["name"])
            except Exception as exc:
                log.warning("Weather fetch error (%s): %s", port["name"], exc)
    return signals


async def fetch_all_port_weather() -> list[dict]:
    """Fetch current weather for every tracked port — full data, not filtered for disruption."""
    if not WEATHER_API_KEY:
        return []

    sem = asyncio.Semaphore(5)  # max 5 concurrent OWM requests

    async def _fetch_one(client: httpx.AsyncClient, port: dict):
        async with sem:
            return await client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"lat": port["lat"], "lon": port["lon"], "appid": WEATHER_API_KEY, "units": "metric"},
            )

    async with httpx.AsyncClient(timeout=15) as client:
        responses = await asyncio.gather(
            *[_fetch_one(client, p) for p in PORTS],
            return_exceptions=True,
        )
    results: list[dict] = []
    for port, resp in zip(PORTS, responses):
        if isinstance(resp, Exception):
            log.warning("Port weather error (%s): %s", port["name"], resp)
            continue
        try:
            resp.raise_for_status()
            data = resp.json()
            cond = (data.get("weather") or [{}])[0]
            cond_id = cond.get("id", 800)
            results.append({
                "name":         port["name"],
                "label":        port["label"],
                "region":       port.get("region", ""),
                "lat":          port["lat"],
                "lon":          port["lon"],
                "temp":         round(data.get("main", {}).get("temp", 0), 1),
                "feels_like":   round(data.get("main", {}).get("feels_like", 0), 1),
                "humidity":     data.get("main", {}).get("humidity", 0),
                "description":  cond.get("description", "clear sky"),
                "condition_id": cond_id,
                "icon":         cond.get("icon", "01d"),
                "wind_speed":   round(data.get("wind", {}).get("speed", 0), 1),
                "visibility":   data.get("visibility", 10000),
                "is_disruptive": cond_id in _DISRUPTIVE_IDS,
            })
        except Exception as exc:
            log.warning("Port weather parse error (%s): %s", port["name"], exc)
    return results


def _hash(text: str) -> str:
    return hashlib.sha256(text[:300].encode()).hexdigest()[:20]


def _get_seen_hashes() -> set[str]:
    from backend.storage.mongo_client import get_db
    try:
        docs = get_db().signal_hashes.find({}, {"_id": 0, "h": 1})
        return {d["h"] for d in docs}
    except Exception:
        return set()


def _mark_hashes_seen(hashes: list[str]) -> None:
    if not hashes:
        return
    from backend.storage.mongo_client import get_db
    try:
        get_db().signal_hashes.insert_many(
            [{"h": h, "ts": datetime.now(timezone.utc)} for h in hashes]
        )
    except Exception:
        pass


# Lazy singleton — one graph per process, created on first background run
_pipeline_graph = None


def _get_pipeline():
    global _pipeline_graph
    if _pipeline_graph is None:
        from backend.graph.pipeline import compile_graph
        _pipeline_graph = compile_graph()
    return _pipeline_graph


def _invoke_pipeline_sync(signal_text: str, session_id: str) -> None:
    """Run the full agent pipeline synchronously (no SSE). Stores alert to Mongo."""
    from backend.graph.state import SupplyChainState
    from backend.storage.mongo_client import store_alert

    initial: SupplyChainState = {
        "raw_signal": signal_text,
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
    try:
        result = _get_pipeline().invoke(initial, config=config)
        if result.get("final_alert"):
            store_alert({
                "session_id": session_id,
                "user_id": "auto",
                "signal": signal_text,
                "signal_type": result.get("signal_type"),
                "severity_score": result.get("severity_score"),
                "alert_type": result.get("alert_type"),
                "final_alert": result.get("final_alert"),
                "affected_entities": result.get("affected_entities", []),
                "affected_suppliers": result.get("affected_suppliers", []),
                "sku_risks": [
                    {
                        **r,
                        "runout_date": r["runout_date"].isoformat()
                        if isinstance(r.get("runout_date"), datetime)
                        else r.get("runout_date"),
                    }
                    for r in result.get("sku_risks", [])
                ],
                "alternatives": result.get("alternatives", []),
                "tier2_exposure": result.get("tier2_exposure"),
                "invisible_risk": result.get("invisible_risk"),
            })
            log.info("Alert stored for session %s (severity=%.2f)", session_id, result.get("severity_score", 0))
        else:
            log.info("Signal below threshold or no alert generated for session %s", session_id)
    except Exception as exc:
        log.error("Pipeline error for signal '%.60s…': %s", signal_text, exc)


# --- Job state (read by /api/scrape-status) ---

job_state: dict = {
    "last_run": None,
    "running": False,
    "signals_found": 0,
    "signals_new": 0,
    "error": None,
}


async def scrape_and_ingest() -> dict:
    """Fetch signals, skip already-seen ones, run pipeline for each novel signal."""
    if job_state["running"]:
        return {"skipped": "already_running"}

    job_state["running"] = True
    job_state["error"] = None

    try:
        news_result, weather_result, disaster_result = await asyncio.gather(
            fetch_news_signals(),
            fetch_weather_signals(),
            fetch_disaster_signals(),
            return_exceptions=True,
        )

        disaster_signals: list[str] = []
        disaster_articles: list[dict] = []
        if isinstance(disaster_result, tuple) and len(disaster_result) == 2:
            disaster_signals, disaster_articles = disaster_result
            # Store disaster articles into news feed (dedupe by URL happens via upsert)
            if disaster_articles:
                try:
                    from backend.storage.mongo_client import store_news_articles
                    store_news_articles(disaster_articles)
                except Exception as exc:
                    log.warning("Failed to store disaster articles: %s", exc)

        all_signals: list[str] = [
            *(news_result if isinstance(news_result, list) else []),
            *(weather_result if isinstance(weather_result, list) else []),
            *disaster_signals,
        ]

        seen = _get_seen_hashes()
        novel = [(s, _hash(s)) for s in all_signals if _hash(s) not in seen]

        job_state["signals_found"] = len(all_signals)
        job_state["signals_new"]   = len(novel)
        job_state["last_run"]      = datetime.now(timezone.utc).isoformat()

        log.info("Scrape complete: %d signals, %d new", len(all_signals), len(novel))

        loop = asyncio.get_event_loop()
        new_hashes: list[str] = []
        for signal_text, h in novel:
            sid = str(uuid.uuid4())
            await loop.run_in_executor(None, _invoke_pipeline_sync, signal_text, sid)
            new_hashes.append(h)

        _mark_hashes_seen(new_hashes)
        return {"signals_found": len(all_signals), "signals_new": len(novel)}

    except Exception as exc:
        job_state["error"] = str(exc)
        log.error("scrape_and_ingest failed: %s", exc)
        return {"error": str(exc)}
    finally:
        job_state["running"] = False


async def scheduler_loop() -> None:
    """Long-running asyncio task started on app startup."""
    log.info("Ripple scraper started (interval: %d min)", SCRAPE_INTERVAL_MINUTES)
    await scrape_and_ingest()          # run immediately on startup
    while True:
        await asyncio.sleep(SCRAPE_INTERVAL_MINUTES * 60)
        await scrape_and_ingest()
