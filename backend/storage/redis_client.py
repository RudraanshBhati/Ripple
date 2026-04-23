import os
import json
import redis
from dotenv import load_dotenv

load_dotenv()

_client = None
SIGNAL_STREAM = "ripple:signals"


def get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379"),
            decode_responses=True,
        )
    return _client


def publish_signal(signal: dict) -> str:
    """Publish a signal dict to the Redis stream. Returns the stream entry ID."""
    entry_id = get_client().xadd(
        SIGNAL_STREAM,
        {"payload": json.dumps(signal)},
        maxlen=500,  # keep last 500 signals
    )
    return entry_id


def consume_signals(count: int = 10, last_id: str = "0") -> list[dict]:
    """Read up to `count` signals from the stream starting after `last_id`."""
    entries = get_client().xread({SIGNAL_STREAM: last_id}, count=count, block=0)
    results = []
    if entries:
        for _, messages in entries:
            for msg_id, fields in messages:
                signal = json.loads(fields["payload"])
                signal["_stream_id"] = msg_id
                results.append(signal)
    return results


def set_cache(key: str, value: str, ttl_seconds: int = 300) -> None:
    get_client().setex(key, ttl_seconds, value)


def get_cache(key: str) -> str | None:
    return get_client().get(key)


def health_check() -> bool:
    try:
        get_client().ping()
        return True
    except Exception as e:
        print(f"Redis health check failed: {e}")
        return False


if __name__ == "__main__":
    print("Redis:", "OK" if health_check() else "FAILED")
