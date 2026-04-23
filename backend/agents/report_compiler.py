"""
Agent 6 — Report Compiler (claude-sonnet-4-6)

Final agent in the pipeline. Receives fully-assembled state and composes
a concise, actionable alert including a ranked alternatives recommendation.
"""
from anthropic import Anthropic
from langsmith import wrappers
from dotenv import load_dotenv
from backend.graph.state import SupplyChainState

load_dotenv()

client = wrappers.wrap_anthropic(Anthropic())
MODEL = "claude-sonnet-4-6"


def _severity_label(score: float) -> str:
    if score >= 0.8:
        return "CRITICAL"
    if score >= 0.6:
        return "HIGH"
    if score >= 0.4:
        return "MEDIUM"
    return "LOW"


def run(state: SupplyChainState) -> dict:
    trace = []

    raw_signal = state.get("raw_signal", "")
    severity = state.get("severity_score", 0.0)
    signal_type = state.get("signal_type", "unknown")
    entities = state.get("affected_entities", [])
    affected_suppliers = state.get("affected_suppliers", [])
    sku_risks = state.get("sku_risks", [])
    alternatives = state.get("alternatives", [])
    tier2_exposure = state.get("tier2_exposure", False)
    invisible_risk = state.get("invisible_risk", False)
    historical_context = state.get("historical_context", "")

    severity_label = _severity_label(severity)
    trace.append(f"[Agent6] Compiling alert: severity={severity_label} tier2={tier2_exposure} skus={len(sku_risks)}")

    sku_risk_lines = []
    for r in sku_risks:
        gap = r.get("gap_days", 0)
        score = r.get("risk_score", 0)
        sku_risk_lines.append(
            f"  - {r['sku_id']}: gap_days={gap:.1f}, risk_score={score:.3f}, "
            f"confidence={r.get('confidence', 0):.1f}"
        )

    supplier_lines = []
    for s in affected_suppliers:
        supplier_lines.append(
            f"  - {s['supplier_id']} {s['name']} ({s.get('country','?')}, tier {s.get('tier','?')}, {s.get('exposure_type','?')})"
        )

    alt_lines = []
    for a in alternatives[:5]:
        alt_lines.append(
            f"  - {a.get('name', a.get('supplier_id', '?'))} ({a.get('country', '?')}) "
            f"similarity={a.get('similarity_score', 0):.2f} "
            f"lead={a.get('estimated_lead_time', '?')}d "
            f"confidence={a.get('confidence', 0):.2f}"
        )

    tier2_note = ""
    if tier2_exposure and invisible_risk:
        tier2_note = (
            "\nIMPORTANT: This is an INVISIBLE TIER-2 RISK. "
            "One or more affected suppliers appear safe on paper (tier-1) but source "
            "critical inputs from a supplier in the disruption zone. "
            "Emphasise this in the alert — it is the key insight the operator would miss without this system."
        )

    alt_guidance = ""
    if alternatives:
        alt_guidance = (
            "\nALTERNATIVES GUIDANCE: Recommend the best alternative based on the data. "
            "If gap_days < -7 (urgent), prioritise fastest lead time. "
            "For geopolitical/tariff signals, prefer suppliers outside the affected country — "
            "call out any trade framework advantages (e.g. India PLI, Indo-US bilateral). "
            "For weather/port signals, prefer geographically diverse options. "
            "State your #1 pick with 1-2 sentences of reasoning, then list others as fallbacks."
        )

    prompt = f"""You are writing a supply chain disruption alert for an operations manager.
Be specific, direct, and actionable. No filler. Use the data below exactly.

--- SIGNAL ---
Raw: {raw_signal}
Type: {signal_type}
Severity: {severity:.2f} ({severity_label})
Affected entities: {', '.join(entities)}

--- AFFECTED SUPPLIERS ---
{chr(10).join(supplier_lines) or '  None identified'}

--- AT-RISK SKUs ---
{chr(10).join(sku_risk_lines) or '  None identified'}

--- ALTERNATIVE SUPPLIERS (scored by Agent 5) ---
{chr(10).join(alt_lines) if alt_lines else '  None found'}
{alt_guidance}

--- HISTORICAL CONTEXT ---
{historical_context or 'None available'}
{tier2_note}

Write the alert now. Structure:
1. One-line headline with severity label and what happened.
2. Risk summary: which SKUs are at risk, gap_days, what that means operationally.
3. If tier-2 invisible risk: call it out explicitly with the supply chain (e.g. "Your Dutch supplier sources from Zhengzhou...").
4. Recommended action: name the #1 alternative supplier, why, and list fallbacks briefly.
5. One-line confidence/caveat.

Keep it under 200 words. Write for a supply chain manager, not an engineer."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )

    final_alert = response.content[0].text.strip()
    trace.append(f"[Agent6] Alert compiled ({len(final_alert)} chars)")

    return {
        "final_alert": final_alert,
        "alert_type": severity_label.lower(),
        "reasoning_trace": trace,
    }
