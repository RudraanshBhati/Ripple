"""
Seed mem0 with pre-structured historical disruption memories.
Usage: uv run python -m backend.seeds.seed_memories

Writes are structured from code — NOT LLM-extracted.
"""
import json
from pathlib import Path
from backend.storage.mem0_client import get_memory, health_check

MEMORIES_FILE = Path(__file__).parent / "memories.json"
USER_ID = "ripple-system"


def run_seed():
    if not health_check():
        print("ERROR: Cannot initialise mem0. Check Ollama + Postgres + Neo4j.")
        return False

    memories = json.loads(MEMORIES_FILE.read_text(encoding="utf-8"))
    memory = get_memory()

    # Clear existing system memories first (clean slate for demo)
    try:
        existing = memory.get_all(filters={"user_id": USER_ID})
        for m in existing.get("results", []):
            memory.delete(m["id"])
        print(f"Cleared {len(existing.get('results', []))} existing memories.")
    except Exception as e:
        print(f"Could not clear existing memories (non-fatal): {e}")

    for i, entry in enumerate(memories, 1):
        try:
            result = memory.add(
                entry["text"],
                user_id=USER_ID,
                metadata=entry["metadata"],
            )
            print(f"  [{i}/{len(memories)}] Seeded: {entry['metadata']['type']} — {entry['metadata'].get('entity', '')}")
        except Exception as e:
            print(f"  [{i}/{len(memories)}] ERROR: {e}")

    # Verify search works
    print("\nVerifying search...")
    results = memory.search("Rotterdam fog false positive", filters={"user_id": USER_ID}, limit=1)
    hits = results.get("results", [])
    if hits:
        print(f"  Search OK — top result: {hits[0]['memory'][:80]}...")
    else:
        print("  WARNING: Search returned no results — check mem0 config")

    print("\nmem0 seed complete.")
    return True


if __name__ == "__main__":
    run_seed()
