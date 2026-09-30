from dataclasses import dataclass
from enum import StrEnum
from typing import FrozenSet, Optional


class ActorType(StrEnum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    WORKER = "WORKER"


@dataclass(frozen=True)
class PrincipalContext:
    """Normalized identity used by new authorization-aware code.

    Existing routes can continue receiving User or StaffProfile while resolving
    tokens through this same source of truth.
    """

    principal_id: str
    actor_type: ActorType
    business_id: str
    role: str
    user_id: Optional[str] = None
    staff_id: Optional[str] = None
    branch_id: Optional[str] = None
    membership_id: Optional[str] = None
    permissions: FrozenSet[str] = frozenset()
    capabilities: FrozenSet[str] = frozenset()
    device_id: Optional[str] = None
    session_id: Optional[str] = None
    token_jti: Optional[str] = None
