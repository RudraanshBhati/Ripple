"""
Run all seed scripts in the correct order.
Usage: uv run python -m backend.seeds.run_all

Order:
  1. Postgres (tables + inventory)
  2. Neo4j (supplier graph)
  3. Supplier embeddings (requires Ollama)
  4. mem0 memories (requires Ollama + Neo4j + Postgres)
"""
from backend.seeds.seed_postgres import run_seed as seed_postgres
from backend.seeds.seed_neo4j import run_seed as seed_neo4j
from backend.seeds.embed_suppliers import run_seed as embed_suppliers
from backend.seeds.seed_memories import run_seed as seed_memories


def main():
    steps = [
        ("Postgres (tables + inventory)", seed_postgres),
        ("Neo4j (supplier graph)",        seed_neo4j),
        ("Supplier embeddings (Ollama)",  embed_suppliers),
        ("mem0 memories",                 seed_memories),
    ]

    for name, fn in steps:
        print(f"\n{'='*55}")
        print(f"  {name}")
        print(f"{'='*55}")
        ok = fn()
        if not ok:
            print(f"\nABORTED at: {name}")
            return

    print("\n" + "="*55)
    print("  All seeds complete. Ripple is ready.")
    print("="*55)


if __name__ == "__main__":
    main()
