# Ripple — Showcase Demo Script

**Recommended scenario:** Scenario 4 — Taiwan Earthquake (CRITICAL 0.95)
Most dramatic story arc: real-world event, semiconductor supply collapse, invisible tier-2 risk.

**Total runtime:** ~5 minutes

---

## Before You Start

```bash
uv run python scripts/seed_demo.py --clear   # fresh demo data
uv run python main.py                         # backend
cd frontend && npm run dev                    # frontend
```

Open `http://localhost:5173` (or your ngrok URL for remote viewers).

---

## Step 1 — News Dashboard (30 sec)

> "Ripple monitors global supply chain signals 24/7 — geopolitical events, weather, port disruptions, earthquake feeds — and classifies them automatically."

- Point to the **3-column news feed** (Weather / Geopolitical / Other)
- Show the **Port Weather strip** at the top
- Hit **Scan Now** to show a live scrape happening in real time

---

## Step 2 — Open the Taiwan Earthquake Alert (30 sec)

Click the **Taiwan Earthquake** alert card (CRITICAL, severity 0.95).

> "A 7.6 magnitude earthquake just hit Hualien. TSMC has suspended Fab 18. TaiwanChipCo has declared force majeure. Keelung Port is down."

Point to the alert detail — the compiled summary, affected suppliers, and SKU risk table.

> "Ripple didn't just detect the earthquake — it already mapped which of our suppliers are affected and which SKUs are at risk of stockout."

---

## Step 3 — Run the Pipeline (60 sec)

Hit **Analyze** (or the signal is already analyzed — show the SKU risk panel).

Walk through the results:
- **SKU-MCU-01**: risk 0.987, gap = **−15 days** → stockout in 6 days, lead time 21 days
- **SKU-MCU-03**: risk 0.951, gap = **−14 days**
- **SKU-PCB-02**: risk 0.918, gap = **−18 days**

> "Three SKUs on the critical path. The worst — SKU-MCU-01 — runs out in 6 days. Our standard lead time is 21 days. That's a 15-day hole."

Point to the **Agents panel** on the right — show which agents ran (Scraper → Supplier Mapping → Risk Scorer → Alt Sourcing → Report Compiler).

---

## Step 4 — Chat: Ask Why (45 sec)

Type in the chat:

> **"Why is SKU-MCU-01 at critical risk?"**

The agent calls `get_analysis_details` and explains:
- Stock on hand, daily usage, runout date
- Scoring methodology
- Then calls `search_history` — surfaces the 2023 Taiwan Strait tension incident where VN-FAB-03 successfully substituted

> "It's not just showing you the number — it's explaining the reasoning and pulling in historical precedent from memory."

---

## Step 5 — Chat: What If Questions (90 sec)

**Question 1 — Extended disruption:**
> **"What if the earthquake aftershocks keep the port closed for 45 days instead of 21?"**

Agent calls `simulate_scenario` with `disruption_extension_days=24`.

Expected: all 3 SKUs get significantly worse — gap deepens by 24 days, risk scores near 1.0.

> "In that scenario, we don't just have a 15-day gap — we have a 39-day gap. That's a full product line stoppage."

---

**Question 2 — Air freight mitigation:**
> **"What if we air freight SKU-MCU-01 — cutting lead time to 5 days?"**

Agent calls `simulate_scenario` with `lead_time_override_days=5`.

Expected: SKU-MCU-01 gap flips positive (+1 day buffer), risk drops sharply.

> "Air freight closes the gap entirely for MCU-01. The simulation shows a +1 day buffer instead of −15. Now you can make that call knowing the numbers."

---

**Question 3 — Demand scenario (optional, if time allows):**
> **"What if our downstream customer doubles their order this week because they're also panic-buying?"**

Agent calls `simulate_scenario` with `demand_multiplier=2.0`.

> "Demand doubling cuts our days-of-stock in half. SKU-MCU-01 now runs out in 3 days, not 6."

---

## Step 6 — Alternative Suppliers (30 sec)

Type:
> **"Find us alternative suppliers for SKU-MCU-01"**

Agent calls `request_alternatives` → Alt Sourcing agent runs → shows:
- **Renesas Electronics Japan** — similarity 0.91, lead time 14 days, confirmed inventory
- **Samsung Foundry Pyeongtaek** — similarity 0.84, 16 days
- **Micron Sanand (India)** — 0.76 similarity, 18 days, India Semiconductor Mission

> "Renesas Japan is the immediate bridge. 14-day air freight, confirmed overlap with MCU-01 spec. And for the medium term — Micron's Sanand fab is qualifying in Q3 2026. Ripple recommends fast-tracking vendor onboarding now to secure that capacity."

---

## Talking Points (if asked)

**"How does it know which suppliers are affected?"**
> Neo4j graph — 3-hop traversal of SOURCES_FROM edges. It finds not just your tier-1 suppliers but tier-2 and tier-3 dependencies that aren't in any ERP system.

**"Where does the historical memory come from?"**
> mem0 semantic memory backed by pgvector. It accumulates patterns across every analysis session — past disruptions, false positives, successful substitutions. The Taiwan Strait 2023 memory was why it immediately suggested VN-FAB-03.

**"What's the 'invisible risk' tag?"**
> SinoBoard Ltd in Dongguan supplies TSMC's chip-packaging materials. They're not a direct supplier of ours — but because TSMC's overflow capacity runs through them, and US export controls block that overflow, there's a second-order risk that no traditional ERP would surface.

**"Can it handle real-time data?"**
> Yes — hit Scan Now. It pulls live news feeds, USGS earthquake data, and GDACS disaster alerts, classifies them with Claude Haiku, and deduplicates against what's already in the database.
