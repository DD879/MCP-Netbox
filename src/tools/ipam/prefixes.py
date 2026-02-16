#!/usr/bin/env python3
"""
IPAM Prefix Management Tools

High-level tools for managing NetBox IP prefixes and network planning.
"""

from typing import Dict, Optional, Any
import logging
from ...registry import mcp_tool
from ...client import NetBoxClient

logger = logging.getLogger(__name__)


@mcp_tool(category="ipam")
def netbox_create_prefix(
    client: NetBoxClient,
    prefix: str,
    status: str = "active",
    description: Optional[str] = None,
    site: Optional[str] = None,
    vlan: Optional[str] = None,
    tenant: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Create a new IP prefix in NetBox IPAM.
    
    Args:
        client: NetBoxClient instance (injected)
        prefix: Network prefix with CIDR notation (e.g., "192.168.1.0/24")
        status: Prefix status (active, reserved, deprecated, container)
        description: Optional description
        site: Optional site name or slug
        vlan: Optional VLAN name or ID
        tenant: Optional tenant name or slug
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Created prefix information or error details
        
    Example:
        netbox_create_prefix("192.168.1.0/24", status="active", confirm=True)
    """
    try:
        if not prefix:
            return {
                "success": False,
                "error": "Prefix is required",
                "error_type": "ValidationError"
            }
        
        logger.info(f"Creating prefix: {prefix}")
        
        # Build prefix data
        prefix_data = {
            "prefix": prefix,
            "status": status
        }
        
        if description:
            prefix_data["description"] = description
        if site:
            prefix_data["site"] = site
        if vlan:
            prefix_data["vlan"] = vlan
        if tenant:
            prefix_data["tenant"] = tenant
        
        # Use dynamic API with safety
        result = client.ipam.prefixes.create(confirm=confirm, **prefix_data)
        
        return {
            "success": True,
            "action": "created",
            "object_type": "prefix",
            "prefix": result,
            "dry_run": result.get("dry_run", False)
        }
        
    except Exception as e:
        logger.error(f"Failed to create prefix {prefix}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@mcp_tool(category="ipam")
def netbox_list_all_prefixes(
    client: NetBoxClient,
    limit: int = 100,
    site_name: Optional[str] = None,
    tenant_name: Optional[str] = None,
    status: Optional[str] = None,
    vrf_name: Optional[str] = None,
    role: Optional[str] = None,
    family: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get summarized list of IP prefixes with optional filtering.
    
    This tool provides bulk prefix discovery across the NetBox IPAM infrastructure,
    enabling efficient network planning, IP space auditing, and capacity management.
    Essential for network administrators and IP address management.
    
    Args:
        client: NetBoxClient instance (injected by dependency system)
        limit: Maximum number of results to return (default: 100)
        site_name: Filter by site name (optional)
        tenant_name: Filter by tenant name (optional)
        status: Filter by prefix status (active, reserved, deprecated, container)
        vrf_name: Filter by VRF name (optional)
        role: Filter by prefix role (optional)
        family: Filter by IP family (4 for IPv4, 6 for IPv6)
        
    Returns:
        Dictionary containing:
        - count: Total number of prefixes found
        - prefixes: List of summarized prefix information
        - filters_applied: Dictionary of filters that were applied
        - summary_stats: Aggregate statistics about the prefixes
        
    Example:
        netbox_list_all_prefixes(status="active", site_name="datacenter-1")
        netbox_list_all_prefixes(family=4, tenant_name="customer-a")
        netbox_list_all_prefixes(vrf_name="MGMT", limit=50)
    """
    try:
        logger.info(f"Listing prefixes with filters - site: {site_name}, tenant: {tenant_name}, status: {status}, vrf: {vrf_name}, family: {family}")
        
        # Build filters dictionary - only include non-None values
        filters = {}
        if site_name:
            filters['site'] = site_name
        if tenant_name:
            filters['tenant'] = tenant_name
        if status:
            filters['status'] = status
        if vrf_name:
            filters['vrf'] = vrf_name
        if role:
            filters['role'] = role
        if family:
            filters['family'] = family
        
        # Execute filtered query with limit
        prefixes = list(client.ipam.prefixes.filter(**filters))
        
        # Apply limit after fetching
        if len(prefixes) > limit:
            prefixes = prefixes[:limit]
        
        # Generate summary statistics
        status_counts = {}
        site_counts = {}
        tenant_counts = {}
        vrf_counts = {}
        family_counts = {}
        role_counts = {}
        
        # Utilization tracking
        total_prefixes = len(prefixes)
        ipv4_count = 0
        ipv6_count = 0
        utilized_prefixes = 0
        
        for prefix in prefixes:
            # Status breakdown with defensive dictionary access
            status_obj = prefix.get("status", {})
            if isinstance(status_obj, dict):
                status = status_obj.get("label", "N/A")
            else:
                status = str(status_obj) if status_obj else "N/A"
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Site breakdown with defensive dictionary access
            site_obj = prefix.get("site")
            if site_obj:
                if isinstance(site_obj, dict):
                    site_name = site_obj.get("name", str(site_obj))
                else:
                    site_name = str(site_obj)
                site_counts[site_name] = site_counts.get(site_name, 0) + 1
            
            # Tenant breakdown with defensive dictionary access
            tenant_obj = prefix.get("tenant")
            if tenant_obj:
                if isinstance(tenant_obj, dict):
                    tenant_name = tenant_obj.get("name", str(tenant_obj))
                else:
                    tenant_name = str(tenant_obj)
                tenant_counts[tenant_name] = tenant_counts.get(tenant_name, 0) + 1
            
            # VRF breakdown with defensive dictionary access
            vrf_obj = prefix.get("vrf")
            if vrf_obj:
                if isinstance(vrf_obj, dict):
                    vrf_name = vrf_obj.get("name", str(vrf_obj))
                else:
                    vrf_name = str(vrf_obj)
                vrf_counts[vrf_name] = vrf_counts.get(vrf_name, 0) + 1
            
            # Role breakdown with defensive dictionary access
            role_obj = prefix.get("role")
            if role_obj:
                if isinstance(role_obj, dict):
                    role_name = role_obj.get("name", str(role_obj))
                else:
                    role_name = str(role_obj)
                role_counts[role_name] = role_counts.get(role_name, 0) + 1
            
            # Family tracking with defensive dictionary access
            family_obj = prefix.get("family")
            if family_obj:
                if isinstance(family_obj, dict):
                    family_val = family_obj.get("value", family_obj.get("label", 4))
                else:
                    family_val = family_obj
                family_counts[f"IPv{family_val}"] = family_counts.get(f"IPv{family_val}", 0) + 1
                if family_val == 4:
                    ipv4_count += 1
                elif family_val == 6:
                    ipv6_count += 1
            
            # Utilization tracking with defensive dictionary access
            utilization = prefix.get("utilization", 0)
            if utilization and utilization > 0:
                utilized_prefixes += 1
        
        # Create human-readable prefix list
        prefix_list = []
        for prefix in prefixes:
            # Defensive dictionary access for family
            family_obj = prefix.get("family")
            family_str = "Unknown"
            if family_obj:
                if isinstance(family_obj, dict):
                    family_val = family_obj.get("value", family_obj.get("label", 4))
                    family_str = f"IPv{family_val}"
                else:
                    family_str = f"IPv{family_obj}"
            
            # Defensive dictionary access for status
            status_obj = prefix.get("status", {})
            if isinstance(status_obj, dict):
                status = status_obj.get("label", "N/A")
            else:
                status = str(status_obj) if status_obj else "N/A"
            
            # Defensive dictionary access for site
            site_obj = prefix.get("site")
            site_name = None
            if site_obj:
                if isinstance(site_obj, dict):
                    site_name = site_obj.get("name")
                else:
                    site_name = str(site_obj)
            
            # Defensive dictionary access for tenant
            tenant_obj = prefix.get("tenant")
            tenant_name = None
            if tenant_obj:
                if isinstance(tenant_obj, dict):
                    tenant_name = tenant_obj.get("name")
                else:
                    tenant_name = str(tenant_obj)
            
            # Defensive dictionary access for vrf
            vrf_obj = prefix.get("vrf")
            vrf_name = None
            if vrf_obj:
                if isinstance(vrf_obj, dict):
                    vrf_name = vrf_obj.get("name")
                else:
                    vrf_name = str(vrf_obj)
            
            # Defensive dictionary access for role
            role_obj = prefix.get("role")
            role_name = None
            if role_obj:
                if isinstance(role_obj, dict):
                    role_name = role_obj.get("name")
                else:
                    role_name = str(role_obj)
            
            prefix_info = {
                "prefix": prefix.get("prefix", "Unknown"),
                "family": family_str,
                "status": status,
                "site": site_name,
                "tenant": tenant_name,
                "vrf": vrf_name,
                "role": role_name,
                "description": prefix.get("description"),
                "utilization": prefix.get("utilization"),
                "is_pool": prefix.get("is_pool"),
                "mark_utilized": prefix.get("mark_utilized"),
                "created": prefix.get("created")
            }
            prefix_list.append(prefix_info)
        
        result = {
            "count": len(prefix_list),
            "prefixes": prefix_list,
            "filters_applied": {k: v for k, v in filters.items() if v is not None},
            "summary_stats": {
                "total_prefixes": total_prefixes,
                "status_breakdown": status_counts,
                "site_breakdown": site_counts,
                "tenant_breakdown": tenant_counts,
                "vrf_breakdown": vrf_counts,
                "role_breakdown": role_counts,
                "family_breakdown": family_counts,
                "ipv4_prefixes": ipv4_count,
                "ipv6_prefixes": ipv6_count,
                "prefixes_with_utilization": utilized_prefixes,
                "prefixes_with_sites": len([p for p in prefix_list if p['site']]),
                "prefixes_with_tenants": len([p for p in prefix_list if p['tenant']]),
                "prefixes_with_vrf": len([p for p in prefix_list if p['vrf']]),
                "pool_prefixes": len([p for p in prefix_list if p['is_pool']])
            }
        }
        
        logger.info(f"Found {len(prefix_list)} prefixes matching criteria. Status breakdown: {status_counts}")
        return result
        
    except Exception as e:
        logger.error(f"Error listing prefixes: {e}")
        return {
            "count": 0,
            "prefixes": [],
            "error": str(e),
            "error_type": type(e).__name__,
            "filters_applied": {k: v for k, v in {
                'site_name': site_name,
                'tenant_name': tenant_name,
                'status': status,
                'vrf_name': vrf_name,
                'role': role,
                'family': family
            }.items() if v is not None}
        }