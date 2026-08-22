import uuid
import hashlib
from typing import List, Dict, Any, Tuple, Set
from datetime import timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.models import AggregatedSignalModel, SignalEntityModel
from src.brain1.policy import CorrelationPolicy
from src.brain1.context import TenantSecurityContext
from src.brain1.metrics import Brain1Metrics

def generate_edge_id(tenant_id: str, left_id: uuid.UUID, right_id: uuid.UUID, rule_version: str) -> uuid.UUID:
    sorted_ids = sorted([str(left_id), str(right_id)])
    canonical_string = f"{tenant_id}:{rule_version}:{sorted_ids[0]}:{sorted_ids[1]}"
    sha256 = hashlib.sha256(canonical_string.encode('utf-8')).digest()
    return uuid.UUID(bytes=sha256[:16])

def score_pair(
    entities_a: List[Tuple[str, str]], 
    entities_b: List[Tuple[str, str]], 
    signal_a: AggregatedSignalModel, 
    signal_b: AggregatedSignalModel,
    policy: CorrelationPolicy,
    context: TenantSecurityContext
) -> Tuple[int, List[str]]:
    score = 0
    reasons = []
    
    dict_a = {}
    for t, v in entities_a:
        dict_a.setdefault(t, set()).add(v)
        
    dict_b = {}
    for t, v in entities_b:
        dict_b.setdefault(t, set()).add(v)
        
    # HASH
    hashes_a = dict_a.get("HASH", set())
    hashes_b = dict_b.get("HASH", set())
    if hashes_a & hashes_b:
        score += policy.weights.get("HASH", 0)
        reasons.append("SAME_UNIQUE_HASH")
        
    # DEVICE
    devices_a = dict_a.get("DEVICE", set())
    devices_b = dict_b.get("DEVICE", set())
    if devices_a & devices_b:
        score += policy.weights.get("DEVICE", 0)
        reasons.append("SAME_DEVICE")
        
    # USER (non-generic)
    users_a = dict_a.get("USER", set()) - policy.generic_users - context.additional_generic_users
    users_b = dict_b.get("USER", set()) - policy.generic_users - context.additional_generic_users
    if users_a & users_b:
        score += policy.weights.get("USER", 0)
        reasons.append("SAME_USER")
        
    # IP
    ips_a = dict_a.get("IP", set()) - context.known_nat_ips - context.known_vpn_ips - context.known_proxy_ips
    ips_b = dict_b.get("IP", set()) - context.known_nat_ips - context.known_vpn_ips - context.known_proxy_ips
    if ips_a & ips_b:
        score += policy.weights.get("IP", 0)
        reasons.append("SAME_IP")
        
    # Time proximity (interval gap)
    gap1 = (signal_a.first_seen - signal_b.last_seen).total_seconds()
    gap2 = (signal_b.first_seen - signal_a.last_seen).total_seconds()
    gap_seconds = max(0, gap1, gap2)
        
    if gap_seconds <= 300:
        score += policy.temporal_gap_5m_score
        reasons.append("TIME_PROXIMITY_5M")
    elif gap_seconds <= 3600:
        score += policy.temporal_gap_60m_score
        reasons.append("TIME_PROXIMITY_60M")
        
    return score, reasons

async def find_candidates(
    session: AsyncSession,
    target_signal: AggregatedSignalModel, 
    target_entities: List[Tuple[str, str]], 
    policy: CorrelationPolicy,
    context: TenantSecurityContext,
    metrics: Brain1Metrics
) -> Set[uuid.UUID]:
    candidate_ids = set()
    window = timedelta(seconds=policy.candidate_window_seconds)
    start_window = target_signal.first_seen - window
    end_window = target_signal.last_seen + window
    
    primary_entities = []
    for t, v in target_entities:
        if t in policy.primary_candidate_entities:
            if t == "USER" and (v in policy.generic_users or v in context.additional_generic_users):
                continue
            primary_entities.append((t, v))
            
    if not primary_entities:
        return set()
        
    for t, v in primary_entities:
        metrics.candidate_queries += 1
        result = await session.execute(
            select(SignalEntityModel.aggregated_signal_id)
            .where(
                SignalEntityModel.tenant_id == target_signal.tenant_id,
                SignalEntityModel.entity_type == t,
                SignalEntityModel.entity_value == v,
                SignalEntityModel.first_seen <= end_window,
                SignalEntityModel.last_seen >= start_window,
                SignalEntityModel.aggregated_signal_id != target_signal.id
            )
            .order_by(SignalEntityModel.last_seen.desc())
            .limit(1000)
        )
        fetched = result.scalars().all()
        metrics.candidate_rows_evaluated += len(fetched)
        if len(fetched) == 1000:
            metrics.candidate_set_truncated = True
            print(f"WARNING: Candidate explosion on {t}:{v}")
        
        candidate_ids.update(fetched)
        
    metrics.max_candidate_set_size = max(metrics.max_candidate_set_size, len(candidate_ids))
    return candidate_ids
