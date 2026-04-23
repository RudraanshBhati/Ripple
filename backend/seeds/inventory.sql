-- ============================================================
-- RIPPLE — PostgreSQL Seed Data
-- Run via: psql -h localhost -U ripple -d ripple -f inventory.sql
-- Or paste into pgAdmin Query Tool
-- ============================================================

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- TABLES
-- ============================================================

DROP TABLE IF EXISTS supplier_embeddings;
DROP TABLE IF EXISTS supplier_skus;
DROP TABLE IF EXISTS sku_inventory;

CREATE TABLE sku_inventory (
    sku_id                  VARCHAR PRIMARY KEY,
    name                    TEXT NOT NULL,
    current_stock           INT NOT NULL,
    in_transit_stock        INT DEFAULT 0,
    safety_stock            INT NOT NULL,
    reorder_point           INT NOT NULL,
    daily_consumption_rate  FLOAT NOT NULL,
    seasonality_factor      FLOAT DEFAULT 1.0
);

CREATE TABLE supplier_skus (
    supplier_id             VARCHAR NOT NULL,
    sku_id                  VARCHAR NOT NULL,
    standard_lead_time_days INT NOT NULL,
    current_lead_time_days  INT NOT NULL,
    transit_time_days       INT NOT NULL,
    customs_buffer_days     INT DEFAULT 2,
    on_time_delivery_rate   FLOAT DEFAULT 0.90,
    PRIMARY KEY (supplier_id, sku_id)
);

CREATE TABLE supplier_embeddings (
    supplier_id  VARCHAR PRIMARY KEY,
    description  TEXT NOT NULL,
    embedding    VECTOR(768)
);

CREATE INDEX ON supplier_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);

-- ============================================================
-- SKU INVENTORY
-- Tuned so demo scenarios produce correct gap_days:
--   SKU-MCU-01: available=900, rate=100 → 9 days; lead=21d → gap=-12 (CRITICAL)
--   SKU-MCU-03: available=420, rate=30  → 14 days; lead=28d → gap=-14 (CRITICAL)
-- ============================================================

INSERT INTO sku_inventory VALUES
    ('SKU-MCU-01', 'Microcontroller Unit v2',  1000, 100, 100, 300, 100.0, 1.0),
    ('SKU-MCU-03', 'PCB Assembly Module v3',    500,  20,  80, 150,  30.0, 1.0);

-- ============================================================
-- SUPPLIER → SKU LEAD TIMES
-- ============================================================

INSERT INTO supplier_skus VALUES
-- TaiwanChipCo → SKU-MCU-01 (21 day lead = scenario 1 gap -12)
('SUP-001', 'SKU-MCU-01', 21, 21, 14, 2, 0.92),

-- DutchParts BV → SKU-MCU-03 (28 day lead = scenario 2 gap -14)
('SUP-002', 'SKU-MCU-03', 28, 28, 18, 2, 0.88),

-- Alternative suppliers for SKU-MCU-01
('SUP-ALT-01', 'SKU-MCU-01', 14, 14, 10, 2, 0.85),   -- VN-FAB-03: 14d
('SUP-ALT-02', 'SKU-MCU-01', 18, 18, 12, 2, 0.81);   -- IN-CHIP-01: 18d

-- ============================================================
-- SUPPLIER DESCRIPTIONS (for pgvector similarity search)
-- Embeddings populated separately by embed_suppliers.py
-- ============================================================

INSERT INTO supplier_embeddings (supplier_id, description) VALUES
('SUP-001',     'Taiwan semiconductor manufacturer specializing in MCU, FPGA, and SoC production. High reliability, ships through Keelung Port.'),
('SUP-002',     'Dutch electronics components supplier. PCB assemblies, passive components, connectors. Ships through Rotterdam.'),
('SUP-003',     'Chinese raw materials supplier in Zhengzhou. Rare earth elements, copper substrates, chemical compounds.'),
('SUP-ALT-01',  'Vietnam-based MCU and SoC manufacturer in Ho Chi Minh City. Growing capacity, competitive lead times, no geopolitical tension.'),
('SUP-ALT-02',  'Indian semiconductor fab in Bengaluru. MCU, FPGA, power management ICs. Strong government support, stable supply.');

-- ============================================================
-- TO ADD MORE DATA LATER — append INSERT rows above
-- Example:
--   INSERT INTO sku_inventory VALUES ('SKU-GPU-01', 'GPU Module v1', 200, 0, 50, 100, 20.0, 1.0);
--   INSERT INTO supplier_skus VALUES ('SUP-001', 'SKU-GPU-01', 35, 35, 21, 2, 0.90);
-- ============================================================
