"""
Demo data seeder for Ripple — populates MongoDB with 4 pre-built supply-chain
alert scenarios designed for judge presentations.

Run:  uv run python scripts/seed_demo.py
      uv run python scripts/seed_demo.py --clear   # wipe existing demo alerts first
"""
import argparse
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.storage.mongo_client import get_db

NOW = datetime.now(timezone.utc)


def dt(days_from_now: float) -> str:
    return (NOW + timedelta(days=days_from_now)).isoformat()


# ---------------------------------------------------------------------------
# Scenario 1 — US-China Tariff War + India Component Shortage
# Severity: CRITICAL (0.92)
# India angle: Tata Electronics / Foxconn India (Chennai) can't get Chinese
#              PCB components; Indian suppliers emerge as best alternative
# Recent event: Trump 145% tariffs on Chinese electronics (2025-2026)
# ---------------------------------------------------------------------------
SCENARIO_1 = {
    "session_id": "demo-" + str(uuid.uuid4()),
    "user_id": "demo",
    "signal": (
        "US imposes 145% tariffs on Chinese electronics effective immediately; "
        "China retaliates by halting rare-earth (gallium, germanium, antimony) "
        "exports. Shenzhen and Dongguan manufacturing zones suspending export lines. "
        "Tata Electronics Hosur plant and Foxconn Chennai report PCB component "
        "shortfalls — Indian assembly lines expected to slow within 72 hours."
    ),
    "signal_type": "geopolitical_trade",
    "severity_score": 0.92,
    "alert_type": "critical",
    "final_alert": (
        "CRITICAL ALERT — US-China Trade War Escalation\n\n"
        "The United States has imposed 145% tariffs on Chinese electronics, with China "
        "retaliating via rare-earth export controls on gallium, germanium, and antimony — "
        "critical inputs for semiconductor manufacturing. TaiwanChipCo (SUP-001) and "
        "SinoBoard Ltd (SUP-003, Dongguan) are directly exposed through Shenzhen export "
        "channels, both having declared partial force majeure.\n\n"
        "SKU-MCU-01 (microcontrollers) faces a critical 11-day supply gap: current stock "
        "covers 10 days at standard consumption while adjusted lead times now stand at 21 days. "
        "Invisible risk detected — DutchParts BV (SUP-002) sources 60% of raw PCB material "
        "from SinoRaw Ltd, Zhengzhou; this tier-2 dependency is now compromised.\n\n"
        "Recommended immediate action: activate alternate sourcing via Dixon Technologies "
        "(India) or Kaynes Technology (India) — both carry CE certification and 16-day lead "
        "times to JNPT. India-sourced alternatives qualify for US tariff exemptions under "
        "the Indo-US bilateral trade framework ratified in late 2025."
    ),
    "affected_entities": [
        "Shenzhen", "Dongguan", "JNPT Nhava Sheva", "Chennai", "Hosur Industrial Corridor"
    ],
    "affected_suppliers": [
        {"supplier_id": "SUP-001", "name": "TaiwanChipCo",   "country": "Taiwan",  "tier": 1, "exposure_type": "direct"},
        {"supplier_id": "SUP-003", "name": "SinoBoard Ltd",  "country": "China",   "tier": 1, "exposure_type": "direct"},
        {"supplier_id": "SUP-002", "name": "DutchParts BV",  "country": "Netherlands", "tier": 2, "exposure_type": "tier2"},
    ],
    "sku_risks": [
        {
            "sku_id": "SKU-MCU-01",
            "current_stock": 1000,
            "daily_consumption": 100.0,
            "runout_date": dt(10),
            "lead_time_days": 21,
            "gap_days": -11.0,
            "risk_score": 0.976,
            "confidence": 0.92,
        },
        {
            "sku_id": "SKU-PCB-02",
            "current_stock": 3200,
            "daily_consumption": 180.0,
            "runout_date": dt(18),
            "lead_time_days": 28,
            "gap_days": -10.0,
            "risk_score": 0.843,
            "confidence": 0.88,
        },
    ],
    "alternatives": [
        {
            "supplier_id": "SUP-ALT-IN-01",
            "name": "Dixon Technologies",
            "country": "India",
            "similarity_score": 0.88,
            "estimated_lead_time": 16,
            "confidence": 0.87,
        },
        {
            "supplier_id": "SUP-ALT-IN-02",
            "name": "Kaynes Technology",
            "country": "India",
            "similarity_score": 0.83,
            "estimated_lead_time": 18,
            "confidence": 0.82,
        },
        {
            "supplier_id": "SUP-ALT-VN-01",
            "name": "Vietronics Ltd",
            "country": "Vietnam",
            "similarity_score": 0.79,
            "estimated_lead_time": 14,
            "confidence": 0.78,
        },
    ],
    "tier2_exposure": True,
    "invisible_risk": True,
    "created_at": NOW - timedelta(hours=2),
}

# ---------------------------------------------------------------------------
# Scenario 2 — Cyclone Remal: Bay of Bengal → Chennai Port Closure
# Severity: HIGH (0.81)
# India angle: DIRECT — Chennai is India's largest east-coast container port;
#              auto & electronics suppliers in Tamil Nadu disrupted
# Recent event: Bay of Bengal cyclone season; Cyclone Remal hit May 2024
# ---------------------------------------------------------------------------
SCENARIO_2 = {
    "session_id": "demo-" + str(uuid.uuid4()),
    "user_id": "demo",
    "signal": (
        "Cyclone Remal intensifies to Category 4 over Bay of Bengal. "
        "Chennai Port Authority has suspended all container operations — expected "
        "72-hour closure minimum. Cochin Port placed on Cyclone Alert Level 2. "
        "Tamil Nadu government issues red alert for coastal districts. "
        "Tata Motors, Hyundai India, and Foxconn Chennai plants halting inbound logistics."
    ),
    "signal_type": "weather_disruption",
    "severity_score": 0.81,
    "alert_type": "high",
    "final_alert": (
        "HIGH ALERT — Cyclone Remal: Chennai Port Closure\n\n"
        "Category 4 Cyclone Remal is forcing a complete suspension of Chennai Port "
        "operations (estimated 72+ hours). Chennai handles 1.7M TEUs annually and is the "
        "primary gateway for Tamil Nadu's electronics and automotive exports — home to "
        "Foxconn's iPhone assembly, Hyundai's largest plant outside Korea, and Tata's "
        "EV supply chain.\n\n"
        "Three tier-1 suppliers are directly affected: Chennai Auto Parts Co. (SUP-006), "
        "Tata Electronic Components (SUP-007), and Sundaram Fasteners (SUP-008). "
        "SKU-PCB-02 and SKU-AUTO-05 (wiring harnesses) face runout within 18 and 14 days "
        "respectively, against post-disruption lead times of 28+ days.\n\n"
        "Tier-2 alert: Cochin Port on standby disrupts specialty chemicals supply to "
        "pharma manufacturers upstream. Recommend rerouting non-perishable SKU inventory "
        "via Mundra (Gujarat) as bridge port and pre-positioning safety stock at Singapore "
        "transshipment hub for inbound European components."
    ),
    "affected_entities": [
        "Chennai Port", "Bay of Bengal", "Cochin Port", "Tamil Nadu", "Mundra Port"
    ],
    "affected_suppliers": [
        {"supplier_id": "SUP-006", "name": "Chennai Auto Parts Co.",      "country": "India", "tier": 1, "exposure_type": "direct"},
        {"supplier_id": "SUP-007", "name": "Tata Electronic Components",  "country": "India", "tier": 1, "exposure_type": "direct"},
        {"supplier_id": "SUP-008", "name": "Sundaram Fasteners",          "country": "India", "tier": 1, "exposure_type": "direct"},
        {"supplier_id": "SUP-009", "name": "Cochin Chemical Works",       "country": "India", "tier": 2, "exposure_type": "tier2"},
    ],
    "sku_risks": [
        {
            "sku_id": "SKU-AUTO-05",
            "current_stock": 4200,
            "daily_consumption": 300.0,
            "runout_date": dt(14),
            "lead_time_days": 28,
            "gap_days": -14.0,
            "risk_score": 0.875,
            "confidence": 0.90,
        },
        {
            "sku_id": "SKU-PCB-02",
            "current_stock": 3240,
            "daily_consumption": 180.0,
            "runout_date": dt(18),
            "lead_time_days": 28,
            "gap_days": -10.0,
            "risk_score": 0.843,
            "confidence": 0.86,
        },
        {
            "sku_id": "SKU-CHEM-03",
            "current_stock": 1800,
            "daily_consumption": 90.0,
            "runout_date": dt(20),
            "lead_time_days": 30,
            "gap_days": -10.0,
            "risk_score": 0.817,
            "confidence": 0.83,
        },
    ],
    "alternatives": [
        {
            "supplier_id": "SUP-ALT-IN-03",
            "name": "Sona BLW Precision (Gujarat)",
            "country": "India",
            "similarity_score": 0.85,
            "estimated_lead_time": 10,
            "confidence": 0.88,
        },
        {
            "supplier_id": "SUP-ALT-IN-04",
            "name": "Motherson Sumi Wiring (Pune)",
            "country": "India",
            "similarity_score": 0.82,
            "estimated_lead_time": 12,
            "confidence": 0.84,
        },
        {
            "supplier_id": "SUP-ALT-MY-01",
            "name": "Perodua Auto Parts",
            "country": "Malaysia",
            "similarity_score": 0.74,
            "estimated_lead_time": 14,
            "confidence": 0.76,
        },
    ],
    "tier2_exposure": True,
    "invisible_risk": False,
    "created_at": NOW - timedelta(hours=5),
}

# ---------------------------------------------------------------------------
# Scenario 3 — Red Sea / Suez Closure: Houthi Escalation
# Severity: HIGH (0.78)
# India angle: JNPT and Mundra face 18-22 day delay on European-origin
#              pharma APIs, auto electronics, specialty chemicals
# Recent event: Ongoing since Nov 2023; major escalation in 2025
# ---------------------------------------------------------------------------
SCENARIO_3 = {
    "session_id": "demo-" + str(uuid.uuid4()),
    "user_id": "demo",
    "signal": (
        "Houthi forces launch coordinated drone and missile strikes on three container "
        "vessels in the Red Sea corridor overnight. MSC, Maersk, and CMA CGM suspend ALL "
        "Suez Canal transits indefinitely. Cape of Good Hope rerouting adds 18-22 days to "
        "Europe-Asia and Europe-India shipping lanes. Lloyd's of London raises war-risk "
        "premiums to 1.2%. JNPT Nhava Sheva and Mundra Port report incoming vessel delays "
        "cascading from Jebel Ali congestion."
    ),
    "signal_type": "port_disruption",
    "severity_score": 0.78,
    "alert_type": "high",
    "final_alert": (
        "HIGH ALERT — Red Sea Corridor: Suez Transit Suspended\n\n"
        "Following coordinated Houthi strikes on three container vessels, all three major "
        "carriers (MSC, Maersk, CMA CGM) have suspended Suez Canal transits indefinitely. "
        "Cape of Good Hope rerouting adds 18–22 days and ~$1.2M per vessel in additional "
        "fuel costs. Jebel Ali is expected to saturate within 10 days as vessels queue.\n\n"
        "Critical India impact: JNPT (Nhava Sheva) and Mundra face upstream delays on "
        "European-origin components — pharmaceutical APIs from Rotterdam/Hamburg, "
        "automotive electronics from Antwerp, specialty chemicals from Frankfurt. "
        "DutchParts BV (SUP-002, Rotterdam) standard 21-day lead time now extends to "
        "42–45 days. SKU-CHEM-03 crosses runout threshold in 24 days vs. new 43-day lead.\n\n"
        "Invisible risk: Rotterdam → Jebel Ali → JNPT transshipment chain breaks at "
        "Jebel Ali. Recommend domestic API bridge via Divi's Laboratories (Hyderabad) "
        "or Sun Pharma Vizag facility. Auto-electronics gap: contact Bosch India (Nashik) "
        "as interim tier-1 substitute."
    ),
    "affected_entities": [
        "Red Sea", "Suez Canal", "Jebel Ali", "JNPT Nhava Sheva", "Mundra Port", "Rotterdam"
    ],
    "affected_suppliers": [
        {"supplier_id": "SUP-002", "name": "DutchParts BV",       "country": "Netherlands", "tier": 1, "exposure_type": "direct"},
        {"supplier_id": "SUP-010", "name": "Hamburg Chemicals GmbH", "country": "Germany", "tier": 1, "exposure_type": "direct"},
        {"supplier_id": "SUP-011", "name": "Antwerp Auto Electronics", "country": "Belgium", "tier": 1, "exposure_type": "direct"},
    ],
    "sku_risks": [
        {
            "sku_id": "SKU-CHEM-03",
            "current_stock": 2160,
            "daily_consumption": 90.0,
            "runout_date": dt(24),
            "lead_time_days": 43,
            "gap_days": -19.0,
            "risk_score": 0.791,
            "confidence": 0.85,
        },
        {
            "sku_id": "SKU-MCU-03",
            "current_stock": 840,
            "daily_consumption": 60.0,
            "runout_date": dt(14),
            "lead_time_days": 43,
            "gap_days": -29.0,
            "risk_score": 0.867,
            "confidence": 0.82,
        },
    ],
    "alternatives": [
        {
            "supplier_id": "SUP-ALT-IN-05",
            "name": "Divi's Laboratories (Hyderabad)",
            "country": "India",
            "similarity_score": 0.87,
            "estimated_lead_time": 7,
            "confidence": 0.91,
        },
        {
            "supplier_id": "SUP-ALT-IN-06",
            "name": "Bosch India – Nashik Plant",
            "country": "India",
            "similarity_score": 0.80,
            "estimated_lead_time": 9,
            "confidence": 0.85,
        },
        {
            "supplier_id": "SUP-ALT-PL-01",
            "name": "Warsaw Precision Parts",
            "country": "Poland",
            "similarity_score": 0.72,
            "estimated_lead_time": 21,
            "confidence": 0.74,
        },
    ],
    "tier2_exposure": True,
    "invisible_risk": True,
    "created_at": NOW - timedelta(hours=9),
}

# ---------------------------------------------------------------------------
# Scenario 4 — Taiwan Earthquake: Semiconductor Supply Collapse
# Severity: CRITICAL (0.95) — most severe
# India angle: India Semiconductor Mission fabs proposed as long-term
#              alternative; Renesas Japan as immediate bridge
# Recent event: Based on Hualien earthquake 3 April 2024 (magnitude 7.4)
# ---------------------------------------------------------------------------
SCENARIO_4 = {
    "session_id": "demo-" + str(uuid.uuid4()),
    "user_id": "demo",
    "signal": (
        "7.6 magnitude earthquake strikes Hualien, Taiwan at 07:58 local time. "
        "TSMC has suspended operations at Fab 18 (3nm / 5nm advanced nodes) and "
        "issued a safety inspection hold on Fabs 12 and 14. Keelung Port reports "
        "structural inspection underway — container handling suspended. "
        "TaiwanChipCo declares force majeure on all pending orders. "
        "USGS reports strong aftershocks (5.8–6.1) expected over 72 hours."
    ),
    "signal_type": "natural_disaster",
    "severity_score": 0.95,
    "alert_type": "critical",
    "final_alert": (
        "CRITICAL ALERT — Taiwan Earthquake: Advanced Node Semiconductor Disruption\n\n"
        "A 7.6 magnitude earthquake near Hualien, Taiwan has suspended TSMC Fab 18 "
        "(3nm/5nm) operations and halted container handling at Keelung Port — the "
        "island's primary export gateway. TaiwanChipCo (SUP-001) has declared force "
        "majeure on all outstanding orders; 340+ global OEMs are affected. This is the "
        "most severe supply disruption since the 2021 TSMC drought-induced slowdown.\n\n"
        "SKU-MCU-01 (microcontrollers, critical path for 6 product lines) faces a "
        "15-day gap: stock exhausts in 6 days vs. 21-day standard lead time. "
        "SKU-MCU-03 (DSP chips) simultaneously enters critical zone at 14-day runout. "
        "Invisible risk: SinoBoard Ltd (Dongguan) supplies TSMC chip-packaging materials "
        "— Chinese overflow capacity unavailable due to US export controls.\n\n"
        "Immediate action: emergency procurement from Renesas Electronics Japan (14-day "
        "air freight, partial SKU-MCU-01 overlap, confirmed available inventory). "
        "Medium-term: India Semiconductor Mission's Micron Sanand fab and CG Power-Renesas "
        "Manesar plant are qualifying for allocation in Q3 2026 — fast-track vendor "
        "onboarding recommended now to secure Q3 capacity."
    ),
    "affected_entities": [
        "Keelung Port", "Hualien", "Taiwan", "TSMC Fab 18", "Dongguan"
    ],
    "affected_suppliers": [
        {"supplier_id": "SUP-001", "name": "TaiwanChipCo",    "country": "Taiwan", "tier": 1, "exposure_type": "direct"},
        {"supplier_id": "SUP-003", "name": "SinoBoard Ltd",   "country": "China",  "tier": 2, "exposure_type": "tier2"},
        {"supplier_id": "SUP-004", "name": "Keelung PCB Works", "country": "Taiwan", "tier": 1, "exposure_type": "port"},
    ],
    "sku_risks": [
        {
            "sku_id": "SKU-MCU-01",
            "current_stock": 600,
            "daily_consumption": 100.0,
            "runout_date": dt(6),
            "lead_time_days": 21,
            "gap_days": -15.0,
            "risk_score": 0.987,
            "confidence": 0.94,
        },
        {
            "sku_id": "SKU-MCU-03",
            "current_stock": 420,
            "daily_consumption": 30.0,
            "runout_date": dt(14),
            "lead_time_days": 28,
            "gap_days": -14.0,
            "risk_score": 0.951,
            "confidence": 0.91,
        },
        {
            "sku_id": "SKU-PCB-02",
            "current_stock": 1800,
            "daily_consumption": 180.0,
            "runout_date": dt(10),
            "lead_time_days": 28,
            "gap_days": -18.0,
            "risk_score": 0.918,
            "confidence": 0.89,
        },
    ],
    "alternatives": [
        {
            "supplier_id": "SUP-ALT-JP-01",
            "name": "Renesas Electronics Japan",
            "country": "Japan",
            "similarity_score": 0.91,
            "estimated_lead_time": 14,
            "confidence": 0.92,
        },
        {
            "supplier_id": "SUP-ALT-IN-07",
            "name": "Micron Sanand – India Semiconductor Mission",
            "country": "India",
            "similarity_score": 0.76,
            "estimated_lead_time": 18,
            "confidence": 0.73,
        },
        {
            "supplier_id": "SUP-ALT-KR-01",
            "name": "Samsung Foundry – Pyeongtaek",
            "country": "South Korea",
            "similarity_score": 0.84,
            "estimated_lead_time": 16,
            "confidence": 0.86,
        },
    ],
    "tier2_exposure": True,
    "invisible_risk": True,
    "created_at": NOW - timedelta(hours=1),
}


# ---------------------------------------------------------------------------
# Seed runner
# ---------------------------------------------------------------------------

SCENARIOS = [SCENARIO_1, SCENARIO_2, SCENARIO_3, SCENARIO_4]
LABELS = [
    "Scenario 1 — US-China Tariff War + India PCB shortage (CRITICAL 0.92)",
    "Scenario 2 — Cyclone Remal: Chennai Port Closure (HIGH 0.81)",
    "Scenario 3 — Red Sea / Suez Suspended: India Pharma Gap (HIGH 0.78)",
    "Scenario 4 — Taiwan Earthquake: Semiconductor Collapse (CRITICAL 0.95)",
]


def seed(clear: bool = False) -> None:
    db = get_db()

    if clear:
        result = db.alerts.delete_many({"user_id": "demo"})
        print(f"Cleared {result.deleted_count} existing demo alerts.")

    inserted = 0
    for scenario, label in zip(SCENARIOS, LABELS):
        doc = {**scenario, "created_at": scenario["created_at"]}
        db.alerts.insert_one(doc)
        print(f"  [ok] {label}")
        inserted += 1

    print(f"\nSeeded {inserted} demo scenarios into MongoDB '{db.name}.alerts'.")
    print("Restart the backend (or hit Scan Now) to see them in the dashboard.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Ripple demo scenarios")
    parser.add_argument("--clear", action="store_true", help="Delete existing demo alerts before seeding")
    args = parser.parse_args()
    seed(clear=args.clear)
