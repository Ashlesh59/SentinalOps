from typing import List, Tuple
from src.db.models import NormalizedAlertModel
from src.brain1.enums import EntityType

def extract_alert_entities(alert: NormalizedAlertModel) -> List[Tuple[EntityType, str]]:
    """
    Extracts individual non-fuzzy entities from a single alert.
    """
    entities = []
    
    if alert.user:
        entities.append((EntityType.USER, alert.user.strip()))
    if alert.host:
        entities.append((EntityType.DEVICE, alert.host.strip()))
    if alert.src_ip:
        entities.append((EntityType.IP, alert.src_ip.strip()))
    if alert.dst_ip:
        entities.append((EntityType.IP, alert.dst_ip.strip()))
    if alert.domain:
        entities.append((EntityType.DOMAIN, alert.domain.strip()))
    if alert.process_name:
        entities.append((EntityType.PROCESS, alert.process_name.strip()))
    if alert.file_hash:
        entities.append((EntityType.HASH, alert.file_hash.strip()))
        
    # Deduplicate
    return list(set(entities))
