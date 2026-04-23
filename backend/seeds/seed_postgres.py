"""
Run the inventory.sql seed against the local PostgreSQL instance.
Usage: uv run python -m backend.seeds.seed_postgres
"""
from pathlib import Path
from backend.storage.postgres_client import get_conn, health_check

SQL_FILE = Path(__file__).parent / "inventory.sql"


def run_seed():
    if not health_check():
        print("ERROR: Cannot connect to Postgres. Is Docker running?")
        return False

    sql = SQL_FILE.read_text(encoding="utf-8")

    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(sql)

    print("Postgres seed complete.")

    # Verify rows
    with conn.cursor() as cur:
        cur.execute("SELECT sku_id, current_stock, daily_consumption_rate FROM sku_inventory")
        rows = cur.fetchall()
        print("\nSKU inventory:")
        for row in rows:
            print(f"  {row[0]}: stock={row[1]}, rate={row[2]}/day")

        cur.execute("SELECT supplier_id, sku_id, current_lead_time_days FROM supplier_skus")
        rows = cur.fetchall()
        print("\nSupplier lead times:")
        for row in rows:
            print(f"  {row[0]} -> {row[1]}: {row[2]} days")

    return True


if __name__ == "__main__":
    run_seed()
