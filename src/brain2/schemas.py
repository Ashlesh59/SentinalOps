import uuid
from typing import List, Literal, Optional, Union
from pydantic import BaseModel, Field

class EvidenceReference(BaseModel):
    evidence_ref: str = Field(..., description="The Safe Alias of the evidence (e.g. SIGNAL_001, EVIDENCE_A)")
    reason: str = Field(..., description="Why this evidence supports or contradicts the hypothesis")

class MissingEvidence(BaseModel):
    evidence_type: str = Field(..., description="The type of evidence missing (e.g. Process Tree, Authentication History)")
    reason: str = Field(..., description="Why this evidence is needed")

class NextBestAction(BaseModel):
    action_type: str = Field(..., description="The action to take (e.g. COLLECT_PROCESS_TREE, ISOLATE_HOST)")
    reason: str = Field(..., description="Why this action is recommended")
    supporting_evidence_refs: List[str] = Field(default_factory=list, description="Safe Aliases supporting this action")

class AttackHypothesis(BaseModel):
    technique_id: str = Field(..., description="MITRE ATT&CK Technique ID (e.g. T1078, T1003)")
    technique_name: Optional[str] = Field(default=None, description="MITRE ATT&CK Technique Name (e.g. Credential Dumping)")
    confidence: Literal["LOW", "MEDIUM", "HIGH", "CERTAIN"] = Field(..., description="Confidence in this technique")
    evidence_refs: List[str] = Field(default_factory=list, description="Safe Aliases mapped to this technique")

class InvestigationResultSchema(BaseModel):
    primary_hypothesis: str = Field(..., description="The primary hypothesis of what happened")
    incident_narrative: str = Field(default="", description="Short analyst-readable narrative of the incident progression")
    
    supporting_evidence: List[EvidenceReference] = Field(default_factory=list)
    contradicting_evidence: List[EvidenceReference] = Field(default_factory=list)
    missing_evidence: List[MissingEvidence] = Field(default_factory=list)
    
    recommended_disposition: Literal["LIKELY_TRUE_POSITIVE", "LIKELY_BENIGN", "UNCERTAIN"]
    confidence: int = Field(default=85, ge=0, le=100, description="Overall AI confidence score 0-100%")
    recommended_priority: Literal["LOW", "MEDIUM", "HIGH", "URGENT", "CRITICAL"]
    estimated_impact: Literal["LOW", "MODERATE", "HIGH", "UNKNOWN"] = Field(default="HIGH", description="Advisory estimated business or security impact")
    
    confidence_drivers: List[str] = Field(default_factory=list, description="Key facts increasing investigation confidence")
    confidence_reducers: List[str] = Field(default_factory=list, description="Key uncertainties reducing confidence")
    
    next_best_actions: List[NextBestAction] = Field(default_factory=list)
    response_considerations: List[str] = Field(default_factory=list, description="Advisory response actions for analyst consideration")
    attack_hypotheses: List[AttackHypothesis] = Field(default_factory=list)
    
    limitations: str = Field(default="None", description="Any limitations or truncated evidence notes")
