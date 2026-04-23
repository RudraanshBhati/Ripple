"""
Run the suppliers.cypher seed against the local Neo4j instance.
Usage: uv run python -m backend.seeds.seed_neo4j
"""
import os
from pathlib import Path
from backend.storage.neo4j_client import get_driver, health_check

CYPHER_FILE = Path(__file__).parent / "suppliers.cypher"


def run_seed():
    if not health_check():
        print("ERROR: Cannot connect to Neo4j. Is Docker running?")
        return False

    raw = CYPHER_FILE.read_text(encoding="utf-8")

    # Strip comment lines and split on semicolons
    statements = []
    for stmt in raw.split(";"):
        lines = [
            line for line in stmt.splitlines()
            if line.strip() and not line.strip().startswith("//")
        ]
        cleaned = " ".join(lines).strip()
        if cleaned:
            statements.append(cleaned)

    driver = get_driver()
    with driver.session() as session:
        for i, stmt in enumerate(statements, 1):
            try:
                session.run(stmt)
                print(f"  [{i}/{len(statements)}] OK")
            except Exception as e:
                print(f"  [{i}/{len(statements)}] ERROR: {e}\n    → {stmt[:80]}")
                return False

    print("\nNeo4j seed complete.")

    # Verify tier-2 chain
    with driver.session() as session:
        result = session.run("""
            MATCH path = (affected:Supplier {name: "SinoRaw Ltd"})
                         <-[:SOURCES_FROM*1..3]-
                         (downstream:Supplier)
            RETURN downstream.name AS name, length(path) AS depth
        """)
        rows = result.data()
        if rows:
            print("\nTier-2 chain verified:")
            for r in rows:
                print(f"  {r['name']} (depth {r['depth']})")
        else:
            print("\nWARNING: Tier-2 chain not found — check SOURCES_FROM relationship")

    return True


if __name__ == "__main__":
    run_seed()
