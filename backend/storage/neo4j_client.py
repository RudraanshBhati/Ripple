import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

_driver = None


def get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            auth=(
                os.getenv("NEO4J_USER", "neo4j"),
                os.getenv("NEO4J_PASSWORD", "ripple2026"),
            ),
        )
    return _driver


def run_cypher(query: str, params: dict | None = None) -> list[dict]:
    with get_driver().session() as session:
        result = session.run(query, params or {})
        return [record.data() for record in result]


def find_direct_suppliers(entity_name: str) -> list[dict]:
    """Find tier-1 suppliers directly associated with a location or entity name."""
    query = """
    MATCH (s:Supplier)
    WHERE toLower(s.city) CONTAINS toLower($name)
       OR toLower(s.country_name) CONTAINS toLower($name)
       OR toLower(s.name) CONTAINS toLower($name)
    RETURN s.id AS supplier_id, s.name AS name, s.country AS country,
           s.tier AS tier, s.city AS city, s.capabilities AS capabilities
    """
    return run_cypher(query, {"name": entity_name})


def traverse_tier2_suppliers(supplier_name: str) -> list[dict]:
    """
    THE wow-moment query: traverse SOURCES_FROM edges up to 3 hops to find
    all downstream suppliers that depend on the given supplier.
    """
    query = """
    MATCH path = (affected:Supplier {name: $name})
                 <-[:SOURCES_FROM*1..3]-
                 (downstream:Supplier)
    RETURN downstream.id AS supplier_id,
           downstream.name AS name,
           downstream.country AS country,
           downstream.tier AS tier,
           downstream.city AS city,
           length(path) AS tier_depth
    ORDER BY tier_depth
    """
    return run_cypher(query, {"name": supplier_name})


def get_suppliers_at_city(city: str) -> list[dict]:
    """Find all suppliers located in a given city."""
    query = """
    MATCH (s:Supplier)
    WHERE toLower(s.city) CONTAINS toLower($city)
    RETURN s.id AS supplier_id, s.name AS name, s.country AS country,
           s.tier AS tier, s.city AS city
    """
    return run_cypher(query, {"city": city})


def get_port_risk(port_name: str) -> list[dict]:
    """Check for active risk events affecting a named port."""
    query = """
    MATCH (r:RiskEvent)-[:AFFECTS]->(p:Port)
    WHERE toLower(p.name) CONTAINS toLower($port_name)
    RETURN r.id AS event_id, r.type AS type, r.severity AS severity,
           r.description AS description, p.name AS port_name
    """
    return run_cypher(query, {"port_name": port_name})


def get_supplier_ports(supplier_name: str) -> list[dict]:
    """Find which ports a supplier ships through."""
    query = """
    MATCH (s:Supplier {name: $name})-[:SHIPS_THROUGH]->(p:Port)
    RETURN p.id AS port_id, p.name AS name, p.country AS country
    """
    return run_cypher(query, {"name": supplier_name})


def find_alternative_suppliers(
    affected_supplier_ids: list[str], sku_id: str | None = None
) -> list[dict]:
    """
    Find suppliers connected to the same products/SKUs as the affected ones,
    excluding the affected suppliers themselves.
    Returns supplier_id, name, country, tier, capabilities, shared_products, reliability_score.
    """
    base_query = """
    MATCH (alt:Supplier)-[:SUPPLIES]->(p:Product)<-[:SUPPLIES]-(affected:Supplier)
    WHERE affected.id IN $affected_ids
      AND NOT alt.id IN $affected_ids
    WITH alt, count(DISTINCT p) AS shared_products
    RETURN alt.id AS supplier_id,
           alt.name AS name,
           alt.country AS country,
           alt.tier AS tier,
           alt.capabilities AS capabilities,
           coalesce(alt.reliability_score, 0.5) AS reliability_score,
           shared_products
    ORDER BY shared_products DESC, reliability_score DESC
    LIMIT 10
    """
    params: dict = {"affected_ids": affected_supplier_ids}

    if sku_id:
        # Narrow to suppliers that supply this specific SKU
        sku_query = """
        MATCH (alt:Supplier)-[:SUPPLIES]->(p:Product {id: $sku_id})
        WHERE NOT alt.id IN $affected_ids
        WITH alt, 1 AS shared_products
        RETURN alt.id AS supplier_id,
               alt.name AS name,
               alt.country AS country,
               alt.tier AS tier,
               alt.capabilities AS capabilities,
               coalesce(alt.reliability_score, 0.5) AS reliability_score,
               shared_products
        ORDER BY reliability_score DESC
        LIMIT 10
        """
        params["sku_id"] = sku_id
        results = run_cypher(sku_query, params)
        if results:
            return results
        # Fall back to shared-product traversal if no direct SKU match
    return run_cypher(base_query, params)


def get_sku_suppliers(sku_id: str) -> list[dict]:
    """Find all suppliers that supply a given SKU."""
    query = """
    MATCH (s:Supplier)-[:SUPPLIES]->(p:Product {id: $sku_id})
    RETURN s.id AS supplier_id, s.name AS name, s.country AS country,
           s.tier AS tier, s.reliability_score AS reliability_score
    ORDER BY s.reliability_score DESC
    """
    return run_cypher(query, {"sku_id": sku_id})


def health_check() -> bool:
    try:
        run_cypher("RETURN 1 AS ok")
        return True
    except Exception as e:
        print(f"Neo4j health check failed: {e}")
        return False


if __name__ == "__main__":
    print("Neo4j:", "OK" if health_check() else "FAILED")
