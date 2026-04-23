import os
import uuid
from datetime import datetime, timezone
from pymongo import MongoClient, DESCENDING
from dotenv import load_dotenv

load_dotenv()

_client = None
_db = None


def get_db():
    global _client, _db
    if _client is None:
        _client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/ripple"))
        _db = _client.get_default_database()
    return _db


def get_client() -> MongoClient:
    get_db()
    return _client


# --- Signals (audit trail) ---

def insert_signal(signal: dict) -> str:
    signal["logged_at"] = datetime.now(timezone.utc)
    result = get_db().signals.insert_one(signal)
    return str(result.inserted_id)


def get_recent_signals(limit: int = 20) -> list[dict]:
    docs = get_db().signals.find().sort("logged_at", DESCENDING).limit(limit)
    return [{**d, "_id": str(d["_id"])} for d in docs]


def get_signals_by_type(signal_type: str, limit: int = 10) -> list[dict]:
    docs = (
        get_db()
        .signals.find({"signal_type": signal_type})
        .sort("logged_at", DESCENDING)
        .limit(limit)
    )
    return [{**d, "_id": str(d["_id"])} for d in docs]


# --- Alerts (pipeline output feed) ---

def store_alert(alert: dict) -> str:
    alert["created_at"] = datetime.now(timezone.utc)
    result = get_db().alerts.insert_one(alert)
    return str(result.inserted_id)


RELEVANT_SIGNAL_TYPES = {
    "weather",
    "weather_disruption",
    "geopolitical",
    "geopolitical_trade",
    "port_disruption",
    "natural_disaster",
    "supply_chain",
    "supply_chain_disruption",
    "other",
}


def list_alerts(limit: int = 50, since: datetime | None = None) -> list[dict]:
    query: dict = {"signal_type": {"$in": list(RELEVANT_SIGNAL_TYPES)}}
    if since:
        query["created_at"] = {"$gt": since}
    docs = get_db().alerts.find(query).sort("created_at", DESCENDING).limit(limit)
    return [{**d, "_id": str(d["_id"])} for d in docs]


def clear_alerts() -> int:
    result = get_db().alerts.delete_many({})
    return result.deleted_count


def clear_irrelevant_alerts() -> int:
    """Delete alerts whose signal_type is not in the relevant whitelist."""
    result = get_db().alerts.delete_many(
        {"$or": [
            {"signal_type": {"$nin": list(RELEVANT_SIGNAL_TYPES)}},
            {"signal_type": None},
        ]}
    )
    return result.deleted_count


# kept for backward compat — routes to store_alert
def log_alert(alert: dict) -> str:
    return store_alert(alert)


# --- Chat sessions ---

def create_session(user_id: str) -> str:
    session_id = str(uuid.uuid4())
    get_db().sessions.insert_one({
        "session_id": session_id,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc),
    })
    return session_id


def list_sessions(user_id: str) -> list[dict]:
    docs = get_db().sessions.find({"user_id": user_id}).sort("created_at", DESCENDING)
    return [{**d, "_id": str(d["_id"])} for d in docs]


# --- Chat messages ---

def append_message(session_id: str, role: str, content: str, metadata: dict | None = None) -> str:
    doc = {
        "session_id": session_id,
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc),
        **(metadata or {}),
    }
    result = get_db().messages.insert_one(doc)
    return str(result.inserted_id)


def delete_session_messages(session_id: str) -> int:
    """Wipe visible chat history for a session. mem0 semantic memory is untouched."""
    result = get_db().messages.delete_many({"session_id": session_id})
    return result.deleted_count


def get_session_messages(session_id: str, limit: int = 50) -> list[dict]:
    docs = (
        get_db()
        .messages.find({"session_id": session_id})
        .sort("timestamp", DESCENDING)
        .limit(limit)
    )
    # return chronological order
    msgs = [{**d, "_id": str(d["_id"])} for d in docs]
    return list(reversed(msgs))


# --- News articles (raw daily feed) ---

def store_news_articles(articles: list[dict]) -> None:
    if not articles:
        return
    db = get_db()
    db.news_articles.create_index("fetched_at", expireAfterSeconds=604800, background=True)
    db.news_articles.create_index("url", unique=True, sparse=True, background=True)
    now = datetime.now(timezone.utc)
    for a in articles:
        url = a.get("url", "")
        updatable = {
            "category": a.get("category", "other"),
            "fetched_at": now,
        }
        # $setOnInsert must not overlap with $set — exclude category/fetched_at
        immutable = {k: v for k, v in a.items() if k not in ("category", "fetched_at")}
        if url:
            db.news_articles.update_one(
                {"url": url},
                {"$set": updatable, "$setOnInsert": immutable},
                upsert=True,
            )
        else:
            db.news_articles.insert_one({**a, "fetched_at": now})


def get_existing_article_urls(urls: list[str]) -> set[str]:
    if not urls:
        return set()
    docs = get_db().news_articles.find({"url": {"$in": urls}}, {"url": 1, "_id": 0})
    return {d["url"] for d in docs}


def clear_news_articles() -> int:
    result = get_db().news_articles.delete_many({})
    return result.deleted_count


def clear_signal_hashes() -> int:
    result = get_db().signal_hashes.delete_many({})
    return result.deleted_count


def list_news_articles(
    category: str | None = None,
    limit: int = 50,
) -> list[dict]:
    query: dict = {}
    if category:
        query["category"] = category
    docs = (
        get_db()
        .news_articles.find(query)
        .sort("published_at", DESCENDING)
        .limit(limit)
    )
    return [{**d, "_id": str(d["_id"])} for d in docs]


# --- Health ---

def health_check() -> bool:
    try:
        get_db().command("ping")
        return True
    except Exception as e:
        print(f"MongoDB health check failed: {e}")
        return False


if __name__ == "__main__":
    print("MongoDB:", "OK" if health_check() else "FAILED")
