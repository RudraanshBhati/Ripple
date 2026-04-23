import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

_conn = None


def get_conn():
    global _conn
    if _conn is None or _conn.closed:
        _conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", 5432)),
            dbname=os.getenv("POSTGRES_DB", "ripple"),
            user=os.getenv("POSTGRES_USER", "ripple"),
            password=os.getenv("POSTGRES_PASSWORD", "ripple2026"),
        )
        _conn.autocommit = True
    return _conn


def run_query(sql: str, params=None) -> list[dict]:
    with get_conn().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params or ())
        return [dict(row) for row in cur.fetchall()]


def run_execute(sql: str, params=None) -> None:
    with get_conn().cursor() as cur:
        cur.execute(sql, params or ())


def get_sku(sku_id: str) -> dict | None:
    rows = run_query(
        "SELECT * FROM sku_inventory WHERE sku_id = %s", (sku_id,)
    )
    return rows[0] if rows else None


def get_supplier_sku(supplier_id: str, sku_id: str) -> dict | None:
    rows = run_query(
        "SELECT * FROM supplier_skus WHERE supplier_id = %s AND sku_id = %s",
        (supplier_id, sku_id),
    )
    return rows[0] if rows else None


def get_skus_for_supplier(supplier_id: str) -> list[dict]:
    return run_query(
        """
        SELECT si.*, ss.standard_lead_time_days, ss.current_lead_time_days,
               ss.transit_time_days, ss.customs_buffer_days, ss.on_time_delivery_rate
        FROM sku_inventory si
        JOIN supplier_skus ss ON si.sku_id = ss.sku_id
        WHERE ss.supplier_id = %s
        """,
        (supplier_id,),
    )


def vector_search_suppliers(embedding: list[float], k: int = 5) -> list[dict]:
    """Cosine similarity search over supplier_embeddings using pgvector."""
    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
    with get_conn().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # Probe all IVFFlat lists — default probes=1 misses buckets on small datasets
        cur.execute("SET ivfflat.probes = 10")
        cur.execute(
            """
            SELECT supplier_id, description,
                   1 - (embedding <=> %s::vector) AS similarity_score
            FROM supplier_embeddings
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (embedding_str, embedding_str, k),
        )
        return [dict(row) for row in cur.fetchall()]


def get_supplier_embedding_description(supplier_id: str) -> str | None:
    rows = run_query(
        "SELECT description FROM supplier_embeddings WHERE supplier_id = %s",
        (supplier_id,),
    )
    return rows[0]["description"] if rows else None


def health_check() -> bool:
    try:
        run_query("SELECT 1 AS ok")
        return True
    except Exception as e:
        print(f"Postgres health check failed: {e}")
        return False


if __name__ == "__main__":
    print("Postgres:", "OK" if health_check() else "FAILED")
