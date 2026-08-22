import uuid
import hashlib
from typing import List, Dict, Any, Tuple, Optional, Set
from src.db.models import IncidentModel, AggregatedSignalModel, CorrelationEdgeModel
from src.brain1.policy import CorrelationPolicy
from src.brain1.context import TenantSecurityContext

def generate_incident_key(tenant_id: str, rule_version: str, anchor_signal_id: uuid.UUID) -> str:
    canonical_string = f"{tenant_id}:{rule_version}:{anchor_signal_id}"
    return hashlib.sha256(canonical_string.encode('utf-8')).hexdigest()

def extract_anchors(entities: List[Tuple[str, str]], policy: CorrelationPolicy, context: TenantSecurityContext) -> Dict[str, List[str]]:
    anchors = {}
    for t, v in entities:
        if t in ["DEVICE", "HASH"]:
            anchors.setdefault(t, []).append(v)
        elif t == "USER" and v not in policy.generic_users and v not in context.additional_generic_users:
            anchors.setdefault(t, []).append(v)
            
    return anchors

def match_incident(
    target_signal: AggregatedSignalModel, 
    target_entities: List[Tuple[str, str]],
    candidate_edges: List[CorrelationEdgeModel], 
    active_incidents: List[Tuple[IncidentModel, Set[uuid.UUID]]],
    policy: CorrelationPolicy,
    context: TenantSecurityContext
) -> Optional[IncidentModel]:
    qualifying_edges = set()
    for e in candidate_edges:
        if e.score >= policy.edge_threshold:
            qualifying_edges.add(e.left_signal_id)
            qualifying_edges.add(e.right_signal_id)
    
    target_anchors = extract_anchors(target_entities, policy, context)
    target_anchors_set = set(f"{k}:{v}" for k, vals in target_anchors.items() for v in vals)
            
    best_incident = None
    best_score = None
    
    for inc, member_ids in active_incidents:
        if not (qualifying_edges & member_ids):
            continue
            
        inc_anchors_set = set(f"{k}:{v}" for k, vals in inc.anchor_entities.items() for v in vals)
        overlap_count = len(target_anchors_set & inc_anchors_set)
        
        if overlap_count == 0:
            continue
            
        max_edge_score = 0
        for edge in candidate_edges:
            if (edge.left_signal_id in member_ids or edge.right_signal_id in member_ids) and edge.score >= policy.edge_threshold:
                max_edge_score = max(max_edge_score, edge.score)
                
        current_tiebreak = (max_edge_score, overlap_count, -inc.first_seen.timestamp())
        
        if best_incident is None:
            best_incident = inc
            best_score = current_tiebreak
        elif current_tiebreak > best_score:
            best_incident = inc
            best_score = current_tiebreak
        elif current_tiebreak == best_score:
            if inc.incident_key < best_incident.incident_key:
                best_incident = inc
                
    return best_incident
