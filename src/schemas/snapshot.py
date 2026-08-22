import uuid
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class SignalSnapshot(BaseModel):
    signal_id: uuid.UUID
    tenant_id: str
    first_seen: datetime
    last_seen: datetime
    occurrence_count: int
    severity: str
    category: str
    alert_type: str
    source_vendor: str
    source_product: str
    entities: Dict[str, Any]

class EdgeSnapshot(BaseModel):
    left_signal_id: uuid.UUID
    right_signal_id: uuid.UUID
    score: int
    reasons: List[str]
    rule_version: str

class Brain1IncidentSnapshot(BaseModel):
    incident_id: uuid.UUID
    tenant_id: str
    incident_key: str
    status: str
    incident_type: str
    first_seen: datetime
    last_seen: datetime
    severity: str
    title: str
    anchor_entities: Dict[str, Any]
    correlation_rule_version: str
    incident_version: int
    signals: List[SignalSnapshot] = Field(default_factory=list)
    edges: List[EdgeSnapshot] = Field(default_factory=list)
