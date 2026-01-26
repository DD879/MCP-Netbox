#!/usr/bin/env python3
"""
IPAM VLAN Management Tools

High-level tools for managing NetBox VLANs and VLAN assignments.
"""

from typing import Dict, Optional, Any
import logging
from ...registry import mcp_tool
from ...client import NetBoxClient

logger = logging.getLogger(__name__)


@mcp_tool(category="ipam")
def netbox_create_vlan(
    client: NetBoxClient,
    name: str,
    vid: int,
    status: str = "active",
    description: Optional[str] = None,
    site: Optional[str] = None,
    group: Optional[str] = None,
    tenant: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Create a new VLAN in NetBox IPAM.
    
    Args:
        client: NetBoxClient instance (injected)
        name: VLAN name
        vid: VLAN ID (1-4094)
        status: VLAN status (active, reserved, deprecated)
        description: Optional description
        site: Optional site name or slug
        group: Optional VLAN group name
        tenant: Optional tenant name or slug
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Created VLAN information or error details
        
    Example:
        netbox_create_vlan("Management", 100, status="active", confirm=True)
    """
    try:
        if not name or not vid:
            return {
                "success": False,
                "error": "VLAN name and VID are required",
                "error_type": "ValidationError"
            }
        
        if not (1 <= vid <= 4094):
            return {
                "success": False,
                "error": "VID must be between 1 and 4094",
                "error_type": "ValidationError"
            }
        
        logger.info(f"Creating VLAN: {name} (VID: {vid})")
        
        # Build VLAN data
        vlan_data = {
            "name": name,
            "vid": vid,
            "status": status
        }
        
        if description:
            vlan_data["description"] = description
        if site:
            vlan_data["site"] = site
        if group:
            vlan_data["group"] = group
        if tenant:
            vlan_data["tenant"] = tenant
        
        # Use dynamic API with safety
        result = client.ipam.vlans.create(confirm=confirm, **vlan_data)
        
        return {
            "success": True,
            "action": "created",
            "object_type": "vlan",
            "vlan": result,
            "dry_run": result.get("dry_run", False)
        }
        
    except Exception as e:
        logger.error(f"Failed to create VLAN {name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@mcp_tool(category="ipam")
def netbox_find_available_vlan_id(
    client: NetBoxClient,
    site: Optional[str] = None,
    group: Optional[str] = None,
    start_vid: int = 1,
    end_vid: int = 4094
) -> Dict[str, Any]:
    """
    Find available VLAN IDs in a range.
    
    Args:
        client: NetBoxClient instance (injected)
        site: Optional site name or slug to filter VLANs
        group: Optional VLAN group name to filter VLANs
        start_vid: Starting VLAN ID (default: 1)
        end_vid: Ending VLAN ID (default: 4094)
        
    Returns:
        Available VLAN IDs or error details
        
    Example:
        netbox_find_available_vlan_id(site="main-dc", start_vid=100, end_vid=200)
    """
    try:
        if not (1 <= start_vid <= 4094) or not (1 <= end_vid <= 4094):
            return {
                "success": False,
                "error": "VLAN IDs must be between 1 and 4094",
                "error_type": "ValidationError"
            }
        
        if start_vid > end_vid:
            return {
                "success": False,
                "error": "start_vid must be less than or equal to end_vid",
                "error_type": "ValidationError"
            }
        
        logger.info(f"Finding available VLAN IDs between {start_vid} and {end_vid}")
        
        # Build filter
        vlan_filter = {}
        if site:
            vlan_filter["site"] = site
        if group:
            vlan_filter["group"] = group
        
        # Get existing VLANs
        existing_vlans = client.ipam.vlans.filter(**vlan_filter)
        used_vids = {vlan["vid"] for vlan in existing_vlans}
        
        # Find available VIDs
        available_vids = []
        for vid in range(start_vid, end_vid + 1):
            if vid not in used_vids:
                available_vids.append(vid)
        
        return {
            "success": True,
            "available_vids": available_vids,
            "count": len(available_vids),
            "range": {"start": start_vid, "end": end_vid},
            "filter": vlan_filter
        }
        
    except Exception as e:
        logger.error(f"Failed to find available VLAN IDs: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@mcp_tool(category="ipam")
def netbox_list_all_vlans(
    client: NetBoxClient,
    limit: int = 100,
    site_name: Optional[str] = None,
    tenant_name: Optional[str] = None,
    status: Optional[str] = None,
    group_name: Optional[str] = None,
    role: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get summarized list of VLANs with optional filtering.
    
    This tool provides bulk VLAN discovery across the NetBox IPAM infrastructure,
    enabling efficient network segmentation management, VLAN planning, and capacity
    oversight. Essential for network administrators managing VLAN assignments.
    
    Args:
        client: NetBoxClient instance (injected by dependency system)
        limit: Maximum number of results to return (default: 100)
        site_name: Filter by site name (optional)
        tenant_name: Filter by tenant name (optional)
        status: Filter by VLAN status (active, reserved, deprecated)
        group_name: Filter by VLAN group name (optional)
        role: Filter by VLAN role (optional)
        
    Returns:
        Dictionary containing:
        - count: Total number of VLANs found
        - vlans: List of summarized VLAN information
        - filters_applied: Dictionary of filters that were applied
        - summary_stats: Aggregate statistics about the VLANs
        
    Example:
        netbox_list_all_vlans(status="active", site_name="datacenter-1")
        netbox_list_all_vlans(tenant_name="customer-a", group_name="production")
        netbox_list_all_vlans(role="user", limit=50)
    """
    try:
        logger.info(f"Listing VLANs with filters - site: {site_name}, tenant: {tenant_name}, status: {status}, group: {group_name}")
        
        # Build filters dictionary - only include non-None values
        filters = {}
        if site_name:
            filters['site'] = site_name
        if tenant_name:
            filters['tenant'] = tenant_name
        if status:
            filters['status'] = status
        if group_name:
            filters['group'] = group_name
        if role:
            filters['role'] = role
        
        # Execute filtered query with limit
        vlans = list(client.ipam.vlans.filter(**filters))
        
        # Apply limit after fetching
        if len(vlans) > limit:
            vlans = vlans[:limit]
        
        # Generate summary statistics
        status_counts = {}
        site_counts = {}
        tenant_counts = {}
        group_counts = {}
        role_counts = {}
        
        # VLAN tracking
        vid_ranges = {"1-100": 0, "101-1000": 0, "1001-4000": 0, "4001-4094": 0}
        total_vlans = len(vlans)
        vlans_with_interfaces = 0
        
        for vlan in vlans:
            # Status breakdown with defensive dictionary access
            status_obj = vlan.get("status", {})
            if isinstance(status_obj, dict):
                status = status_obj.get("label", "N/A")
            else:
                status = str(status_obj) if status_obj else "N/A"
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Site breakdown with defensive dictionary access
            site_obj = vlan.get("site")
            if site_obj:
                if isinstance(site_obj, dict):
                    site_name = site_obj.get("name", str(site_obj))
                else:
                    site_name = str(site_obj)
                site_counts[site_name] = site_counts.get(site_name, 0) + 1
            
            # Tenant breakdown with defensive dictionary access
            tenant_obj = vlan.get("tenant")
            if tenant_obj:
                if isinstance(tenant_obj, dict):
                    tenant_name = tenant_obj.get("name", str(tenant_obj))
                else:
                    tenant_name = str(tenant_obj)
                tenant_counts[tenant_name] = tenant_counts.get(tenant_name, 0) + 1
            
            # Group breakdown with defensive dictionary access
            group_obj = vlan.get("group")
            if group_obj:
                if isinstance(group_obj, dict):
                    group_name = group_obj.get("name", str(group_obj))
                else:
                    group_name = str(group_obj)
                group_counts[group_name] = group_counts.get(group_name, 0) + 1
            
            # Role breakdown with defensive dictionary access
            role_obj = vlan.get("role")
            if role_obj:
                if isinstance(role_obj, dict):
                    role_name = role_obj.get("name", str(role_obj))
                else:
                    role_name = str(role_obj)
                role_counts[role_name] = role_counts.get(role_name, 0) + 1
            
            # VID range tracking with defensive dictionary access
            vid = vlan.get("vid", 0)
            if 1 <= vid <= 100:
                vid_ranges["1-100"] += 1
            elif 101 <= vid <= 1000:
                vid_ranges["101-1000"] += 1
            elif 1001 <= vid <= 4000:
                vid_ranges["1001-4000"] += 1
            elif 4001 <= vid <= 4094:
                vid_ranges["4001-4094"] += 1
            
            # Interface assignments (checking if VLAN has interfaces)
            try:
                vlan_id = vlan.get("id")
                vlan_interfaces = list(client.dcim.interfaces.filter(untagged_vlan_id=vlan_id))
                tagged_interfaces = list(client.dcim.interfaces.filter(tagged_vlans=vlan_id))
                if vlan_interfaces or tagged_interfaces:
                    vlans_with_interfaces += 1
            except:
                pass  # Skip interface counting if API call fails
        
        # Create human-readable VLAN list
        vlan_list = []
        for vlan in vlans:
            # Get interface assignments for this specific VLAN
            untagged_interfaces = []
            tagged_interfaces = []
            try:
                vlan_id = vlan.get("id")
                untagged_interfaces = list(client.dcim.interfaces.filter(untagged_vlan_id=vlan_id))
                tagged_interfaces = list(client.dcim.interfaces.filter(tagged_vlans=vlan_id))
            except:
                pass  # Skip if interface queries fail
            
            # Defensive dictionary access for status
            status_obj = vlan.get("status", {})
            if isinstance(status_obj, dict):
                status = status_obj.get("label", "N/A")
            else:
                status = str(status_obj) if status_obj else "N/A"
            
            # Defensive dictionary access for site
            site_obj = vlan.get("site")
            site_name = None
            if site_obj:
                if isinstance(site_obj, dict):
                    site_name = site_obj.get("name")
                else:
                    site_name = str(site_obj)
            
            # Defensive dictionary access for tenant
            tenant_obj = vlan.get("tenant")
            tenant_name = None
            if tenant_obj:
                if isinstance(tenant_obj, dict):
                    tenant_name = tenant_obj.get("name")
                else:
                    tenant_name = str(tenant_obj)
            
            # Defensive dictionary access for group
            group_obj = vlan.get("group")
            group_name = None
            if group_obj:
                if isinstance(group_obj, dict):
                    group_name = group_obj.get("name")
                else:
                    group_name = str(group_obj)
            
            # Defensive dictionary access for role
            role_obj = vlan.get("role")
            role_name = None
            if role_obj:
                if isinstance(role_obj, dict):
                    role_name = role_obj.get("name")
                else:
                    role_name = str(role_obj)
            
            vlan_info = {
                "name": vlan.get("name", "Unknown"),
                "vid": vlan.get("vid"),
                "status": status,
                "site": site_name,
                "tenant": tenant_name,
                "group": group_name,
                "role": role_name,
                "description": vlan.get("description"),
                "interface_assignments": {
                    "untagged_count": len(untagged_interfaces),
                    "tagged_count": len(tagged_interfaces),
                    "total_interfaces": len(untagged_interfaces) + len(tagged_interfaces)
                },
                "created": vlan.get("created"),
                "last_updated": vlan.get("last_updated")
            }
            vlan_list.append(vlan_info)
        
        result = {
            "count": len(vlan_list),
            "vlans": vlan_list,
            "filters_applied": {k: v for k, v in filters.items() if v is not None},
            "summary_stats": {
                "total_vlans": total_vlans,
                "status_breakdown": status_counts,
                "site_breakdown": site_counts,
                "tenant_breakdown": tenant_counts,
                "group_breakdown": group_counts,
                "role_breakdown": role_counts,
                "vid_range_distribution": vid_ranges,
                "vlans_with_interfaces": vlans_with_interfaces,
                "vlans_without_interfaces": total_vlans - vlans_with_interfaces,
                "vlans_with_sites": len([v for v in vlan_list if v['site']]),
                "vlans_with_tenants": len([v for v in vlan_list if v['tenant']]),
                "vlans_with_groups": len([v for v in vlan_list if v['group']]),
                "vlans_with_roles": len([v for v in vlan_list if v['role']])
            }
        }
        
        logger.info(f"Found {len(vlan_list)} VLANs matching criteria. Status breakdown: {status_counts}")
        return result
        
    except Exception as e:
        logger.error(f"Error listing VLANs: {e}")
        return {
            "count": 0,
            "vlans": [],
            "error": str(e),
            "error_type": type(e).__name__,
            "filters_applied": {k: v for k, v in {
                'site_name': site_name,
                'tenant_name': tenant_name,
                'status': status,
                'group_name': group_name,
                'role': role
            }.items() if v is not None}
        }