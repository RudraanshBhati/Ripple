import operator
from typing import Annotated, List, Optional, Dict, Any
from typing_extensions import TypedDict
from datetime import datetime


class SKURisk(TypedDict):
    sku_id: str
    current_stock: int
    daily_consumption: float
    runout_date: datetime
    lead_time_days: int
    gap_days: float
    risk_score: float
    confidence: float


class AlternativeSupplier(TypedDict):
    supplier_id: str
    name: str
    country: str
    similarity_score: float
    estimated_lead_time: int
    confidence: float


class SupplyChainState(TypedDict):
    # --- Signal ---
    raw_signal: Optional[str]
    signal_type: Optional[str]
    severity_score: float
    affected_entities: List[str]

    # --- Supplier mapping ---
    affected_suppliers: List[Dict[str, Any]]
    tier2_exposure: bool
    invisible_risk: bool
    supplier_mapping_done: bool

    # --- Risk scoring ---
    sku_risks: List[SKURisk]
    historical_context: Optional[str]
    risk_scored: bool

    # --- Alt sourcing ---
    alternatives: List[AlternativeSupplier]
    alternatives_found: bool

    # --- Output ---
    alert_ready: bool
    alert_type: str
    final_alert: Optional[str]

    # --- Chat / orchestrator ---
    messages: List[Dict[str, Any]]
    pending_user_question: Optional[str]
    next_agent: Optional[str]
    alternatives_requested: bool

    # --- Meta ---
    reasoning_trace: Annotated[List[str], operator.add]
    session_id: str
    timestamp: datetime
