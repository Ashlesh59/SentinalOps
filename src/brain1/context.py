from typing import Set
from pydantic import BaseModel, Field

class TenantSecurityContext(BaseModel):
    tenant_id: str
    additional_generic_users: Set[str] = Field(default_factory=set)
    known_nat_ips: Set[str] = Field(default_factory=set)
    known_vpn_ips: Set[str] = Field(default_factory=set)
    known_proxy_ips: Set[str] = Field(default_factory=set)
    context_version: str = "1.0"

class TenantSecurityContextResolver:
    @staticmethod
    def resolve(tenant_id: str) -> TenantSecurityContext:
        # Default empty context for MVP
        return TenantSecurityContext(tenant_id=tenant_id)
