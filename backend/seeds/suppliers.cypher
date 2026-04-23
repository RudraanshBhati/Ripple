// ============================================================
// RIPPLE — Neo4j Seed Data
// Run this in Neo4j Browser at http://localhost:7474
// Login: neo4j / ripple2026
// ============================================================

// Clear existing data (safe for demo reset)
MATCH (n) DETACH DELETE n;

// ============================================================
// COUNTRIES
// ============================================================
CREATE (tw:Country {id: "TW", name: "Taiwan", risk_index: 0.65, geopolitical_tension: "high"});
CREATE (nl:Country {id: "NL", name: "Netherlands", risk_index: 0.12, geopolitical_tension: "low"});
CREATE (cn:Country {id: "CN", name: "China", risk_index: 0.45, geopolitical_tension: "medium"});
CREATE (vn:Country {id: "VN", name: "Vietnam", risk_index: 0.25, geopolitical_tension: "low"});
CREATE (in_:Country {id: "IN", name: "India", risk_index: 0.28, geopolitical_tension: "low"});

// ============================================================
// PORTS
// ============================================================
CREATE (keelung:Port {id: "PORT-KEELUNG", name: "Keelung Port", country: "TW", throughput_teu_monthly: 120000});
CREATE (rotterdam:Port {id: "PORT-ROTTERDAM", name: "Rotterdam Port", country: "NL", throughput_teu_monthly: 1100000});
CREATE (shanghai:Port {id: "PORT-SHANGHAI", name: "Shanghai Port", country: "CN", throughput_teu_monthly: 4000000});

// ============================================================
// SUPPLIERS — TIER 1
// ============================================================

// Scenario 1: TaiwanChipCo — directly affected by Keelung strike
CREATE (taiwanchip:Supplier {
    id: "SUP-001",
    name: "TaiwanChipCo",
    country: "TW",
    country_name: "Taiwan",
    city: "Hsinchu",
    tier: 1,
    capabilities: ["MCU", "FPGA", "SoC"],
    capacity_monthly: 50000,
    reliability_score: 0.92
});

// Scenario 2: DutchParts BV — SAFE-looking tier-1, hidden tier-2 risk via SinoRaw
CREATE (dutchparts:Supplier {
    id: "SUP-002",
    name: "DutchParts BV",
    country: "NL",
    country_name: "Netherlands",
    city: "Eindhoven",
    tier: 1,
    capabilities: ["PCB", "passive_components", "connectors"],
    capacity_monthly: 30000,
    reliability_score: 0.88
});

// ============================================================
// SUPPLIERS — TIER 2 (the invisible risk layer)
// ============================================================

// SinoRaw Ltd — in Zhengzhou, sources raw materials for DutchParts
CREATE (sinoraw:Supplier {
    id: "SUP-003",
    name: "SinoRaw Ltd",
    country: "CN",
    country_name: "China",
    city: "Zhengzhou",
    tier: 2,
    capabilities: ["rare_earth", "copper_substrate", "chemical_compounds"],
    capacity_monthly: 80000,
    reliability_score: 0.75
});

// ============================================================
// SUPPLIERS — ALTERNATIVES (for alt sourcing agent)
// ============================================================

CREATE (vnfab:Supplier {
    id: "SUP-ALT-01",
    name: "VN-FAB-03",
    country: "VN",
    country_name: "Vietnam",
    city: "Ho Chi Minh City",
    tier: 1,
    capabilities: ["MCU", "SoC", "embedded_controllers"],
    capacity_monthly: 35000,
    reliability_score: 0.85
});

CREATE (inchip:Supplier {
    id: "SUP-ALT-02",
    name: "IN-CHIP-01",
    country: "IN",
    country_name: "India",
    city: "Bengaluru",
    tier: 1,
    capabilities: ["MCU", "FPGA", "power_management"],
    capacity_monthly: 28000,
    reliability_score: 0.81
});

// ============================================================
// PRODUCTS / SKUs
// ============================================================

CREATE (mcu01:Product {
    id: "SKU-MCU-01",
    name: "Microcontroller Unit v2",
    category: "semiconductor",
    critical: true
});

CREATE (mcu03:Product {
    id: "SKU-MCU-03",
    name: "PCB Assembly Module v3",
    category: "passive_component",
    critical: true
});

// ============================================================
// RELATIONSHIPS
// ============================================================

// --- SUPPLIES (supplier → product) ---
MATCH (s:Supplier {id: "SUP-001"}), (p:Product {id: "SKU-MCU-01"})
CREATE (s)-[:SUPPLIES]->(p);

MATCH (s:Supplier {id: "SUP-002"}), (p:Product {id: "SKU-MCU-03"})
CREATE (s)-[:SUPPLIES]->(p);

MATCH (s:Supplier {id: "SUP-ALT-01"}), (p:Product {id: "SKU-MCU-01"})
CREATE (s)-[:SUPPLIES]->(p);

MATCH (s:Supplier {id: "SUP-ALT-02"}), (p:Product {id: "SKU-MCU-01"})
CREATE (s)-[:SUPPLIES]->(p);

// --- SOURCES_FROM (THE tier-2 invisible risk edge) ---
// DutchParts sources raw materials from SinoRaw in Zhengzhou
MATCH (downstream:Supplier {id: "SUP-002"}), (upstream:Supplier {id: "SUP-003"})
CREATE (downstream)-[:SOURCES_FROM]->(upstream);

// --- SHIPS_THROUGH (supplier → port) ---
MATCH (s:Supplier {id: "SUP-001"}), (p:Port {id: "PORT-KEELUNG"})
CREATE (s)-[:SHIPS_THROUGH]->(p);

MATCH (s:Supplier {id: "SUP-002"}), (p:Port {id: "PORT-ROTTERDAM"})
CREATE (s)-[:SHIPS_THROUGH]->(p);

MATCH (s:Supplier {id: "SUP-003"}), (p:Port {id: "PORT-SHANGHAI"})
CREATE (s)-[:SHIPS_THROUGH]->(p);

// --- LOCATED_IN (port → country) ---
MATCH (p:Port {id: "PORT-KEELUNG"}), (c:Country {id: "TW"})
CREATE (p)-[:LOCATED_IN]->(c);

MATCH (p:Port {id: "PORT-ROTTERDAM"}), (c:Country {id: "NL"})
CREATE (p)-[:LOCATED_IN]->(c);

MATCH (p:Port {id: "PORT-SHANGHAI"}), (c:Country {id: "CN"})
CREATE (p)-[:LOCATED_IN]->(c);

// ============================================================
// RISK EVENTS (pre-seeded for demo context)
// ============================================================

CREATE (evt1:RiskEvent {
    id: "EVT-DEMO-001",
    type: "port_strike",
    severity: 0.85,
    source: "GDELT",
    description: "Taiwan port workers strike, Keelung operations disrupted",
    location: "Keelung",
    country: "TW"
});

CREATE (evt2:RiskEvent {
    id: "EVT-DEMO-002",
    type: "flooding",
    severity: 0.74,
    source: "Open-Meteo",
    description: "Severe flooding in Zhengzhou, Henan province",
    location: "Zhengzhou",
    country: "CN"
});

CREATE (evt3:RiskEvent {
    id: "EVT-DEMO-003",
    type: "weather_fog",
    severity: 0.18,
    source: "Open-Meteo",
    description: "Dense fog at Rotterdam port, reduced visibility",
    location: "Rotterdam",
    country: "NL"
});

MATCH (r:RiskEvent {id: "EVT-DEMO-001"}), (p:Port {id: "PORT-KEELUNG"})
CREATE (r)-[:AFFECTS]->(p);

MATCH (r:RiskEvent {id: "EVT-DEMO-002"}), (s:Supplier {id: "SUP-003"})
CREATE (r)-[:AFFECTS]->(s);

MATCH (r:RiskEvent {id: "EVT-DEMO-003"}), (p:Port {id: "PORT-ROTTERDAM"})
CREATE (r)-[:AFFECTS]->(p);

// ============================================================
// TO ADD MORE DATA LATER — just append below and re-run
// Examples:
//   CREATE (:Supplier {id: "SUP-005", name: "JP-Steel-01", city: "Osaka", ...})
//   MATCH (s:Supplier {id:"SUP-005"}), (p:Product {id:"SKU-MCU-01"}) CREATE (s)-[:SUPPLIES]->(p)
// ============================================================
