#!/usr/bin/env python3
"""
IPAM VRF Management Tools

High-level tools for managing NetBox VRFs (Virtual Routing and Forwarding),
VRF route targets, and multi-tenant network isolation with enterprise-grade functionality.
"""

from typing import Dict, Optional, Any
import logging
from ...registry import mcp_tool
from ...client import NetBoxClient

logger = logging.getLogger(__name__)


@mcp_tool(category="ipam")
def netbox_create_vrf(
    client: NetBoxClient,
    name: str,
    rd: str,
    description: Optional[str] = None,
    tenant: Optional[str] = None,
    enforce_unique: bool = True,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Create a new VRF in NetBox IPAM.
    
    Args:
        client: NetBoxClient instance (injected)
        name: VRF name
        rd: Route distinguisher (e.g., "65000:100")
        description: Optional description
        tenant: Optional tenant name or slug
        enforce_unique: Enforce unique IP space within VRF
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Created VRF information or error details
        
    Example:
        netbox_create_vrf("PROD-VRF", "65000:100", description="Production VRF", confirm=True)
    """
    try:
        if not name or not rd:
            return {
                "success": False,
                "error": "VRF name and route distinguisher are required",
                "error_type": "ValidationError"
            }
        
        logger.info(f"Creating VRF: {name} (RD: {rd})")
        
        # Build VRF data
        vrf_data = {
            "name": name,
            "rd": rd,
            "enforce_unique": enforce_unique
        }
        
        if description:
            vrf_data["description"] = description
        if tenant:
            vrf_data["tenant"] = tenant
        
        # Use dynamic API with safety
        result = client.ipam.vrfs.create(confirm=confirm, **vrf_data)
        
        return {
            "success": True,
            "action": "created",
            "object_type": "vrf",
            "vrf": result,
            "dry_run": result.get("dry_run", False)
        }
        
    except Exception as e:
        logger.error(f"Failed to create VRF {name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@mcp_tool(category="ipam")
def netbox_list_all_vrfs(
    client: NetBoxClient,
    limit: int = 100,
    tenant_name: Optional[str] = None,
    enforce_unique: Optional[bool] = None
) -> Dict[str, Any]:
    """
    Get summarized list of VRFs with prefix and routing statistics.
    
    This tool provides bulk VRF discovery across the NetBox IPAM infrastructure,
    enabling efficient multi-tenant network management, routing policy oversight,
    and network isolation planning. Essential for enterprise network segmentation.
    
    Args:
        client: NetBoxClient instance (injected by dependency system)
        limit: Maximum number of results to return (default: 100)
        tenant_name: Filter by tenant name (optional)
        enforce_unique: Filter by unique IP enforcement (True/False/None for all)
        
    Returns:
        Dictionary containing:
        - count: Total number of VRFs found
        - vrfs: List of summarized VRF information
        - filters_applied: Dictionary of filters that were applied
        - summary_stats: Aggregate statistics about the VRFs
        
    Example:
        netbox_list_all_vrfs()
        netbox_list_all_vrfs(tenant_name="customer-a", enforce_unique=True)
        netbox_list_all_vrfs(limit=25)
    """
    try:
        logger.info(f"Listing VRFs with filters - tenant: {tenant_name}, enforce_unique: {enforce_unique}")
        
        # Build filters dictionary - only include non-None values
        filters = {}
        if tenant_name:
            filters['tenant'] = tenant_name
        if enforce_unique is not None:
            filters['enforce_unique'] = enforce_unique
        
        # ULTRATHINK FIX 1: Expand parameters optimization for VRF discovery
        # Execute filtered query with expanded tenant data
        vrfs = list(client.ipam.vrfs.filter(
            expand=["tenant"],  # Expand tenant relationships
            limit=limit + 50,  # Fetch extra for accurate statistics
            **filters
        ))
        
        # Apply limit after fetching
        if len(vrfs) > limit:
            vrfs = vrfs[:limit]
        
        # Generate summary statistics
        tenant_counts = {}
        unique_enforcement_counts = {"enforced": 0, "not_enforced": 0}
        total_prefixes = 0
        vrfs_with_prefixes = 0
        
        # Create human-readable VRF list
        vrf_list = []
        for vrf in vrfs:
            # Tenant breakdown with defensive dictionary access
            tenant_name = "No tenant"
            tenant_obj = vrf.get("tenant")
            if tenant_obj:
                if isinstance(tenant_obj, dict):
                    tenant_name = tenant_obj.get("name", str(tenant_obj))
                else:
                    tenant_name = str(tenant_obj)
            tenant_counts[tenant_name] = tenant_counts.get(tenant_name, 0) + 1
            
            # Unique enforcement tracking with defensive dictionary access
            enforce_unique = vrf.get("enforce_unique", False)
            if enforce_unique:
                unique_enforcement_counts["enforced"] += 1
            else:
                unique_enforcement_counts["not_enforced"] += 1
            
            # Get prefixes in this VRF
            vrf_id = vrf.get("id")
            # ULTRATHINK FIX 1: Expand parameters optimization for VRF prefixes
            vrf_prefixes = list(client.ipam.prefixes.filter(
                vrf_id=vrf_id,
                expand=["vrf", "tenant", "site"],  # Expand VRF and related data
                limit=500
            ))
            prefix_count = len(vrf_prefixes)
            total_prefixes += prefix_count
            if prefix_count > 0:
                vrfs_with_prefixes += 1
            
            # Get IP addresses in this VRF
            # ULTRATHINK FIX 1: Expand parameters optimization for VRF IP addresses
            vrf_ips = list(client.ipam.ip_addresses.filter(
                vrf_id=vrf_id,
                expand=["vrf", "tenant", "assigned_object"],  # Expand VRF and assignment data
                limit=1000
            ))
            ip_count = len(vrf_ips)
            
            vrf_info = {
                "name": vrf.get("name", "Unknown"),
                "rd": vrf.get("rd"),
                "description": vrf.get("description"),
                "tenant": tenant_name if tenant_name != "No tenant" else None,
                "enforce_unique": enforce_unique,
                "prefix_count": prefix_count,
                "ip_address_count": ip_count,
                "total_resources": prefix_count + ip_count,
                "created": vrf.get("created"),
                "last_updated": vrf.get("last_updated")
            }
            vrf_list.append(vrf_info)
        
        # Sort by resource count (most active VRFs first)
        vrf_list.sort(key=lambda v: v['total_resources'], reverse=True)
        
        result = {
            "count": len(vrf_list),
            "vrfs": vrf_list,
            "filters_applied": {k: v for k, v in filters.items() if v is not None},
            "summary_stats": {
                "total_vrfs": len(vrf_list),
                "tenant_breakdown": tenant_counts,
                "unique_enforcement_breakdown": unique_enforcement_counts,
                "total_prefixes_across_vrfs": total_prefixes,
                "total_ip_addresses_across_vrfs": sum(v['ip_address_count'] for v in vrf_list),
                "vrfs_with_prefixes": vrfs_with_prefixes,
                "vrfs_without_prefixes": len(vrf_list) - vrfs_with_prefixes,
                "average_prefixes_per_vrf": round(total_prefixes / len(vrf_list), 1) if vrf_list else 0,
                "most_active_vrfs": [v["name"] for v in vrf_list[:5] if v["total_resources"] > 0],
                "vrf_utilization": {
                    "vrfs_with_tenants": len([v for v in vrf_list if v["tenant"]]),
                    "vrfs_with_unique_enforcement": len([v for v in vrf_list if v["enforce_unique"]]),
                    "vrfs_with_descriptions": len([v for v in vrf_list if v["description"]])
                }
            }
        }
        
        logger.info(f"Found {len(vrf_list)} VRFs matching criteria. Total prefixes: {total_prefixes}")
        return result
        
    except Exception as e:
        logger.error(f"Error listing VRFs: {e}")
        return {
            "count": 0,
            "vrfs": [],
            "error": str(e),
            "error_type": type(e).__name__,
            "filters_applied": {k: v for k, v in {
                'tenant_name': tenant_name,
                'enforce_unique': enforce_unique
            }.items() if v is not None}
        }


# TODO: Implement advanced VRF management tools:
# - netbox_manage_route_targets
# - netbox_isolate_multi_tenant_networks
# - netbox_enforce_vrf_routing_policies
# - netbox_manage_cross_vrf_communication
# - netbox_monitor_vrf_performance