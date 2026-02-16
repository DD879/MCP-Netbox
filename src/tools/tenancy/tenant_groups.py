#!/usr/bin/env python3
"""
Tenancy Tenant Group Management Tools

High-level tools for managing NetBox tenant groups with enterprise-grade functionality.
"""

from typing import Dict, Optional, Any
import logging
from ...registry import mcp_tool
from ...client import NetBoxClient

logger = logging.getLogger(__name__)


@mcp_tool(category="tenancy")
def netbox_create_tenant_group(
    client: NetBoxClient,
    name: str,
    slug: str,
    parent: Optional[str] = None,
    description: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Create a new tenant group in NetBox Tenancy.
    
    Args:
        client: NetBoxClient instance (injected)
        name: Tenant group name
        slug: URL-friendly identifier
        parent: Optional parent group name
        description: Optional description
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Created tenant group information or error details
        
    Example:
        netbox_create_tenant_group("Enterprise Customers", "enterprise-customers", confirm=True)
    """
    try:
        if not name or not slug:
            return {
                "success": False,
                "error": "Tenant group name and slug are required",
                "error_type": "ValidationError"
            }
        
        logger.info(f"Creating tenant group: {name} (slug: {slug})")
        
        # Build tenant group data
        group_data = {
            "name": name,
            "slug": slug
        }
        
        if description:
            group_data["description"] = description
        if parent:
            group_data["parent"] = parent
        
        # Use dynamic API with safety
        result = client.tenancy.tenant_groups.create(confirm=confirm, **group_data)
        
        return {
            "success": True,
            "action": "created",
            "object_type": "tenant_group",
            "tenant_group": result,
            "dry_run": result.get("dry_run", False)
        }
        
    except Exception as e:
        logger.error(f"Failed to create tenant group {name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@mcp_tool(category="tenancy")
def netbox_list_all_tenant_groups(
    client: NetBoxClient,
    limit: int = 100,
    parent_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get summarized list of tenant groups with tenant statistics.
    
    This tool provides bulk tenant group discovery across the NetBox tenancy infrastructure,
    enabling efficient tenant organization, hierarchical management, and tenant categorization.
    Essential for enterprise multi-tenant administration and tenant relationship management.
    
    Args:
        client: NetBoxClient instance (injected by dependency system)
        limit: Maximum number of results to return (default: 100)
        parent_name: Filter by parent group name (optional)
        
    Returns:
        Dictionary containing:
        - count: Total number of tenant groups found
        - tenant_groups: List of summarized tenant group information
        - filters_applied: Dictionary of filters that were applied
        - summary_stats: Aggregate statistics about the tenant groups
        
    Example:
        netbox_list_all_tenant_groups()
        netbox_list_all_tenant_groups(parent_name="customers")
        netbox_list_all_tenant_groups(limit=25)
    """
    try:
        logger.info(f"Listing tenant groups with filters - parent: {parent_name}")
        
        # Build filters dictionary - only include non-None values
        filters = {}
        if parent_name:
            filters['parent'] = parent_name
        
        # ULTRATHINK FIX 1: Expand parameters optimization for tenant groups discovery
        # Execute filtered query with expanded parent data
        tenant_groups = list(client.tenancy.tenant_groups.filter(
            expand=["parent"],  # Expand parent group relationships
            limit=limit + 50,  # Fetch extra for accurate statistics
            **filters
        ))
        
        # Apply limit after fetching
        if len(tenant_groups) > limit:
            tenant_groups = tenant_groups[:limit]
        
        # Generate summary statistics
        parent_counts = {}
        total_tenants = 0
        groups_with_tenants = 0
        hierarchy_levels = {}
        
        # Create human-readable tenant group list
        group_list = []
        for group in tenant_groups:
            # Parent breakdown with defensive dictionary access
            parent_name = "Root level"
            parent_obj = group.get("parent")
            if parent_obj:
                if isinstance(parent_obj, dict):
                    parent_name = parent_obj.get("name", str(parent_obj))
                else:
                    parent_name = str(parent_obj)
            parent_counts[parent_name] = parent_counts.get(parent_name, 0) + 1
            
            # Get tenants in this group
            group_id = group.get("id")
            # ULTRATHINK FIX 1: Expand parameters optimization for group tenants
            group_tenants = list(client.tenancy.tenants.filter(
                group_id=group_id,
                expand=["group"],  # Expand group relationships
                limit=500
            ))
            tenant_count = len(group_tenants)
            total_tenants += tenant_count
            if tenant_count > 0:
                groups_with_tenants += 1
            
            # Calculate hierarchy level (simple depth calculation) with defensive access
            level = 0
            current_parent = parent_obj
            while current_parent and level < 10:  # Prevent infinite loops
                level += 1
                try:
                    if isinstance(current_parent, dict):
                        parent_id = current_parent.get("id")
                    else:
                        parent_id = current_parent
                    
                    if parent_id:
                        parent_detail = client.tenancy.tenant_groups.get(parent_id)
                        if isinstance(parent_detail, dict):
                            current_parent = parent_detail.get("parent")
                        else:
                            current_parent = None
                    else:
                        current_parent = None
                except:
                    break
            
            hierarchy_levels[f"Level {level}"] = hierarchy_levels.get(f"Level {level}", 0) + 1
            
            # Get child groups
            # ULTRATHINK FIX 1: Expand parameters optimization for child groups
            child_groups = list(client.tenancy.tenant_groups.filter(
                parent_id=group_id,
                expand=["parent"],  # Expand parent relationships
                limit=100
            ))
            child_count = len(child_groups)
            
            group_info = {
                "name": group.get("name", "Unknown"),
                "slug": group.get("slug", ""),
                "parent": parent_name if parent_name != "Root level" else None,
                "description": group.get("description"),
                "tenant_count": tenant_count,
                "child_group_count": child_count,
                "hierarchy_level": level,
                "total_descendants": tenant_count + child_count,
                "created": group.get("created"),
                "last_updated": group.get("last_updated")
            }
            group_list.append(group_info)
        
        # Sort by total descendants (most populated groups first)
        group_list.sort(key=lambda g: g['total_descendants'], reverse=True)
        
        result = {
            "count": len(group_list),
            "tenant_groups": group_list,
            "filters_applied": {k: v for k, v in filters.items() if v is not None},
            "summary_stats": {
                "total_groups": len(group_list),
                "parent_breakdown": parent_counts,
                "hierarchy_breakdown": hierarchy_levels,
                "total_tenants_across_groups": total_tenants,
                "groups_with_tenants": groups_with_tenants,
                "groups_without_tenants": len(group_list) - groups_with_tenants,
                "average_tenants_per_group": round(total_tenants / len(group_list), 1) if group_list else 0,
                "most_populated_groups": [g["name"] for g in group_list[:5] if g["tenant_count"] > 0],
                "organizational_structure": {
                    "root_level_groups": len([g for g in group_list if not g["parent"]]),
                    "nested_groups": len([g for g in group_list if g["parent"]]),
                    "groups_with_children": len([g for g in group_list if g["child_group_count"] > 0]),
                    "leaf_groups": len([g for g in group_list if g["child_group_count"] == 0]),
                    "deepest_level": max([g["hierarchy_level"] for g in group_list]) if group_list else 0
                }
            }
        }
        
        logger.info(f"Found {len(group_list)} tenant groups matching criteria. Total tenants: {total_tenants}")
        return result
        
    except Exception as e:
        logger.error(f"Error listing tenant groups: {e}")
        return {
            "count": 0,
            "tenant_groups": [],
            "error": str(e),
            "error_type": type(e).__name__,
            "filters_applied": {k: v for k, v in {
                'parent_name': parent_name
            }.items() if v is not None}
        }


# TODO: Implement advanced tenant group management tools:
# - netbox_reorganize_tenant_hierarchy
# - netbox_migrate_tenants_between_groups
# - netbox_analyze_tenant_group_utilization
# - netbox_bulk_tenant_group_operations