#!/usr/bin/env python3
"""
DCIM Device Role Management Tools

High-level tools for managing NetBox device roles with enterprise-grade functionality.
"""

from typing import Dict, Optional, Any
import logging
from ...registry import mcp_tool
from ...client import NetBoxClient

logger = logging.getLogger(__name__)


@mcp_tool(category="dcim")
def netbox_create_device_role(
    client: NetBoxClient,
    name: str,
    slug: str,
    color: str = "9e9e9e",
    vm_role: bool = False,
    description: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Create a new device role in NetBox DCIM.
    
    Args:
        client: NetBoxClient instance (injected)
        name: Role name
        slug: URL-friendly identifier
        color: Hex color code (without #)
        vm_role: Whether role applies to virtual machines
        description: Optional description
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Created device role information or error details
        
    Example:
        netbox_create_device_role("Router", "router", color="2196f3", confirm=True)
    """
    try:
        if not name or not slug:
            return {
                "success": False,
                "error": "Role name and slug are required",
                "error_type": "ValidationError"
            }
        
        # Validate color format
        if not color.startswith('#'):
            color = color.lstrip('#')
        if len(color) != 6:
            return {
                "success": False,
                "error": "Color must be a 6-character hex code",
                "error_type": "ValidationError"
            }
        
        logger.info(f"Creating device role: {name} (slug: {slug})")
        
        # Build device role data
        role_data = {
            "name": name,
            "slug": slug,
            "color": color,
            "vm_role": vm_role
        }
        
        if description:
            role_data["description"] = description
        
        # Use dynamic API with safety
        result = client.dcim.device_roles.create(confirm=confirm, **role_data)
        
        return {
            "success": True,
            "action": "created",
            "object_type": "device_role",
            "device_role": result,
            "dry_run": result.get("dry_run", False)
        }
        
    except Exception as e:
        logger.error(f"Failed to create device role {name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@mcp_tool(category="dcim")
def netbox_list_all_device_roles(
    client: NetBoxClient,
    limit: int = 100,
    vm_role: Optional[bool] = None
) -> Dict[str, Any]:
    """
    Get summarized list of device roles with usage statistics.
    
    This tool provides bulk device role discovery across the NetBox DCIM infrastructure,
    enabling efficient role-based device management, organizational planning, and
    infrastructure categorization. Essential for device lifecycle and role management.
    
    Args:
        client: NetBoxClient instance (injected by dependency system)
        limit: Maximum number of results to return (default: 100)
        vm_role: Filter by VM role capability (True/False/None for all)
        
    Returns:
        Dictionary containing:
        - count: Total number of device roles found
        - device_roles: List of summarized device role information
        - filters_applied: Dictionary of filters that were applied
        - summary_stats: Aggregate statistics about the device roles
        
    Example:
        netbox_list_all_device_roles()
        netbox_list_all_device_roles(vm_role=True)
        netbox_list_all_device_roles(limit=25)
    """
    try:
        logger.info(f"Listing device roles with filters - vm_role: {vm_role}")
        
        # Build filters dictionary - only include non-None values
        filters = {}
        if vm_role is not None:
            filters['vm_role'] = vm_role
        
        # Execute filtered query
        device_roles = list(client.dcim.device_roles.filter(**filters))
        
        # Apply limit after fetching
        if len(device_roles) > limit:
            device_roles = device_roles[:limit]
        
        # Generate summary statistics
        vm_role_counts = {"vm_capable": 0, "physical_only": 0}
        color_usage = {}
        total_devices = 0
        roles_with_devices = 0
        
        # Create human-readable device role list
        role_list = []
        for role in device_roles:
            # VM role tracking with defensive dictionary access
            is_vm_role = role.get("vm_role", False)
            if is_vm_role:
                vm_role_counts["vm_capable"] += 1
            else:
                vm_role_counts["physical_only"] += 1
            
            # Color tracking with defensive dictionary access
            role_color = role.get("color", "unknown")
            color_usage[role_color] = color_usage.get(role_color, 0) + 1
            
            # Get devices using this role
            role_id = role.get("id")
            devices_with_role = list(client.dcim.devices.filter(role_id=role_id))
            device_count = len(devices_with_role)
            total_devices += device_count
            if device_count > 0:
                roles_with_devices += 1
            
            # Get VMs using this role (if vm_role is True)
            vm_count = 0
            if is_vm_role:
                try:
                    vms_with_role = list(client.virtualization.virtual_machines.filter(role_id=role_id))
                    vm_count = len(vms_with_role)
                except:
                    vm_count = 0  # Skip if virtualization API fails
            
            role_info = {
                "name": role.get("name", "Unknown"),
                "slug": role.get("slug", ""),
                "color": role_color,
                "vm_role": is_vm_role,
                "description": role.get("description"),
                "device_count": device_count,
                "vm_count": vm_count,
                "total_resources": device_count + vm_count,
                "created": role.get("created"),
                "last_updated": role.get("last_updated")
            }
            role_list.append(role_info)
        
        # Sort by total resource count (most used roles first)
        role_list.sort(key=lambda r: r['total_resources'], reverse=True)
        
        result = {
            "count": len(role_list),
            "device_roles": role_list,
            "filters_applied": {k: v for k, v in filters.items() if v is not None},
            "summary_stats": {
                "total_roles": len(role_list),
                "vm_role_breakdown": vm_role_counts,
                "color_distribution": color_usage,
                "total_devices_assigned": total_devices,
                "total_vms_assigned": sum(r['vm_count'] for r in role_list),
                "roles_in_use": roles_with_devices,
                "roles_unused": len(role_list) - roles_with_devices,
                "average_devices_per_role": round(total_devices / len(role_list), 1) if role_list else 0,
                "most_used_roles": [r["name"] for r in role_list[:5] if r["total_resources"] > 0],
                "role_categories": {
                    "vm_capable_roles": len([r for r in role_list if r["vm_role"]]),
                    "physical_only_roles": len([r for r in role_list if not r["vm_role"]]),
                    "hybrid_roles": len([r for r in role_list if r["vm_role"] and r["device_count"] > 0 and r["vm_count"] > 0])
                }
            }
        }
        
        logger.info(f"Found {len(role_list)} device roles matching criteria. Total devices assigned: {total_devices}")
        return result
        
    except Exception as e:
        logger.error(f"Error listing device roles: {e}")
        return {
            "count": 0,
            "device_roles": [],
            "error": str(e),
            "error_type": type(e).__name__,
            "filters_applied": {k: v for k, v in {
                'vm_role': vm_role
            }.items() if v is not None}
        }


# TODO: Implement advanced device role management tools:
# - netbox_get_device_role_usage
# - netbox_update_device_role_properties
# - netbox_get_role_based_device_inventory
# - netbox_migrate_devices_between_roles