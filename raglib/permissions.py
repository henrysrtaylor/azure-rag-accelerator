"""Document-level security (DLS) for Azure AI Search.

Builds OData filter expressions from user security groups to restrict
document access based on Entra ID group membership.
"""
import logging
import os

from raglib.log import log_message

# Control logging via environment variable
_SHOULD_LOG = os.getenv("OPTION_LOGGING", "true").lower() == "true"


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
        log_message(_SHOULD_LOG, False, "[PERMISSIONS] No filter applied - full access", logging.INFO)
        return None
    
    if not security_groups:
        log_message(_SHOULD_LOG, False, "[PERMISSIONS] Empty groups list - denying all access", logging.WARNING)
        return f"{field}/any(g: g eq '__DENY_ALL__')"
    
    groups_str = ",".join(security_groups)
    filter_expr = f"{field}/any(g: search.in(g, '{groups_str}'))"
    log_message(_SHOULD_LOG, False, f"[PERMISSIONS] Filter applied with {len(security_groups)} group(s)", logging.INFO)
    return filter_expr
