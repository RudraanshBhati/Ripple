"""
Generate 768-dim embeddings for supplier descriptions via Ollama (nomic-embed-text)
and store them in the pgvector supplier_embeddings table.
Usage: uv run python -m backend.seeds.embed_suppliers

Requires: Ollama running locally with nomic-embed-text pulled.
  ollama pull nomic-embed-text
"""
import os
import httpx
from backend.storage.postgres_client import get_conn, run_query, health_check

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")


def get_embedding(text: str) -> list[float]:
    response = httpx.post(
        f"{OLLAMA_BASE_URL}/api/embeddings",
        json={"model": EMBEDDING_MODEL, "prompt": text},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()["embedding"]


def run_seed():
    if not health_check():
        print("ERROR: Cannot connect to Postgres. Is Docker running?")
        return False

    # Fetch suppliers that have descriptions but no embedding yet
    rows = run_query(
        "SELECT supplier_id, description FROM supplier_embeddings WHERE embedding IS NULL"
    )

    if not rows:
        print("All suppliers already have embeddings. Run inventory.sql first.")
        return True

    print(f"Generating embeddings for {len(rows)} suppliers via {EMBEDDING_MODEL}...\n")

    conn = get_conn()
    for i, row in enumerate(rows, 1):
        supplier_id = row["supplier_id"]
        description = row["description"]
        try:
            embedding = get_embedding(description)
            embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE supplier_embeddings SET embedding = %s::vector WHERE supplier_id = %s",
                    (embedding_str, supplier_id),
                )
            print(f"  [{i}/{len(rows)}] {supplier_id} — {len(embedding)}-dim OK")
        except Exception as e:
            print(f"  [{i}/{len(rows)}] {supplier_id} — ERROR: {e}")
            return False

    print("\nEmbeddings complete. Verifying similarity search...")

    # Quick sanity check: MCU query should surface VN-FAB-03 and IN-CHIP-01
    test_embedding = get_embedding("MCU semiconductor manufacturer Asia alternative supplier")
    test_str = "[" + ",".join(str(x) for x in test_embedding) + "]"

    results = run_query(
        f"""
        SELECT supplier_id,
               1 - (embedding <=> %s::vector) AS similarity
        FROM supplier_embeddings
        ORDER BY embedding <=> %s::vector
        LIMIT 3
        """,
        (test_str, test_str),
    )
    print("\nTop-3 similarity results for 'MCU Asia alternative':")
    for r in results:
        print(f"  {r['supplier_id']}: {r['similarity']:.4f}")

    return True


if __name__ == "__main__":
    run_seed()
