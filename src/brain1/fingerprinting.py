import hashlib
from src.db.models import NormalizedAlertModel

def generate_dedup_fingerprint(alert: NormalizedAlertModel) -> str | None:
    """
    Generates a deterministic deduplication fingerprint using SHA-256.
    NEVER use Python's built-in hash().
    """
    if not alert.source_event_id:
        return None
        
    components = [
        str(alert.tenant_id),
        str(alert.source_type),
        str(alert.source_vendor),
        str(alert.source_product),
        str(alert.source_event_id)
    ]
    
    # Canonical serialization
    canonical_string = ":".join(components)
    
    sha256 = hashlib.sha256(canonical_string.encode('utf-8')).hexdigest()
    return f"exact-v1:{sha256}"
