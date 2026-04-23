import os
from mem0 import Memory
from dotenv import load_dotenv

load_dotenv()

_memory = None


def get_memory() -> Memory:
    global _memory
    if _memory is None:
        config = {
            "llm": {
                "provider": "anthropic",
                "config": {
                    "model": "claude-haiku-4-5-20251001",
                    "api_key": os.getenv("ANTHROPIC_API_KEY"),
                },
            },
            "embedder": {
                "provider": "ollama",
                "config": {
                    "model": os.getenv("EMBEDDING_MODEL", "nomic-embed-text"),
                    "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                },
            },
            "vector_store": {
                "provider": "pgvector",
                "config": {
                    "user": os.getenv("POSTGRES_USER", "ripple"),
                    "password": os.getenv("POSTGRES_PASSWORD", "ripple2026"),
                    "host": os.getenv("POSTGRES_HOST", "localhost"),
                    "port": int(os.getenv("POSTGRES_PORT", 5432)),
                    "dbname": os.getenv("POSTGRES_DB", "ripple"),
                    "embedding_model_dims": 768,
                },
            },
            "graph_store": {
                "provider": "neo4j",
                "config": {
                    "url": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                    "username": os.getenv("NEO4J_USER", "neo4j"),
                    "password": os.getenv("NEO4J_PASSWORD", "ripple2026"),
                },
            },
        }
        _memory = Memory.from_config(config)
    return _memory


def add_memory(text: str, user_id: str = "ripple-system", metadata: dict | None = None) -> str:
    """
    Add a pre-structured memory entry. Writes are always structured from agent code —
    never rely on LLM extraction.
    """
    result = get_memory().add(text, user_id=user_id, metadata=metadata or {})
    # mem0 returns either {"id": "..."} or {"results": [...]} depending on version
    if isinstance(result, dict):
        return result.get("id") or (result.get("results") or [{}])[0].get("id", "")
    return ""


def search_memories(query: str, user_id: str = "ripple-system", limit: int = 5) -> list[dict]:
    """Search memories by semantic similarity."""
    try:
        results = get_memory().search(query, filters={"user_id": user_id}, limit=limit)
        return results.get("results", [])
    except Exception as e:
        print(f"mem0 search failed (non-fatal): {e}")
        return []


def get_all_memories(user_id: str = "ripple-system") -> list[dict]:
    try:
        results = get_memory().get_all(filters={"user_id": user_id})
        return results.get("results", [])
    except Exception as e:
        print(f"mem0 get_all failed (non-fatal): {e}")
        return []


def health_check() -> bool:
    try:
        get_memory()
        return True
    except Exception as e:
        print(f"mem0 health check failed: {e}")
        return False


if __name__ == "__main__":
    print("mem0:", "OK" if health_check() else "FAILED")
