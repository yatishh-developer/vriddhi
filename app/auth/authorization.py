from typing import Iterable, Optional

from auth.errors import AuthError
from auth.principal import ActorType, PrincipalContext


# Current StaffProfile JSON uses these legacy key names. New domain code can
# consistently request dotted permissions while old staff records keep working.
LEGACY_PERMISSION_ALIASES = {
    "create_bill": "billing.create",
    "cancel_bill": "billing.cancel",
    "void_bill": "billing.void",
    "refund_bill": "billing.refund",
    "collect_payment": "payments.collect",
    "apply_discount": "billing.discount",
    "credit_sale": "credit.create",
    "create_kot": "kot.create",
    "cancel_kot": "kot.cancel",
    "convert_kot_to_bill": "billing.create",
    "hold_bill": "billing.hold",
    "resume_held_bill": "billing.resume_held",
    "manage_products": "products.manage",
    "view_reports": "reports.view",
    "manage_staff": "staff.manage",
}

# One legacy action can authorize several actor-neutral v1 operations.  This
# keeps existing staff profiles usable while new roles can store the dotted
# permissions directly.
LEGACY_PERMISSION_GRANTS = {
    "create_bill": {
        "orders.view", "orders.create", "orders.modify", "products.view",
        "customers.view", "customers.create",
    },
    "hold_bill": {"orders.hold"},
    "resume_held_bill": {"orders.resume"},
    "cancel_bill": {"orders.cancel"},
}


def permissions_from_legacy_map(permissions: dict[str, object]) -> frozenset[str]:
    granted = {key for key, value in permissions.items() if value is True}
    granted.update(
        alias for legacy, alias in LEGACY_PERMISSION_ALIASES.items() if permissions.get(legacy) is True
    )
    for legacy, mapped_permissions in LEGACY_PERMISSION_GRANTS.items():
        if permissions.get(legacy) is True:
            granted.update(mapped_permissions)
    return frozenset(granted)


def require_permission(principal: PrincipalContext, permission: str) -> PrincipalContext:
    if "*" not in principal.permissions and permission not in principal.permissions:
        raise AuthError(403, "PERMISSION_DENIED", "You do not have permission for this action.")
    return principal


def require_any_permission(
    principal: PrincipalContext,
    permissions: Iterable[str],
) -> PrincipalContext:
    if "*" in principal.permissions or any(item in principal.permissions for item in permissions):
        return principal
    raise AuthError(403, "PERMISSION_DENIED", "You do not have permission for this action.")


def require_capability(principal: PrincipalContext, capability: str) -> PrincipalContext:
    if "*" not in principal.capabilities and capability not in principal.capabilities:
        raise AuthError(403, "PERMISSION_DENIED", "This capability is not enabled for this business.")
    return principal


def require_business_access(principal: PrincipalContext, business_id: Optional[str]) -> PrincipalContext:
    if business_id and business_id != principal.business_id:
        raise AuthError(403, "BUSINESS_ACCESS_DENIED", "You cannot access this business.")
    return principal


def require_branch_access(principal: PrincipalContext, branch_id: Optional[str]) -> PrincipalContext:
    requested_branch = (branch_id or "main").strip() or "main"
    if principal.actor_type == ActorType.WORKER:
        principal_branch = (principal.branch_id or "main").strip() or "main"
        if requested_branch != principal_branch:
            raise AuthError(403, "BRANCH_ACCESS_DENIED", "You cannot access this branch.")
    return principal
