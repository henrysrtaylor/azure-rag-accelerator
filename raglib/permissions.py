"""Document-level security (DLS) for Azure AI Search.

Builds OData filter expressions from user security groups to restrict
document access based on Entra ID group membership.
"""
import logging

logger = logging.getLogger(__name__)


def build_security_filter(
    security_groups: list[str] | None,
    field: str = "security_groups"
) -> str | None:
    """
    Build an OData filter expression from user security groups.

    Args:
        security_groups: List of group names from JWT token. Pass None to disable
                        filtering (full access), or empty list to deny all access.
        field: Name of the Collection(Edm.String) field in the search index.

    Returns:
        OData filter string for Azure AI Search, or None if no filter applied.

    Example:
        >>> build_security_filter(["group-a", "group-b"])
        "security_groups/any(g: search.in(g, 'group-a,group-b'))"
    """
    if security_groups is None:
        logger.info("[PERMISSIONS] No filter applied - full access")
        return None
    
    if not security_groups:
        logger.warning("[PERMISSIONS] Empty groups list - denying all access")
        return f"{field}/any(g: g eq '__DENY_ALL__')"
    
    groups_str = ",".join(security_groups)
    filter_expr = f"{field}/any(g: search.in(g, '{groups_str}'))"
    logger.info("[PERMISSIONS] Filter applied with %d group(s)", len(security_groups))
    return filter_expr
