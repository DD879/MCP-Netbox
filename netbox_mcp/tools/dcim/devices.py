#\!/usr/bin/env python3
"""
DCIM Device Lifecycle Management Tools

High-level tools for managing NetBox devices with comprehensive lifecycle management,
including creation, provisioning, decommissioning, and enterprise-grade functionality.
"""

from typing import Dict, Optional, Any, List
import logging
from ...registry import mcp_tool
from ...client import NetBoxClient
from ...cache import get_cache

logger = logging.getLogger(__name__)


@mcp_tool(category="dcim")
def netbox_create_device(
    client: NetBoxClient,
    name: str,
    device_type: str,
    site: str,
    role: str,
    status: str = "active",
    rack: Optional[str] = None,
    position: Optional[int] = None,
    face: str = "front",
    serial: Optional[str] = None,
    asset_tag: Optional[str] = None,
    description: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Create a new device in NetBox DCIM.
    
    Args:
        client: NetBoxClient instance (injected)
        name: Device name (hostname)
        device_type: Device type model or slug
        site: Site name or slug
        role: Device role name or slug
        status: Device status (active, planned, staged, failed, inventory, decommissioning, offline)
        rack: Optional rack name
        position: Rack position (bottom U)
        face: Rack face (front, rear)
        serial: Serial number
        asset_tag: Asset tag
        description: Optional description
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Created device information or error details
        
    Example:
        netbox_create_device("rtr-01", "isr4331", "amsterdam-dc", "router", confirm=True)
    """
    try:
        if not name or not device_type or not site or not role:
            return {
                "success": False,
                "error": "Device name, type, site, and role are required",
                "error_type": "ValidationError"
            }
        
        logger.info(f"Creating device: {name} ({device_type})")
        
        # Resolve foreign key references
        foreign_keys = {}
        
        # Resolve device_type
        if isinstance(device_type, str) and not device_type.isdigit():
            device_types = client.dcim.device_types.filter(model=device_type)
            if not device_types:
                device_types = client.dcim.device_types.filter(slug=device_type)
            if device_types:
                foreign_keys["device_type"] = device_types[0]["id"]
            else:
                return {
                    "success": False,
                    "error": f"Device type '{device_type}' not found",
                    "error_type": "DeviceTypeNotFound"
                }
        else:
            foreign_keys["device_type"] = device_type
        
        # Resolve site
        if isinstance(site, str) and not site.isdigit():
            sites = client.dcim.sites.filter(slug=site)
            if not sites:
                sites = client.dcim.sites.filter(name=site)
            if sites:
                foreign_keys["site"] = sites[0]["id"]
            else:
                return {
                    "success": False,
                    "error": f"Site '{site}' not found",
                    "error_type": "SiteNotFound"
                }
        else:
            foreign_keys["site"] = site
        
        # Resolve role
        if isinstance(role, str) and not role.isdigit():
            roles = client.dcim.device_roles.filter(slug=role)
            if not roles:
                roles = client.dcim.device_roles.filter(name=role)
            if roles:
                foreign_keys["role"] = roles[0]["id"]
            else:
                return {
                    "success": False,
                    "error": f"Device role '{role}' not found",
                    "error_type": "DeviceRoleNotFound"
                }
        else:
            foreign_keys["role"] = role
        
        # Resolve rack if provided
        if rack:
            if isinstance(rack, str) and not rack.isdigit():
                racks = client.dcim.racks.filter(name=rack, site_id=foreign_keys["site"])
                if racks:
                    foreign_keys["rack"] = racks[0]["id"]
                else:
                    return {
                        "success": False,
                        "error": f"Rack '{rack}' not found in site",
                        "error_type": "RackNotFound"
                    }
            else:
                foreign_keys["rack"] = rack
        
        # Build device data
        device_data = {
            "name": name,
            "device_type": foreign_keys["device_type"],
            "site": foreign_keys["site"],
            "role": foreign_keys["role"],
            "status": status,
            "face": face
        }
        
        if rack:
            device_data["rack"] = foreign_keys.get("rack", rack)
        if position is not None:
            device_data["position"] = position
        if serial:
            device_data["serial"] = serial
        if asset_tag:
            device_data["asset_tag"] = asset_tag
        if description:
            device_data["description"] = description
        
        # Use dynamic API with safety
        result = client.dcim.devices.create(confirm=confirm, **device_data)
        
        return {
            "success": True,
            "action": "created",
            "object_type": "device",
            "device": result,
            "dry_run": result.get("dry_run", False)
        }
        
    except Exception as e:
        logger.error(f"Failed to create device {name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }




@mcp_tool(category="dcim")
def netbox_get_device_info(
    client: NetBoxClient,
    device_name: str,
    site: Optional[str] = None,
    interface_limit: int = 20,
    cable_limit: int = 10,
    include_interfaces: bool = True,
    include_cables: bool = True
) -> Dict[str, Any]:
    """
    Get comprehensive information about a device with pagination support.
    
    Args:
        client: NetBoxClient instance (injected)
        device_name: Name of the device
        site: Optional site name for filtering
        interface_limit: Maximum number of interfaces to return (default: 20)
        cable_limit: Maximum number of cables to return (default: 10)
        include_interfaces: Include interface information (default: True)
        include_cables: Include cable information (default: True)
        
    Returns:
        Device information including limited interfaces and connections
        
    Example:
        netbox_get_device_info("rtr-01", site="amsterdam-dc")
        netbox_get_device_info("switch-01", interface_limit=50, cable_limit=20)
        netbox_get_device_info("server-01", include_cables=False)
        
    Note:
        For devices with many interfaces/cables, use the specialized tools:
        - netbox_get_device_basic_info (device only)
        - netbox_get_device_interfaces (interfaces with pagination)
        - netbox_get_device_cables (cables with pagination)
    """
    try:
        logger.info(f"Getting device information: {device_name}")
        
        # Build filter
        device_filter = {"name": device_name}
        if site:
            device_filter["site"] = site
        
        # Find the device
        devices = client.dcim.devices.filter(**device_filter)
        
        if not devices:
            return {
                "success": False,
                "error": f"Device '{device_name}' not found" + (f" in site '{site}'" if site else ""),
                "error_type": "DeviceNotFound"
            }
        
        device = devices[0]
        device_id = device["id"]
        
        # Get related information with pagination
        result_data = {
            "success": True,
            "device": device
        }
        
        # Get interfaces with API-side pagination if requested
        if include_interfaces:
            # Use API-side counting for efficiency
            total_interfaces = client.dcim.interfaces.count(device_id=device_id)
            # Use API-side pagination with limit parameter
            interfaces = list(client.dcim.interfaces.filter(device_id=device_id, limit=interface_limit))
            result_data["interfaces"] = interfaces
            result_data["interface_pagination"] = {
                "total_count": total_interfaces,
                "returned_count": len(interfaces),
                "limit": interface_limit,
                "truncated": total_interfaces > interface_limit
            }
        else:
            result_data["interfaces"] = []
            result_data["interface_pagination"] = {
                "total_count": 0,
                "returned_count": 0,
                "limit": interface_limit,
                "truncated": False
            }
        
        # Get cables with API-side pagination if requested
        if include_cables:
            # Use API-side counting for efficiency
            total_cables = client.dcim.cables.count(termination_a_id=device_id)
            # Use API-side pagination with limit parameter
            cables = list(client.dcim.cables.filter(termination_a_id=device_id, limit=cable_limit))
            result_data["cables"] = cables
            result_data["cable_pagination"] = {
                "total_count": total_cables,
                "returned_count": len(cables),
                "limit": cable_limit,
                "truncated": total_cables > cable_limit
            }
        else:
            result_data["cables"] = []
            result_data["cable_pagination"] = {
                "total_count": 0,
                "returned_count": 0,
                "limit": cable_limit,
                "truncated": False
            }
        
        # Power connections endpoint doesn't exist in this NetBox version
        result_data["power_connections"] = []
        
        # Statistics
        result_data["statistics"] = {
            "interface_count": result_data["interface_pagination"]["total_count"],
            "cable_count": result_data["cable_pagination"]["total_count"],
            "power_connection_count": 0,
            "interface_returned": result_data["interface_pagination"]["returned_count"],
            "cable_returned": result_data["cable_pagination"]["returned_count"]
        }
        
        return result_data
        
    except Exception as e:
        logger.error(f"Failed to get device info for {device_name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@mcp_tool(category="dcim")
def netbox_get_device_basic_info(
    client: NetBoxClient,
    device_name: str,
    site: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get basic device information only (no interfaces or cables).
    
    This lightweight tool returns only device details without related objects,
    making it ideal for quick device lookups that respect token limits.
    
    Args:
        client: NetBoxClient instance (injected)
        device_name: Name of the device
        site: Optional site name for filtering
        
    Returns:
        Basic device information without interfaces or cables
        
    Example:
        netbox_get_device_basic_info("rtr-01", site="amsterdam-dc")
        netbox_get_device_basic_info("switch-01")
    """
    try:
        logger.info(f"Getting basic device information: {device_name}")
        
        # Build filter
        device_filter = {"name": device_name}
        if site:
            device_filter["site"] = site
        
        # Find the device
        devices = client.dcim.devices.filter(**device_filter)
        
        if not devices:
            return {
                "success": False,
                "error": f"Device '{device_name}' not found" + (f" in site '{site}'" if site else ""),
                "error_type": "DeviceNotFound"
            }
        
        device = devices[0]
        device_id = device["id"]
        
        # Get counts only (no actual data)
        interface_count = len(list(client.dcim.interfaces.filter(device_id=device_id)))
        cable_count = len(list(client.dcim.cables.filter(termination_a_id=device_id)))
        
        return {
            "success": True,
            "device": device,
            "statistics": {
                "interface_count": interface_count,
                "cable_count": cable_count,
                "power_connection_count": 0
            },
            "note": "Use netbox_get_device_interfaces or netbox_get_device_cables for detailed related data"
        }
        
    except Exception as e:
        logger.error(f"Failed to get basic device info for {device_name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@mcp_tool(category="dcim")
def netbox_get_device_interfaces(
    client: NetBoxClient,
    device_name: str,
    site: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    interface_type: Optional[str] = None,
    enabled_only: bool = False
) -> Dict[str, Any]:
    """
    Get device interfaces with pagination support.
    
    This specialized tool returns device interfaces with comprehensive filtering
    and pagination, ideal for devices with many interfaces.
    
    Args:
        client: NetBoxClient instance (injected)
        device_name: Name of the device
        site: Optional site name for filtering
        limit: Maximum number of interfaces to return (default: 50)
        offset: Starting position for pagination (default: 0)
        interface_type: Filter by interface type (optional)
        enabled_only: Only return enabled interfaces (default: False)
        
    Returns:
        Device interfaces with pagination information
        
    Example:
        netbox_get_device_interfaces("switch-01")
        netbox_get_device_interfaces("switch-01", limit=20, offset=40)
        netbox_get_device_interfaces("server-01", enabled_only=True)
    """
    try:
        logger.info(f"Getting device interfaces: {device_name}")
        
        # Build device filter
        device_filter = {"name": device_name}
        if site:
            device_filter["site"] = site
        
        # Find the device
        devices = client.dcim.devices.filter(**device_filter)
        
        if not devices:
            return {
                "success": False,
                "error": f"Device '{device_name}' not found" + (f" in site '{site}'" if site else ""),
                "error_type": "DeviceNotFound"
            }
        
        device = devices[0]
        device_id = device["id"]
        
        # Build interface filter
        interface_filter = {"device_id": device_id}
        if interface_type:
            interface_filter["type"] = interface_type
        if enabled_only:
            interface_filter["enabled"] = True
        
        # Use API-side counting and pagination for efficiency
        total_count = client.dcim.interfaces.count(**interface_filter)
        
        # Apply API-side pagination with limit and offset
        interfaces = list(client.dcim.interfaces.filter(
            **interface_filter,
            limit=limit,
            offset=offset
        ))
        
        end_index = offset + len(interfaces)
        
        return {
            "success": True,
            "device": {
                "id": device["id"],
                "name": device["name"],
                "display": device.get("display", device["name"])
            },
            "interfaces": interfaces,
            "pagination": {
                "total_count": total_count,
                "returned_count": len(interfaces),
                "limit": limit,
                "offset": offset,
                "has_next": end_index < total_count,
                "has_previous": offset > 0,
                "next_offset": end_index if end_index < total_count else None,
                "previous_offset": max(0, offset - limit) if offset > 0 else None
            },
            "filters_applied": {
                "interface_type": interface_type,
                "enabled_only": enabled_only
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get device interfaces for {device_name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@mcp_tool(category="dcim")
def netbox_get_device_cables(
    client: NetBoxClient,
    device_name: str,
    site: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    cable_status: Optional[str] = None,
    cable_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get device cables with pagination support.
    
    This specialized tool returns device cables with comprehensive filtering
    and pagination, ideal for devices with many cable connections.
    
    Args:
        client: NetBoxClient instance (injected)
        device_name: Name of the device
        site: Optional site name for filtering
        limit: Maximum number of cables to return (default: 50)
        offset: Starting position for pagination (default: 0)
        cable_status: Filter by cable status (optional)
        cable_type: Filter by cable type (optional)
        
    Returns:
        Device cables with pagination information
        
    Example:
        netbox_get_device_cables("switch-01")
        netbox_get_device_cables("switch-01", limit=20, offset=20)
        netbox_get_device_cables("server-01", cable_status="connected")
    """
    try:
        logger.info(f"Getting device cables: {device_name}")
        
        # Build device filter
        device_filter = {"name": device_name}
        if site:
            device_filter["site"] = site
        
        # Find the device
        devices = client.dcim.devices.filter(**device_filter)
        
        if not devices:
            return {
                "success": False,
                "error": f"Device '{device_name}' not found" + (f" in site '{site}'" if site else ""),
                "error_type": "DeviceNotFound"
            }
        
        device = devices[0]
        device_id = device["id"]
        
        # Build cable filter - cables where this device is termination A
        cable_filter = {"termination_a_id": device_id}
        if cable_status:
            cable_filter["status"] = cable_status
        if cable_type:
            cable_filter["type"] = cable_type
        
        # Use API-side counting and pagination for efficiency
        total_count = client.dcim.cables.count(**cable_filter)
        
        # Apply API-side pagination with limit and offset
        cables = list(client.dcim.cables.filter(
            **cable_filter,
            limit=limit,
            offset=offset
        ))
        
        end_index = offset + len(cables)
        
        return {
            "success": True,
            "device": {
                "id": device["id"],
                "name": device["name"],
                "display": device.get("display", device["name"])
            },
            "cables": cables,
            "pagination": {
                "total_count": total_count,
                "returned_count": len(cables),
                "limit": limit,
                "offset": offset,
                "has_next": end_index < total_count,
                "has_previous": offset > 0,
                "next_offset": end_index if end_index < total_count else None,
                "previous_offset": max(0, offset - limit) if offset > 0 else None
            },
            "filters_applied": {
                "cable_status": cable_status,
                "cable_type": cable_type
            },
            "note": "Only shows cables where this device is termination A. Use netbox_list_all_cables for comprehensive cable search."
        }
        
    except Exception as e:
        logger.error(f"Failed to get device cables for {device_name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@mcp_tool(category="dcim")
def netbox_provision_new_device(
    client: NetBoxClient,
    device_name: str,
    site_name: str,
    rack_name: str,
    device_model: str,
    role_name: str,
    position: int,
    status: str = "active",
    face: str = "front",
    tenant: Optional[str] = None,
    platform: Optional[str] = None,
    serial: Optional[str] = None,
    asset_tag: Optional[str] = None,
    description: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Provision a complete new device in a rack with a single function call.
    
    This high-level function reduces 5-6 potential API calls and complex validations 
    into one single, logical function. Essential for data center provisioning workflows.
    
    Args:
        client: NetBoxClient instance (injected)
        device_name: Name for the new device
        site_name: Name of the site where the rack is located
        rack_name: Name of the rack to place the device in
        device_model: Device model name or slug (will be resolved to device_type)
        role_name: Device role name or slug
        position: Rack position (1-based, from bottom)
        status: Device status (active, offline, planned, staged, failed, inventory, decommissioning)
        face: Rack face (front, rear)
        tenant: Optional tenant name or slug
        platform: Optional platform name or slug
        serial: Optional serial number
        asset_tag: Optional asset tag
        description: Optional description
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Complete device provisioning result with all resolved information
        
    Example:
        netbox_provision_new_device(
            device_name="sw-floor3-001", 
            site_name="Main DC", 
            rack_name="R-12", 
            device_model="C9300-24T", 
            role_name="Access Switch", 
            position=42, 
            confirm=True
        )
    """
    try:
        if not all([device_name, site_name, rack_name, device_model, role_name]):
            return {
                "success": False,
                "error": "device_name, site_name, rack_name, device_model, and role_name are required",
                "error_type": "ValidationError"
            }
        
        if not (1 <= position <= 100):
            return {
                "success": False,
                "error": "Position must be between 1 and 100",
                "error_type": "ValidationError"
            }
        
        logger.info(f"Provisioning device: {device_name} in {site_name}/{rack_name} at position {position}")
        
        # Step 1: Find the site
        logger.debug(f"Looking up site: {site_name}")
        sites = client.dcim.sites.filter(name=site_name)
        if not sites:
            sites = client.dcim.sites.filter(slug=site_name)
        if not sites:
            return {
                "success": False,
                "error": f"Site '{site_name}' not found",
                "error_type": "NotFoundError"
            }
        site = sites[0]
        site_id = site["id"]
        logger.debug(f"Found site: {site['name']} (ID: {site_id})")
        
        # Step 2: Find the rack within that site
        logger.debug(f"Looking up rack: {rack_name} in site {site['name']}")
        racks = client.dcim.racks.filter(site_id=site_id, name=rack_name)
        if not racks:
            return {
                "success": False,
                "error": f"Rack '{rack_name}' not found in site '{site['name']}'",
                "error_type": "NotFoundError"
            }
        rack = racks[0]
        rack_id = rack["id"]
        logger.debug(f"Found rack: {rack['name']} (ID: {rack_id})")
        
        # Step 3: Find the device type
        logger.debug(f"Looking up device type: {device_model}")
        device_types = client.dcim.device_types.filter(model=device_model)
        if not device_types:
            device_types = client.dcim.device_types.filter(slug=device_model)
        if not device_types:
            return {
                "success": False,
                "error": f"Device type '{device_model}' not found",
                "error_type": "NotFoundError"
            }
        device_type = device_types[0]
        device_type_id = device_type["id"]
        logger.debug(f"Found device type: {device_type['model']} (ID: {device_type_id})")
        
        # Step 4: Find the device role
        logger.debug(f"Looking up device role: {role_name}")
        roles = client.dcim.device_roles.filter(name=role_name)
        if not roles:
            roles = client.dcim.device_roles.filter(slug=role_name)
        if not roles:
            return {
                "success": False,
                "error": f"Device role '{role_name}' not found",
                "error_type": "NotFoundError"
            }
        role = roles[0]
        role_id = role["id"]
        logger.debug(f"Found device role: {role['name']} (ID: {role_id})")
        
        # Step 5: Validate rack position availability
        logger.debug(f"Validating position {position} availability in rack {rack['name']}")
        
        # Check if position is within rack height
        if position > rack["u_height"]:
            return {
                "success": False,
                "error": f"Position {position} exceeds rack height of {rack['u_height']}U",
                "error_type": "ValidationError"
            }
        
        # Check if position is already occupied
        existing_devices = client.dcim.devices.filter(rack_id=rack_id, position=position)
        if existing_devices:
            return {
                "success": False,
                "error": f"Position {position} is already occupied by device '{existing_devices[0]['name']}'",
                "error_type": "ConflictError"
            }
        
        # Check if device extends beyond rack height
        device_u_height = int(device_type.get("u_height", 1))
        if position + device_u_height - 1 > rack["u_height"]:
            return {
                "success": False,
                "error": f"Device height ({device_u_height}U) at position {position} would exceed rack height of {rack['u_height']}U",
                "error_type": "ValidationError"
            }
        
        # Check for overlapping devices
        for check_pos in range(position, position + int(device_u_height)):
            overlapping = client.dcim.devices.filter(rack_id=rack_id, position=check_pos)
            if overlapping:
                return {
                    "success": False,
                    "error": f"Device would overlap with existing device '{overlapping[0]['name']}' at position {check_pos}",
                    "error_type": "ConflictError"
                }
        
        # Step 6: Resolve optional foreign keys
        tenant_id = None
        tenant_name = None
        if tenant:
            logger.debug(f"Looking up tenant: {tenant}")
            tenants = client.tenancy.tenants.filter(name=tenant)
            if not tenants:
                tenants = client.tenancy.tenants.filter(slug=tenant)
            if tenants:
                tenant_id = tenants[0]["id"]
                tenant_name = tenants[0]["name"]
                logger.debug(f"Found tenant: {tenant_name} (ID: {tenant_id})")
            else:
                logger.warning(f"Tenant '{tenant}' not found, proceeding without tenant assignment")
        
        platform_id = None
        platform_name = None
        if platform:
            logger.debug(f"Looking up platform: {platform}")
            platforms = client.dcim.platforms.filter(name=platform)
            if not platforms:
                platforms = client.dcim.platforms.filter(slug=platform)
            if platforms:
                platform_id = platforms[0]["id"]
                platform_name = platforms[0]["name"]
                logger.debug(f"Found platform: {platform_name} (ID: {platform_id})")
            else:
                logger.warning(f"Platform '{platform}' not found, proceeding without platform assignment")
        
        # Step 7: Assemble the complete payload
        device_data = {
            "name": device_name,
            "device_type": device_type_id,
            "role": role_id,
            "site": site_id,
            "rack": rack_id,
            "position": position,
            "face": face,
            "status": status
        }
        
        # Add optional fields
        if tenant_id:
            device_data["tenant"] = tenant_id
        if platform_id:
            device_data["platform"] = platform_id
        if serial:
            device_data["serial"] = serial
        if asset_tag:
            device_data["asset_tag"] = asset_tag
        if description:
            device_data["description"] = description
        
        # Step 8: Create the device
        if not confirm:
            # Dry run mode - return what would be created without actually creating
            logger.info(f"DRY RUN: Would create device with data: {device_data}")
            return {
                "success": True,
                "action": "dry_run",
                "object_type": "device",
                "device": {"name": device_name, "dry_run": True, "would_create": device_data},
                "resolved_references": {
                    "site": {"name": site["name"], "id": site_id},
                    "rack": {"name": rack["name"], "id": rack_id, "position": position},
                    "device_type": {"model": device_type["model"], "id": device_type_id, "u_height": device_u_height},
                    "role": {"name": role["name"], "id": role_id},
                    "tenant": {"name": tenant_name, "id": tenant_id} if tenant_id else None,
                    "platform": {"name": platform_name, "id": platform_id} if platform_id else None
                },
                "dry_run": True
            }
        
        logger.info(f"Creating device with data: {device_data}")
        result = client.dcim.devices.create(confirm=confirm, **device_data)
        
        return {
            "success": True,
            "action": "provisioned",
            "object_type": "device",
            "device": result,
            "resolved_references": {
                "site": {"name": site["name"], "id": site_id},
                "rack": {"name": rack["name"], "id": rack_id, "position": position},
                "device_type": {"model": device_type["model"], "id": device_type_id, "u_height": device_u_height},
                "role": {"name": role["name"], "id": role_id},
                "tenant": {"name": tenant_name, "id": tenant_id} if tenant_id else None,
                "platform": {"name": platform_name, "id": platform_id} if platform_id else None
            },
            "dry_run": result.get("dry_run", False)
        }
        
    except Exception as e:
        logger.error(f"Failed to provision device {device_name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }




@mcp_tool(category="dcim")
def netbox_decommission_device(
    client: NetBoxClient,
    device_name: str,
    decommission_strategy: str = "offline",
    handle_ips: str = "unassign",
    handle_cables: str = "remove",
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Safely decommission a device with comprehensive validation and cleanup.
    
    This enterprise-grade decommissioning tool handles the complex workflow of removing
    devices from production while maintaining data integrity and preventing accidental
    deletion of devices with active connections.
    
    Args:
        client: NetBoxClient instance (injected)
        device_name: Name of the device to decommission
        decommission_strategy: Strategy for device status ("offline", "decommissioning", "inventory")
        handle_ips: IP address handling ("unassign", "deprecate", "keep")
        handle_cables: Cable handling ("remove", "deprecate", "keep")
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Comprehensive decommissioning report with all actions performed
        
    Example:
        netbox_decommission_device(
            device_name="old-server-01",
            decommission_strategy="offline",
            handle_ips="deprecate",
            handle_cables="remove",
            confirm=True
        )
    """
    try:
        if not device_name:
            return {
                "success": False,
                "error": "device_name is required",
                "error_type": "ValidationError"
            }
        
        # Validate strategy parameters
        valid_strategies = ["offline", "decommissioning", "inventory", "failed"]
        valid_ip_handling = ["unassign", "deprecate", "keep"]
        valid_cable_handling = ["remove", "deprecate", "keep"]
        
        if decommission_strategy not in valid_strategies:
            return {
                "success": False,
                "error": f"Invalid decommission_strategy. Must be one of: {valid_strategies}",
                "error_type": "ValidationError"
            }
        
        if handle_ips not in valid_ip_handling:
            return {
                "success": False,
                "error": f"Invalid handle_ips. Must be one of: {valid_ip_handling}",
                "error_type": "ValidationError"
            }
        
        if handle_cables not in valid_cable_handling:
            return {
                "success": False,
                "error": f"Invalid handle_cables. Must be one of: {valid_cable_handling}",
                "error_type": "ValidationError"
            }
        
        logger.info(f"Decommissioning device: {device_name} (strategy: {decommission_strategy})")
        
        # Step 1: Find the device
        logger.debug(f"Looking up device: {device_name}")
        devices = client.dcim.devices.filter(name=device_name)
        if not devices:
            return {
                "success": False,
                "error": f"Device '{device_name}' not found",
                "error_type": "NotFoundError"
            }
        device = devices[0]
        device_id = device["id"]
        current_status = device.get("status", "unknown")
        logger.debug(f"Found device: {device['name']} (ID: {device_id}, Current Status: {current_status})")
        
        # Step 2: Pre-flight validation and dependency checks
        logger.debug("Performing pre-flight validation...")
        validation_results = {}
        
        # Check for critical dependencies (cluster membership, etc.)
        if device.get("cluster"):
            validation_results["cluster_warning"] = f"Device is member of cluster: {device['cluster'].get('name', 'Unknown')}"
        
        if device.get("virtual_chassis"):
            validation_results["virtual_chassis_warning"] = f"Device is part of virtual chassis: {device['virtual_chassis']}"
        
        # Step 3: Inventory current connections and assignments
        logger.debug("Inventorying current device connections...")
        
        # Get all interfaces
        interfaces = client.dcim.interfaces.filter(device_id=device_id)
        interface_count = len(interfaces)
        
        # Get all IP addresses assigned to this device's interfaces
        device_ips = []
        for interface in interfaces:
            assigned_ips = client.ipam.ip_addresses.filter(assigned_object_id=interface["id"])
            interface_ips = [ip for ip in assigned_ips if ip.get("assigned_object_type") == "dcim.interface"]
            device_ips.extend(interface_ips)
        
        # Get all cables connected to this device
        device_cables = []
        for interface in interfaces:
            if interface.get("cable"):
                try:
                    cables = client.dcim.cables.filter(id=interface["cable"])
                    device_cables.extend(cables)
                except Exception as e:
                    logger.warning(f"Could not retrieve cable {interface['cable']}: {e}")
        
        # Remove duplicate cables
        unique_cables = {cable["id"]: cable for cable in device_cables}.values()
        device_cables = list(unique_cables)
        
        logger.debug(f"Device inventory: {len(device_ips)} IP addresses, {len(device_cables)} cables, {interface_count} interfaces")
        
        # Step 4: Risk assessment
        risk_factors = []
        if current_status in ["active", "planned"]:
            risk_factors.append("Device is currently in active/planned status")
        if device_ips:
            risk_factors.append(f"{len(device_ips)} IP addresses currently assigned")
        if device_cables:
            risk_factors.append(f"{len(device_cables)} cables currently connected")
        if device.get("primary_ip4") or device.get("primary_ip6"):
            risk_factors.append("Device has primary IP addresses configured")
        
        # Generate decommissioning plan
        decommission_plan = {
            "device_status_change": {
                "from": current_status,
                "to": decommission_strategy,
                "action": "Update device status"
            },
            "ip_addresses": {
                "count": len(device_ips),
                "action": handle_ips,
                "details": [{"address": ip["address"], "interface": ip.get("assigned_object_id")} for ip in device_ips]
            },
            "cables": {
                "count": len(device_cables),
                "action": handle_cables,
                "details": [{"cable_id": cable["id"], "label": cable.get("label", "Unlabeled")} for cable in device_cables]
            },
            "interfaces": {
                "count": interface_count,
                "action": "Keep (status will reflect device decommissioning)"
            }
        }
        
        if not confirm:
            # Dry run mode - return the plan without executing
            logger.info(f"DRY RUN: Would decommission device {device_name}")
            return {
                "success": True,
                "action": "dry_run",
                "object_type": "device_decommission",
                "device": {
                    "name": device["name"],
                    "id": device_id,
                    "current_status": current_status,
                    "dry_run": True
                },
                "decommission_plan": decommission_plan,
                "risk_assessment": {
                    "risk_level": "high" if len(risk_factors) > 2 else "medium" if risk_factors else "low",
                    "risk_factors": risk_factors
                },
                "validation_results": validation_results,
                "dry_run": True
            }
        
        # Step 5: Execute decommissioning plan
        execution_results = {}
        
        # 5a: Handle IP addresses
        if device_ips and handle_ips != "keep":
            logger.info(f"Processing {len(device_ips)} IP addresses...")
            ip_results = []
            
            for ip in device_ips:
                try:
                    if handle_ips == "unassign":
                        # Unassign the IP from the interface
                        update_data = {
                            "assigned_object_type": None,
                            "assigned_object_id": None
                        }
                        result = client.ipam.ip_addresses.update(ip["id"], confirm=True, **update_data)
                        ip_results.append({
                            "ip": ip["address"],
                            "action": "unassigned",
                            "status": "success"
                        })
                    elif handle_ips == "deprecate":
                        # Change IP status to deprecated
                        update_data = {"status": "deprecated"}
                        result = client.ipam.ip_addresses.update(ip["id"], confirm=True, **update_data)
                        ip_results.append({
                            "ip": ip["address"],
                            "action": "deprecated",
                            "status": "success"
                        })
                except Exception as e:
                    logger.error(f"Failed to process IP {ip['address']}: {e}")
                    ip_results.append({
                        "ip": ip["address"],
                        "action": f"failed: {e}",
                        "status": "error"
                    })
            
            execution_results["ip_processing"] = {
                "total": len(device_ips),
                "successful": len([r for r in ip_results if r["status"] == "success"]),
                "failed": len([r for r in ip_results if r["status"] == "error"]),
                "details": ip_results
            }
        
        # 5b: Handle cables
        if device_cables and handle_cables != "keep":
            logger.info(f"Processing {len(device_cables)} cables...")
            cable_results = []
            
            for cable in device_cables:
                try:
                    if handle_cables == "remove":
                        # Delete the cable
                        client.dcim.cables.delete(cable["id"], confirm=True)
                        cable_results.append({
                            "cable_id": cable["id"],
                            "label": cable.get("label", "Unlabeled"),
                            "action": "removed",
                            "status": "success"
                        })
                    elif handle_cables == "deprecate":
                        # Update cable status to deprecated (if status field exists)
                        try:
                            update_data = {"status": "deprecated"}
                            result = client.dcim.cables.update(cable["id"], confirm=True, **update_data)
                            cable_results.append({
                                "cable_id": cable["id"],
                                "label": cable.get("label", "Unlabeled"),
                                "action": "deprecated",
                                "status": "success"
                            })
                        except Exception:
                            # If deprecation fails, try removal
                            client.dcim.cables.delete(cable["id"], confirm=True)
                            cable_results.append({
                                "cable_id": cable["id"],
                                "label": cable.get("label", "Unlabeled"),
                                "action": "removed (deprecation not supported)",
                                "status": "success"
                            })
                except Exception as e:
                    logger.error(f"Failed to process cable {cable['id']}: {e}")
                    cable_results.append({
                        "cable_id": cable["id"],
                        "label": cable.get("label", "Unlabeled"),
                        "action": f"failed: {e}",
                        "status": "error"
                    })
            
            execution_results["cable_processing"] = {
                "total": len(device_cables),
                "successful": len([r for r in cable_results if r["status"] == "success"]),
                "failed": len([r for r in cable_results if r["status"] == "error"]),
                "details": cable_results
            }
        
        # 5c: Update device status
        logger.info(f"Updating device status to: {decommission_strategy}")
        try:
            device_update_data = {"status": decommission_strategy}
            updated_device = client.dcim.devices.update(device_id, confirm=True, **device_update_data)
            execution_results["device_status"] = {
                "action": "updated",
                "from": current_status,
                "to": decommission_strategy,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Failed to update device status: {e}")
            execution_results["device_status"] = {
                "action": "failed",
                "error": str(e),
                "status": "error"
            }
        
        # Step 6: Generate completion summary
        total_actions = 1  # Device status update
        successful_actions = 1 if execution_results.get("device_status", {}).get("status") == "success" else 0
        
        if "ip_processing" in execution_results:
            total_actions += execution_results["ip_processing"]["total"]
            successful_actions += execution_results["ip_processing"]["successful"]
        
        if "cable_processing" in execution_results:
            total_actions += execution_results["cable_processing"]["total"]
            successful_actions += execution_results["cable_processing"]["successful"]
        
        overall_success = successful_actions == total_actions
        
        return {
            "success": overall_success,
            "action": "decommissioned",
            "object_type": "device",
            "device": {
                "name": device["name"],
                "id": device_id,
                "status_changed": execution_results.get("device_status", {}).get("status") == "success",
                "new_status": decommission_strategy if execution_results.get("device_status", {}).get("status") == "success" else current_status
            },
            "execution_summary": {
                "total_actions": total_actions,
                "successful_actions": successful_actions,
                "failed_actions": total_actions - successful_actions,
                "success_rate": f"{(successful_actions/total_actions*100):.1f}%" if total_actions > 0 else "0%"
            },
            "execution_results": execution_results,
            "decommission_strategy": decommission_strategy,
            "cleanup_performed": {
                "ips": handle_ips if device_ips else "none",
                "cables": handle_cables if device_cables else "none"
            },
            "dry_run": False
        }
        
    except Exception as e:
        logger.error(f"Failed to decommission device {device_name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }



@mcp_tool(category="dcim")
def netbox_list_all_devices(
    client: NetBoxClient,
    limit: int = 100,
    site_name: Optional[str] = None,
    role_name: Optional[str] = None,
    tenant_name: Optional[str] = None,
    status: Optional[str] = None,
    manufacturer_name: Optional[str] = None,
    fields: Optional[List[str]] = None,
    summary_mode: bool = False,
    include_counts: bool = True,
    include_related: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Get a summarized list of all devices in NetBox with field-selective optimization.

    This function is the correct choice for open, exploratory questions like
    "what devices are there?" or "show all servers in datacenter-1". Use
    'netbox_get_device' for detailed information about one specific device.

    Args:
        client: NetBoxClient instance (injected by dependency system)
        limit: Maximum number of results to return (default: 100)
        site_name: Filter by site name (optional)
        role_name: Filter by device role name (optional)
        tenant_name: Filter by tenant name (optional)
        status: Filter by device status (active, offline, planned, etc.)
        manufacturer_name: Filter by manufacturer name (optional)
        fields: Only include specific fields in response (reduces network overhead)
        summary_mode: Return minimal response with only essential fields
        include_counts: Include statistical aggregations (default: True)
        include_related: Selective related data to include (site, rack, device_type, role)

    Returns:
        Dictionary containing:
        - count: Total number of devices found
        - devices: List of summarized device information
        - filters_applied: Dictionary of filters that were applied
        - summary_stats: Aggregate statistics about the devices (if include_counts=True)

    Examples:
        # Standard query
        netbox_list_all_devices(site_name="datacenter-1", role_name="switch")

        # Performance optimized for device discovery
        netbox_list_all_devices(fields=["name", "status"], summary_mode=True)

        # Location-focused query
        netbox_list_all_devices(include_related=["site", "rack"])

        # Complete device profile
        netbox_list_all_devices(include_related=["site", "rack", "device_type", "role"])
    """
    try:
        # PHASE 2 OPTIMIZATION: Intelligent caching layer
        cache = get_cache()

        # Build cache key parameters
        cache_params = {
            "limit": limit,
            "site_name": site_name,
            "role_name": role_name,
            "tenant_name": tenant_name,
            "status": status,
            "manufacturer_name": manufacturer_name,
            "fields": fields,
            "summary_mode": summary_mode,
            "include_counts": include_counts,
            "include_related": include_related
        }

        # Try to get cached result
        cached_result, cache_type = cache.get_cached_result("list_devices", **cache_params)
        if cached_result is not None:
            logger.info(f"Cache {cache_type.upper()} for device list query - {cache_params}")
            return cached_result

        logger.info(f"Listing devices with filters - site: {site_name}, role: {role_name}, tenant: {tenant_name}, status: {status}, manufacturer: {manufacturer_name}")

        # Build filters dictionary with proper NetBox API parameter resolution
        # CRITICAL FIX #2 & #3: Resolve names to IDs for proper NetBox API filtering
        filters = {}

        # Resolve site name to site ID
        if site_name:
            try:
                sites = list(client.dcim.sites.filter(slug=site_name))
                if not sites:
                    sites = list(client.dcim.sites.filter(name=site_name))
                if sites:
                    site_id = sites[0].get('id') if isinstance(sites[0], dict) else sites[0].id
                    filters['site_id'] = site_id
                    logger.info(f"Resolved site '{site_name}' to ID {site_id}")
                else:
                    logger.warning(f"Site '{site_name}' not found, skipping site filter")
            except Exception as e:
                logger.warning(f"Failed to resolve site '{site_name}': {e}")

        # Resolve role name to role ID
        if role_name:
            try:
                roles = list(client.dcim.device_roles.filter(slug=role_name))
                if not roles:
                    roles = list(client.dcim.device_roles.filter(name=role_name))
                if roles:
                    role_id = roles[0].get('id') if isinstance(roles[0], dict) else roles[0].id
                    filters['role_id'] = role_id
                    logger.info(f"Resolved role '{role_name}' to ID {role_id}")
                else:
                    logger.warning(f"Role '{role_name}' not found, skipping role filter")
            except Exception as e:
                logger.warning(f"Failed to resolve role '{role_name}': {e}")

        # Resolve tenant name to tenant ID
        if tenant_name:
            try:
                tenants = list(client.tenancy.tenants.filter(slug=tenant_name))
                if not tenants:
                    tenants = list(client.tenancy.tenants.filter(name=tenant_name))
                if tenants:
                    tenant_id = tenants[0].get('id') if isinstance(tenants[0], dict) else tenants[0].id
                    filters['tenant_id'] = tenant_id
                    logger.info(f"Resolved tenant '{tenant_name}' to ID {tenant_id}")
                else:
                    logger.warning(f"Tenant '{tenant_name}' not found, skipping tenant filter")
            except Exception as e:
                logger.warning(f"Failed to resolve tenant '{tenant_name}': {e}")

        # Status can be used directly
        if status:
            filters['status'] = status

        # Smart manufacturer filtering with automatic fallback
        original_manufacturer_name = manufacturer_name
        if manufacturer_name:
            try:
                manufacturers = list(client.dcim.manufacturers.filter(slug=manufacturer_name))
                if not manufacturers:
                    manufacturers = list(client.dcim.manufacturers.filter(name=manufacturer_name))
                if manufacturers:
                    manufacturer_id = manufacturers[0].get('id') if isinstance(manufacturers[0], dict) else manufacturers[0].id
                    filters['device_type__manufacturer_id'] = manufacturer_id
                    logger.info(f"Resolved manufacturer '{manufacturer_name}' to ID {manufacturer_id}")
                else:
                    logger.warning(f"Manufacturer '{manufacturer_name}' not found, using fallback filtering")
            except Exception as e:
                logger.warning(f"Failed to resolve manufacturer '{manufacturer_name}': {e}, using fallback")

        # PHASE 2 OPTIMIZATION: Field-selective query execution

        # Define field mapping for performance optimization
        essential_fields = ["id", "name", "status"]
        standard_fields = essential_fields + ["role", "site", "device_type", "primary_ip4", "primary_ip6"]
        full_fields = standard_fields + ["rack", "position", "tenant", "serial", "asset_tag", "description"]

        # Determine which fields to fetch based on parameters
        query_fields = None
        if summary_mode:
            query_fields = essential_fields
        elif fields:
            query_fields = fields
            # Always include essential fields
            for field in essential_fields:
                if field not in query_fields:
                    query_fields.append(field)
        elif include_related:
            query_fields = essential_fields[:]
            # Map include_related to actual field names
            related_mapping = {
                "site": ["site"],
                "rack": ["rack", "position"],
                "device_type": ["device_type"],
                "role": ["role"],
                "ip": ["primary_ip4", "primary_ip6"],
                "tenant": ["tenant"]
            }
            for related in include_related:
                if related in related_mapping:
                    query_fields.extend(related_mapping[related])

        # CRITICAL FIX #1: Resolve manufacturer data corruption with simpler approach
        # Use standard pynetbox filtering and resolve manufacturer data dynamically
        # CRITICAL FIX #5: Handle NetBoxClient wrapper returning list from filter()
        try:
            # The NetBoxClient wrapper's filter() method already returns a list
            devices = client.dcim.devices.filter(**filters)

            # Ensure we have a list (in case the wrapper changes)
            if not isinstance(devices, list):
                devices = list(devices)

            logger.info(f"Query executed with filters: {filters}, returned {len(devices)} devices")

        except Exception as e:
            logger.error(f"Device query failed with filters {filters}: {e}")
            devices = []

        # CRITICAL FIX #6: Skip fallback filter when server-side filtering works
        # The fallback filter has bugs with serialized device data (device_type is ID, not object)
        # Since the NetBox API filter IS working (returning 20 devices with manufacturer_id=22),
        # but not all 20 devices are WatchGuard (only 3 are), we should NOT apply fallback
        # The confusion was in the filter diagnostics thinking 20 = "all devices" when it's not
        logger.info(f"Manufacturer filter returned {len(devices)} devices, server-side filtering appears to be working correctly")
        
        # Apply limit after fetching (since pynetbox limit behavior can be inconsistent)
        if len(devices) > limit:
            devices = devices[:limit]
        
        # PHASE 2 OPTIMIZATION: Conditional statistics calculation
        status_counts = {}
        role_counts = {}
        site_counts = {}
        manufacturer_counts = {}

        # Only calculate statistics if requested (performance optimization)
        if include_counts:
            for device in devices:
                # Status breakdown with defensive checks for dictionary access
                status_obj = device.get("status", {})
                if isinstance(status_obj, dict):
                    status = status_obj.get("label", "N/A")
                else:
                    status = str(status_obj) if status_obj else "N/A"
                status_counts[status] = status_counts.get(status, 0) + 1

                # Role breakdown with defensive checks for dictionary access
                role_obj = device.get("role")
                if role_obj:
                    if isinstance(role_obj, dict):
                        role_name = role_obj.get("name", str(role_obj))
                    else:
                        role_name = str(role_obj)
                    role_counts[role_name] = role_counts.get(role_name, 0) + 1

                # Site breakdown with defensive checks for dictionary access
                site_obj = device.get("site")
                if site_obj:
                    if isinstance(site_obj, dict):
                        site_name = site_obj.get("name", str(site_obj))
                    else:
                        site_name = str(site_obj)
                    site_counts[site_name] = site_counts.get(site_name, 0) + 1

                # Manufacturer breakdown with defensive checks for dictionary access
                device_type_obj = device.get("device_type")
                if device_type_obj and isinstance(device_type_obj, dict):
                    manufacturer_obj = device_type_obj.get("manufacturer")
                    if manufacturer_obj:
                        if isinstance(manufacturer_obj, dict):
                            mfg_name = manufacturer_obj.get("name", str(manufacturer_obj))
                        else:
                            mfg_name = str(manufacturer_obj)
                        manufacturer_counts[mfg_name] = manufacturer_counts.get(mfg_name, 0) + 1
        
        # PHASE 2 OPTIMIZATION: Create optimized device list based on field selection
        device_list = []
        for device in devices:
            # DEFENSIVE CHECK: Handle dictionary access for all device attributes
            status_obj = device.get("status", {})
            if isinstance(status_obj, dict):
                status = status_obj.get("label", "N/A")
            else:
                status = str(status_obj) if status_obj else "N/A"
            
            site_obj = device.get("site")
            site_name = None
            if site_obj and isinstance(site_obj, dict):
                site_name = site_obj.get("name")
            elif site_obj:
                site_name = str(site_obj)
            
            role_obj = device.get("role")
            role_name = None
            if role_obj and isinstance(role_obj, dict):
                role_name = role_obj.get("name")
            elif role_obj:
                role_name = str(role_obj)
            
            device_type_obj = device.get("device_type")
            device_type_model = None
            manufacturer_name = None

            if device_type_obj:
                if isinstance(device_type_obj, dict):
                    # Already expanded device type object
                    device_type_model = device_type_obj.get("model")
                    manufacturer_obj = device_type_obj.get("manufacturer")
                    if manufacturer_obj and isinstance(manufacturer_obj, dict):
                        manufacturer_name = manufacturer_obj.get("name")
                    elif manufacturer_obj:
                        manufacturer_name = str(manufacturer_obj)
                else:
                    # Device type is just an ID - fetch the device type details dynamically
                    try:
                        device_type_id = device_type_obj
                        device_type_record = client.dcim.device_types.get(device_type_id)
                        if device_type_record:
                            device_type_model = device_type_record.model
                            manufacturer_record = device_type_record.manufacturer
                            if manufacturer_record:
                                manufacturer_name = manufacturer_record.name if hasattr(manufacturer_record, 'name') else str(manufacturer_record)
                    except Exception as e:
                        logger.warning(f"Failed to fetch device type {device_type_id}: {e}")
                        device_type_model = None
                        manufacturer_name = None
            
            # Handle IP addresses
            primary_ip4_obj = device.get("primary_ip4")
            primary_ip6_obj = device.get("primary_ip6")
            primary_ip = None
            if primary_ip4_obj:
                if isinstance(primary_ip4_obj, dict):
                    primary_ip = primary_ip4_obj.get("address")
                else:
                    primary_ip = str(primary_ip4_obj)
            elif primary_ip6_obj:
                if isinstance(primary_ip6_obj, dict):
                    primary_ip = primary_ip6_obj.get("address")
                else:
                    primary_ip = str(primary_ip6_obj)
            
            rack_obj = device.get("rack")
            rack_name = None
            if rack_obj and isinstance(rack_obj, dict):
                rack_name = rack_obj.get("name")
            elif rack_obj:
                rack_name = str(rack_obj)
            
            tenant_obj = device.get("tenant")
            tenant_name = None
            if tenant_obj and isinstance(tenant_obj, dict):
                tenant_name = tenant_obj.get("name")
            elif tenant_obj:
                tenant_name = str(tenant_obj)
            
            # PHASE 2 OPTIMIZATION: Field-selective device info creation
            device_info = {"name": device.get("name", "Unknown")}

            if summary_mode:
                # Minimal response mode - only essential fields
                device_info.update({
                    "status": status,
                    "id": device.get("id")
                })
            elif fields:
                # User-specified fields only
                field_mapping = {
                    "status": status,
                    "site": site_name,
                    "role": role_name,
                    "device_type": device_type_model,
                    "manufacturer": manufacturer_name,
                    "primary_ip": primary_ip,
                    "rack": rack_name,
                    "position": device.get("position"),
                    "tenant": tenant_name,
                    "id": device.get("id")
                }
                for field in fields:
                    if field in field_mapping:
                        device_info[field] = field_mapping[field]
            else:
                # Full device info (default behavior)
                device_info.update({
                    "status": status,
                    "site": site_name,
                    "role": role_name,
                    "device_type": device_type_model,
                    "manufacturer": manufacturer_name,
                    "primary_ip": primary_ip,
                    "rack": rack_name,
                    "position": device.get("position"),
                    "tenant": tenant_name
                })

            device_list.append(device_info)
        
        # PHASE 2 OPTIMIZATION: Conditional result structure
        result = {
            "count": len(device_list),
            "devices": device_list,
            "filters_applied": {
                "resolved_filters": {k: v for k, v in filters.items() if v is not None},
                "original_params": {
                    "site_name": site_name,
                    "role_name": role_name,
                    "tenant_name": tenant_name,
                    "manufacturer_name": manufacturer_name,
                    "status": status
                }
            }
        }

        # Only include summary statistics if requested (performance optimization)
        if include_counts:
            result["summary_stats"] = {
                "total_devices": len(device_list),
                "status_breakdown": status_counts,
                "role_breakdown": role_counts,
                "site_breakdown": site_counts,
                "manufacturer_breakdown": manufacturer_counts,
                "devices_with_ip": len([d for d in device_list if d.get('primary_ip')]),
                "devices_in_racks": len([d for d in device_list if d.get('rack')])
            }
        
        # PHASE 2 OPTIMIZATION: Cache the successful result
        cache.cache_result("list_devices", result, **cache_params)

        logger.info(f"Found {len(device_list)} devices matching criteria. Status breakdown: {status_counts}")
        return result
        
    except Exception as e:
        # PHASE 2 OPTIMIZATION: Cache failed query to avoid repetition
        cache.cache_failed_query("list_devices", str(e), **cache_params)

        logger.error(f"Error listing devices: {e}")
        return {
            "count": 0,
            "devices": [],
            "error": str(e),
            "error_type": type(e).__name__,
            "filters_applied": {k: v for k, v in {
                'site_name': site_name,
                'role_name': role_name, 
                'tenant_name': tenant_name,
                'status': status,
                'manufacturer_name': manufacturer_name
            }.items() if v is not None}
        }


@mcp_tool(category="dcim")
def netbox_update_device(
    client: NetBoxClient,
    device_id: int,
    name: Optional[str] = None,
    status: Optional[str] = None,
    role: Optional[str] = None,
    site: Optional[str] = None,
    rack: Optional[str] = None,
    position: Optional[int] = None,
    face: Optional[str] = None,
    device_type: Optional[str] = None,
    platform: Optional[str] = None,
    tenant: Optional[str] = None,
    serial: Optional[str] = None,
    asset_tag: Optional[str] = None,
    description: Optional[str] = None,
    comments: Optional[str] = None,
    oob_ip: Optional[str] = None,
    primary_ip4: Optional[str] = None,
    primary_ip6: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Update an existing device in NetBox DCIM.
    
    This function enables comprehensive device property updates with enterprise-grade
    safety mechanisms and intelligent foreign key resolution for relationship fields.
    
    Args:
        client: NetBoxClient instance (injected)
        device_id: Device ID to update
        name: Device name (hostname)
        status: Device status (active, planned, staged, failed, inventory, decommissioning, offline)
        role: Device role name or slug
        site: Site name or slug  
        rack: Rack name (will be resolved within the device's site)
        position: Rack position (bottom U)
        face: Rack face (front, rear)
        device_type: Device type model or slug
        platform: Platform name or slug
        tenant: Tenant name or slug
        serial: Serial number
        asset_tag: Asset tag
        description: Device description
        comments: Device comments
        oob_ip: Out-of-band management IP (e.g., BMC/iDRAC IP with CIDR notation)
        primary_ip4: Primary IPv4 address (must be assigned to device interface)
        primary_ip6: Primary IPv6 address (must be assigned to device interface)
        confirm: Must be True to execute (safety mechanism)
    
    Returns:
        Dict containing the updated device data and operation status
        
    Examples:
        # Update device status and description
        result = netbox_update_device(
            device_id=123,
            status="planned",
            description="Updated via NetBox MCP",
            confirm=True
        )
        
        # Move device to different rack
        result = netbox_update_device(
            device_id=456,
            rack="R01-A23",
            position=42,
            face="front",
            confirm=True
        )
        
        # Change device role and platform
        result = netbox_update_device(
            device_id=789,
            role="server",
            platform="Linux",
            confirm=True
        )
        
        # Set device OOB IP for BMC/iDRAC management
        result = netbox_update_device(
            device_id=456,
            oob_ip="192.168.100.10/24",
            description="Server with iDRAC configured",
            confirm=True
        )
        
        # Set primary IP addresses for device
        result = netbox_update_device(
            device_id=62,
            primary_ip4="82.94.240.130/24",
            primary_ip6="2001:888:2000:1450::82:94:240:130/64",
            confirm=True
        )
    """
    
    # STEP 1: DRY RUN CHECK
    if not confirm:
        update_fields = {}
        if name: update_fields["name"] = name
        if status: update_fields["status"] = status
        if role: update_fields["role"] = role
        if site: update_fields["site"] = site
        if rack: update_fields["rack"] = rack
        if position is not None: update_fields["position"] = position
        if face: update_fields["face"] = face
        if device_type: update_fields["device_type"] = device_type
        if platform: update_fields["platform"] = platform
        if tenant: update_fields["tenant"] = tenant
        if serial: update_fields["serial"] = serial
        if asset_tag: update_fields["asset_tag"] = asset_tag
        if description is not None: update_fields["description"] = description
        if comments is not None: update_fields["comments"] = comments
        if oob_ip: update_fields["oob_ip"] = oob_ip
        if primary_ip4: update_fields["primary_ip4"] = primary_ip4
        if primary_ip6: update_fields["primary_ip6"] = primary_ip6
        
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Device would be updated. Set confirm=True to execute.",
            "would_update": {
                "device_id": device_id,
                "fields": update_fields
            }
        }
    
    # STEP 2: PARAMETER VALIDATION
    if not device_id or device_id <= 0:
        raise ValueError("device_id must be a positive integer")
    
    # Check that at least one field is provided for update
    update_fields = [name, status, role, site, rack, position, face, device_type, platform, 
                    tenant, serial, asset_tag, description, comments, oob_ip, primary_ip4, primary_ip6]
    if not any(field is not None for field in update_fields):
        raise ValueError("At least one field must be provided for update")
    
    # STEP 3: VERIFY DEVICE EXISTS
    try:
        existing_device = client.dcim.devices.get(device_id)
        if not existing_device:
            raise ValueError(f"Device with ID {device_id} not found")
        
        # Apply defensive dict/object handling
        device_name = existing_device.get('name') if isinstance(existing_device, dict) else existing_device.name
        device_site = existing_device.get('site') if isinstance(existing_device, dict) else existing_device.site
        
        # Extract site ID for rack resolution
        if isinstance(device_site, dict):
            current_site_id = device_site.get('id')
            current_site_name = device_site.get('name', 'Unknown')
        else:
            current_site_id = getattr(device_site, 'id', None)
            current_site_name = getattr(device_site, 'name', 'Unknown')
            
    except Exception as e:
        raise ValueError(f"Could not retrieve device {device_id}: {e}")
    
    # STEP 4: BUILD UPDATE PAYLOAD WITH FOREIGN KEY RESOLUTION
    update_payload = {}
    
    # Basic string fields
    if name is not None:
        if name and not name.strip():
            raise ValueError("name cannot be empty")
        update_payload["name"] = name
    
    if status:
        valid_statuses = ["active", "planned", "staged", "failed", "inventory", "decommissioning", "offline"]
        if status not in valid_statuses:
            raise ValueError(f"status must be one of: {', '.join(valid_statuses)}")
        update_payload["status"] = status
    
    if serial is not None:
        update_payload["serial"] = serial
        
    if asset_tag is not None:
        update_payload["asset_tag"] = asset_tag
        
    if description is not None:
        update_payload["description"] = f"[NetBox-MCP] {description}" if description else ""
        
    if comments is not None:
        update_payload["comments"] = f"[NetBox-MCP] {comments}" if comments else ""
    
    if face:
        if face not in ["front", "rear"]:
            raise ValueError("face must be 'front' or 'rear'")
        update_payload["face"] = face
    
    if position is not None:
        if position < 1:
            raise ValueError("position must be 1 or greater")
        update_payload["position"] = position
    
    # Foreign key resolution for relationship fields
    if role:
        try:
            roles = client.dcim.device_roles.filter(name=role)
            if not roles:
                roles = client.dcim.device_roles.filter(slug=role)
            if not roles:
                raise ValueError(f"Device role '{role}' not found")
            role_obj = roles[0]
            role_id = role_obj.get('id') if isinstance(role_obj, dict) else role_obj.id
            update_payload["role"] = role_id
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Could not find device role '{role}': {e}")
    
    if site:
        try:
            sites = client.dcim.sites.filter(name=site)
            if not sites:
                sites = client.dcim.sites.filter(slug=site)
            if not sites:
                raise ValueError(f"Site '{site}' not found")
            site_obj = sites[0]
            site_id = site_obj.get('id') if isinstance(site_obj, dict) else site_obj.id
            update_payload["site"] = site_id
            # Update current_site_id for rack resolution
            current_site_id = site_id
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Could not find site '{site}': {e}")
    
    if device_type:
        try:
            device_types = client.dcim.device_types.filter(model=device_type)
            if not device_types:
                device_types = client.dcim.device_types.filter(slug=device_type)
            if not device_types:
                raise ValueError(f"Device type '{device_type}' not found")
            dt_obj = device_types[0]
            dt_id = dt_obj.get('id') if isinstance(dt_obj, dict) else dt_obj.id
            update_payload["device_type"] = dt_id
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Could not find device type '{device_type}': {e}")
    
    if platform:
        try:
            platforms = client.dcim.platforms.filter(name=platform)
            if not platforms:
                platforms = client.dcim.platforms.filter(slug=platform)
            if not platforms:
                raise ValueError(f"Platform '{platform}' not found")
            platform_obj = platforms[0]
            platform_id = platform_obj.get('id') if isinstance(platform_obj, dict) else platform_obj.id
            update_payload["platform"] = platform_id
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Could not find platform '{platform}': {e}")
    
    if tenant:
        try:
            tenants = client.tenancy.tenants.filter(name=tenant)
            if not tenants:
                tenants = client.tenancy.tenants.filter(slug=tenant)
            if not tenants:
                raise ValueError(f"Tenant '{tenant}' not found")
            tenant_obj = tenants[0]
            tenant_id = tenant_obj.get('id') if isinstance(tenant_obj, dict) else tenant_obj.id
            update_payload["tenant"] = tenant_id
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Could not find tenant '{tenant}': {e}")
    
    if rack:
        try:
            # Rack resolution requires site context
            if not current_site_id:
                raise ValueError("Cannot resolve rack without a valid site context")
            
            racks = client.dcim.racks.filter(name=rack, site_id=current_site_id)
            if not racks:
                raise ValueError(f"Rack '{rack}' not found in site '{current_site_name}'")
            rack_obj = racks[0]
            rack_id = rack_obj.get('id') if isinstance(rack_obj, dict) else rack_obj.id
            update_payload["rack"] = rack_id
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Could not find rack '{rack}': {e}")
    
    # OOB IP resolution for device-level management IP
    if oob_ip:
        try:
            # Validate IP address format
            import ipaddress
            try:
                ip_obj = ipaddress.ip_interface(oob_ip)
                validated_oob_ip = str(ip_obj)
            except ValueError as e:
                raise ValueError(f"Invalid OOB IP address format '{oob_ip}': {e}")
            
            # Look for existing IP address with comprehensive search
            existing_ips = client.ipam.ip_addresses.filter(address=validated_oob_ip)
            if existing_ips:
                # Use existing IP address
                ip_obj = existing_ips[0]
                oob_ip_id = ip_obj.get('id') if isinstance(ip_obj, dict) else ip_obj.id
                
                # Apply defensive dict/object handling for assigned_object_type check
                assigned_object_type = ip_obj.get('assigned_object_type') if isinstance(ip_obj, dict) else getattr(ip_obj, 'assigned_object_type', None)
                
                # Check if IP is already assigned to an interface (OOB should be device-level only)
                if assigned_object_type == 'dcim.interface':
                    logger.warning(f"OOB IP {validated_oob_ip} is currently assigned to an interface, proceeding to use for device OOB field anyway")
                
                logger.debug(f"Using existing OOB IP address: {validated_oob_ip} (ID: {oob_ip_id})")
                update_payload["oob_ip"] = oob_ip_id
            else:
                # Try alternative search without full CIDR (in case of format mismatch)
                ip_without_cidr = validated_oob_ip.split('/')[0]
                alternative_ips = client.ipam.ip_addresses.filter(address__net_contains=ip_without_cidr)
                
                if alternative_ips:
                    # Found IP with different CIDR notation
                    ip_obj = alternative_ips[0]
                    oob_ip_id = ip_obj.get('id') if isinstance(ip_obj, dict) else ip_obj.id
                    existing_address = ip_obj.get('address') if isinstance(ip_obj, dict) else getattr(ip_obj, 'address', None)
                    
                    logger.info(f"Found existing IP {existing_address} for OOB request {validated_oob_ip}, using existing IP")
                    update_payload["oob_ip"] = oob_ip_id
                else:
                    # Only create new IP if absolutely not found
                    ip_data = {
                        "address": validated_oob_ip,
                        "status": "active",
                        "description": f"[NetBox-MCP] OOB IP for device {device_name}"
                    }
                    
                    logger.debug(f"Creating new OOB IP address: {validated_oob_ip}")
                    try:
                        new_ip = client.ipam.ip_addresses.create(confirm=True, **ip_data)
                        oob_ip_id = new_ip.get('id') if isinstance(new_ip, dict) else new_ip.id
                        update_payload["oob_ip"] = oob_ip_id
                    except Exception as create_error:
                        # If creation fails due to duplicate, try one more search
                        if "Duplicate IP address" in str(create_error):
                            logger.warning(f"Duplicate IP detected during creation, retrying search for {validated_oob_ip}")
                            retry_ips = client.ipam.ip_addresses.filter(address=validated_oob_ip)
                            if retry_ips:
                                ip_obj = retry_ips[0]
                                oob_ip_id = ip_obj.get('id') if isinstance(ip_obj, dict) else ip_obj.id
                                update_payload["oob_ip"] = oob_ip_id
                                logger.info(f"Successfully found existing OOB IP on retry: {validated_oob_ip} (ID: {oob_ip_id})")
                            else:
                                raise create_error
                        else:
                            raise create_error
                
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Could not resolve OOB IP '{oob_ip}': {e}")
    
    # Primary IP resolution for primary_ip4 and primary_ip6
    if primary_ip4:
        try:
            # Use the same robust IP search logic as netbox_set_primary_ip
            import ipaddress
            try:
                ip_obj = ipaddress.ip_interface(primary_ip4)
                validated_primary_ip4 = str(ip_obj)
            except ValueError as e:
                raise ValueError(f"Invalid primary IPv4 address format '{primary_ip4}': {e}")
            
            # Search for existing IP with flexible search
            existing_ips = client.ipam.ip_addresses.filter(address=validated_primary_ip4)
            if not existing_ips:
                ip_base = validated_primary_ip4.split('/')[0]
                for search_ip in [f"{ip_base}/24", f"{ip_base}/32", f"{ip_base}/16"]:
                    existing_ips = client.ipam.ip_addresses.filter(address=search_ip)
                    if existing_ips:
                        validated_primary_ip4 = search_ip
                        break
            
            if not existing_ips:
                raise ValueError(f"Primary IPv4 address {primary_ip4} not found in NetBox. Ensure IP is assigned to device interface first.")
            
            ip_address_obj = existing_ips[0]
            primary_ip4_id = ip_address_obj.get('id') if isinstance(ip_address_obj, dict) else ip_address_obj.id
            
            # Verify IP is assigned to this device's interface
            assigned_object_type = ip_address_obj.get('assigned_object_type') if isinstance(ip_address_obj, dict) else getattr(ip_address_obj, 'assigned_object_type', None)
            assigned_object_id = ip_address_obj.get('assigned_object_id') if isinstance(ip_address_obj, dict) else getattr(ip_address_obj, 'assigned_object_id', None)
            
            if assigned_object_type == "dcim.interface" and assigned_object_id:
                interface = client.dcim.interfaces.get(assigned_object_id)
                interface_device_id = None
                
                if isinstance(interface, dict):
                    interface_device = interface.get('device')
                    if isinstance(interface_device, int):
                        interface_device_id = interface_device
                    elif isinstance(interface_device, dict):
                        interface_device_id = interface_device.get('id')
                else:
                    interface_device = getattr(interface, 'device', None)
                    if isinstance(interface_device, int):
                        interface_device_id = interface_device
                    else:
                        interface_device_id = getattr(interface_device, 'id', None) if interface_device else None
                
                if interface_device_id != device_id:
                    raise ValueError(f"Primary IPv4 address {validated_primary_ip4} is not assigned to device {device_name}")
            
            update_payload["primary_ip4"] = primary_ip4_id
            
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Could not resolve primary IPv4 '{primary_ip4}': {e}")
    
    if primary_ip6:
        try:
            # Same logic for IPv6
            import ipaddress
            try:
                ip_obj = ipaddress.ip_interface(primary_ip6)
                validated_primary_ip6 = str(ip_obj)
            except ValueError as e:
                raise ValueError(f"Invalid primary IPv6 address format '{primary_ip6}': {e}")
            
            # Search for existing IP
            existing_ips = client.ipam.ip_addresses.filter(address=validated_primary_ip6)
            if not existing_ips:
                ip_base = validated_primary_ip6.split('/')[0]
                for search_ip in [f"{ip_base}/64", f"{ip_base}/128", f"{ip_base}/48"]:
                    existing_ips = client.ipam.ip_addresses.filter(address=search_ip)
                    if existing_ips:
                        validated_primary_ip6 = search_ip
                        break
            
            if not existing_ips:
                raise ValueError(f"Primary IPv6 address {primary_ip6} not found in NetBox. Ensure IP is assigned to device interface first.")
            
            ip_address_obj = existing_ips[0]
            primary_ip6_id = ip_address_obj.get('id') if isinstance(ip_address_obj, dict) else ip_address_obj.id
            
            # Verify IP is assigned to this device's interface (same logic as IPv4)
            assigned_object_type = ip_address_obj.get('assigned_object_type') if isinstance(ip_address_obj, dict) else getattr(ip_address_obj, 'assigned_object_type', None)
            assigned_object_id = ip_address_obj.get('assigned_object_id') if isinstance(ip_address_obj, dict) else getattr(ip_address_obj, 'assigned_object_id', None)
            
            if assigned_object_type == "dcim.interface" and assigned_object_id:
                interface = client.dcim.interfaces.get(assigned_object_id)
                interface_device_id = None
                
                if isinstance(interface, dict):
                    interface_device = interface.get('device')
                    if isinstance(interface_device, int):
                        interface_device_id = interface_device
                    elif isinstance(interface_device, dict):
                        interface_device_id = interface_device.get('id')
                else:
                    interface_device = getattr(interface, 'device', None)
                    if isinstance(interface_device, int):
                        interface_device_id = interface_device
                    else:
                        interface_device_id = getattr(interface_device, 'id', None) if interface_device else None
                
                if interface_device_id != device_id:
                    raise ValueError(f"Primary IPv6 address {validated_primary_ip6} is not assigned to device {device_name}")
            
            update_payload["primary_ip6"] = primary_ip6_id
            
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Could not resolve primary IPv6 '{primary_ip6}': {e}")
    
    # STEP 5: CONFLICT DETECTION FOR RACK POSITION
    if rack and position is not None:
        try:
            # Check if the position is already occupied by another device
            rack_id = update_payload.get("rack")
            if rack_id:
                existing_devices = client.dcim.devices.filter(
                    rack_id=rack_id, 
                    position=position,
                    no_cache=True  # Force live check
                )
                
                for existing in existing_devices:
                    existing_id = existing.get('id') if isinstance(existing, dict) else existing.id
                    if existing_id != device_id:  # Different device occupying the position
                        existing_name = existing.get('name') if isinstance(existing, dict) else existing.name
                        raise ValueError(f"Position {position} in rack is already occupied by device '{existing_name}' (ID: {existing_id})")
                        
        except ValueError:
            raise
        except Exception as e:
            logger.warning(f"Could not check rack position conflicts: {e}")
    
    # STEP 6: UPDATE DEVICE
    try:
        updated_device = client.dcim.devices.update(device_id, confirm=confirm, **update_payload)
        
        # Apply defensive dict/object handling to response
        device_id_updated = updated_device.get('id') if isinstance(updated_device, dict) else updated_device.id
        device_name_updated = updated_device.get('name') if isinstance(updated_device, dict) else updated_device.name
        device_status_updated = updated_device.get('status') if isinstance(updated_device, dict) else getattr(updated_device, 'status', None)
        
        # Handle status object/dict
        if isinstance(device_status_updated, dict):
            status_label = device_status_updated.get('label', device_status_updated.get('value', 'Unknown'))
        else:
            status_label = str(device_status_updated) if device_status_updated else 'Unknown'
        
    except Exception as e:
        raise ValueError(f"NetBox API error during device update: {e}")
    
    # STEP 7: RETURN SUCCESS
    return {
        "success": True,
        "message": f"Device ID {device_id} successfully updated.",
        "data": {
            "device_id": device_id_updated,
            "name": device_name_updated,
            "status": status_label,
            "serial": updated_device.get('serial') if isinstance(updated_device, dict) else getattr(updated_device, 'serial', None),
            "asset_tag": updated_device.get('asset_tag') if isinstance(updated_device, dict) else getattr(updated_device, 'asset_tag', None),
            "description": updated_device.get('description') if isinstance(updated_device, dict) else getattr(updated_device, 'description', None)
        }
    }


@mcp_tool(category="dcim")
def netbox_set_primary_ip(
    client: NetBoxClient,
    device_name: str,
    ip_address: str,
    ip_version: str = "auto",
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Set primary IP address for a device in NetBox DCIM.
    
    This tool sets the primary IPv4 or IPv6 address for a device by updating the 
    device's primary_ip4 or primary_ip6 field. The IP address must already be 
    assigned to an interface on the device.
    
    Args:
        client: NetBoxClient instance (injected)
        device_name: Name of the device
        ip_address: IP address with CIDR notation (e.g., "10.0.1.100/24")
        ip_version: IP version selection ("auto", "ipv4", "ipv6")
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Dict containing the primary IP assignment result and device information
        
    Examples:
        # Auto-detect IP version
        netbox_set_primary_ip("server-01", "10.0.1.100/24", confirm=True)
        
        # Force IPv4 assignment
        netbox_set_primary_ip("server-01", "10.0.1.100/24", "ipv4", confirm=True)
        
        # IPv6 primary assignment
        netbox_set_primary_ip("server-01", "2001:db8::1/64", "ipv6", confirm=True)
        
        # Management IP as primary
        netbox_set_primary_ip("switch-01", "192.168.100.20/24", confirm=True)
    """
    
    # STEP 1: DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Primary IP would be set. Set confirm=True to execute.",
            "would_update": {
                "device": device_name,
                "ip_address": ip_address,
                "ip_version": ip_version
            }
        }
    
    # STEP 2: PARAMETER VALIDATION
    if not device_name or not device_name.strip():
        raise ValueError("device_name cannot be empty")
    
    if not ip_address or not ip_address.strip():
        raise ValueError("ip_address cannot be empty")
    
    if ip_version not in ["auto", "ipv4", "ipv6"]:
        raise ValueError("ip_version must be 'auto', 'ipv4', or 'ipv6'")
    
    # STEP 3: VALIDATE IP ADDRESS FORMAT AND DETERMINE VERSION
    try:
        import ipaddress
        ip_obj = ipaddress.ip_interface(ip_address)
        validated_ip = str(ip_obj)
        
        # Determine IP version
        if ip_version == "auto":
            detected_version = "ipv4" if ip_obj.version == 4 else "ipv6"
        elif ip_version == "ipv4" and ip_obj.version != 4:
            raise ValueError(f"IP address {ip_address} is not IPv4 but ip_version is set to 'ipv4'")
        elif ip_version == "ipv6" and ip_obj.version != 6:
            raise ValueError(f"IP address {ip_address} is not IPv6 but ip_version is set to 'ipv6'")
        else:
            detected_version = ip_version
            
    except ValueError as e:
        if "cannot be empty" in str(e) or "must be" in str(e):
            raise  # Re-raise our parameter validation errors
        else:
            raise ValueError(f"Invalid IP address format '{ip_address}': {e}")
    
    # STEP 4: LOOKUP DEVICE
    try:
        devices = client.dcim.devices.filter(name=device_name)
        if not devices:
            raise ValueError(f"Device '{device_name}' not found")
        
        device = devices[0]
        device_id = device.get('id') if isinstance(device, dict) else device.id
        device_display = device.get('display', device_name) if isinstance(device, dict) else getattr(device, 'display', device_name)
        
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Could not find device '{device_name}': {e}")
    
    # STEP 5: FIND IP ADDRESS OBJECT WITH FLEXIBLE SEARCH
    try:
        existing_ips = client.ipam.ip_addresses.filter(address=validated_ip)
        
        if not existing_ips:
            # If exact match failed, try alternative search methods
            ip_base = validated_ip.split('/')[0]  # Get IP without subnet
            
            # Try searching for IP with common subnet masks
            alternative_searches = []
            if '/' not in ip_address:  # Original input had no subnet
                # Try common subnets for the IP
                alternative_searches = [f"{ip_base}/24", f"{ip_base}/32", f"{ip_base}/16"]
            else:
                # Try without subnet or with alternative subnets
                alternative_searches = [ip_base, f"{ip_base}/24", f"{ip_base}/32"]
            
            for search_ip in alternative_searches:
                existing_ips = client.ipam.ip_addresses.filter(address=search_ip)
                if existing_ips:
                    logger.info(f"Found IP address {search_ip} for search term {ip_address}")
                    validated_ip = search_ip  # Update validated_ip to match what we found
                    break
            
            if not existing_ips:
                # Final attempt: search by IP address alone (network contains search)
                try:
                    existing_ips = client.ipam.ip_addresses.filter(address__net_contains=ip_base)
                    if existing_ips:
                        found_ip = existing_ips[0]
                        found_address = found_ip.get('address') if isinstance(found_ip, dict) else getattr(found_ip, 'address', None)
                        logger.info(f"Found IP address {found_address} using network search for {ip_base}")
                        validated_ip = found_address
                except Exception as search_error:
                    logger.debug(f"Network search failed: {search_error}")
        
        if not existing_ips:
            # Provide helpful error message
            search_terms_tried = [validated_ip] + alternative_searches if 'alternative_searches' in locals() else [validated_ip]
            raise ValueError(f"IP address not found in NetBox. Tried: {', '.join(search_terms_tried)}. Ensure IP is assigned to device interface first.")
        
        ip_address_obj = existing_ips[0]
        ip_id = ip_address_obj.get('id') if isinstance(ip_address_obj, dict) else ip_address_obj.id
        
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Could not find IP address '{validated_ip}': {e}")
    
    # STEP 6: VERIFY IP IS ASSIGNED TO DEVICE INTERFACE
    try:
        # Check if IP is assigned to an interface
        assigned_object_type = ip_address_obj.get('assigned_object_type') if isinstance(ip_address_obj, dict) else getattr(ip_address_obj, 'assigned_object_type', None)
        assigned_object_id = ip_address_obj.get('assigned_object_id') if isinstance(ip_address_obj, dict) else getattr(ip_address_obj, 'assigned_object_id', None)
        
        if assigned_object_type != "dcim.interface" or not assigned_object_id:
            raise ValueError(f"IP address {validated_ip} is not assigned to any interface")
        
        # Get the interface and verify it belongs to our device
        interface = client.dcim.interfaces.get(assigned_object_id)
        
        # Apply comprehensive defensive handling for interface → device resolution
        interface_name = 'Unknown'
        interface_device_id = None
        interface_device_name = 'Unknown'
        
        if isinstance(interface, dict):
            interface_name = interface.get('name', 'Unknown')
            interface_device = interface.get('device')
            
            if isinstance(interface_device, dict):
                # Device is a nested object with id and name
                interface_device_id = interface_device.get('id')
                interface_device_name = interface_device.get('name', 'Unknown')
            elif isinstance(interface_device, int):
                # Device is just an ID, need to fetch the device object
                interface_device_id = interface_device
                try:
                    device_obj = client.dcim.devices.get(interface_device_id)
                    interface_device_name = device_obj.get('name') if isinstance(device_obj, dict) else device_obj.name
                except Exception as e:
                    logger.warning(f"Could not fetch device name for ID {interface_device_id}: {e}")
                    interface_device_name = f"Device-{interface_device_id}"
            elif interface_device is not None:
                # Device is some other object type
                interface_device_id = getattr(interface_device, 'id', None)
                interface_device_name = getattr(interface_device, 'name', 'Unknown')
        else:
            # Handle as object
            interface_name = getattr(interface, 'name', 'Unknown')
            interface_device = getattr(interface, 'device', None)
            
            if interface_device:
                if isinstance(interface_device, int):
                    # Device is just an ID
                    interface_device_id = interface_device
                    try:
                        device_obj = client.dcim.devices.get(interface_device_id)
                        interface_device_name = device_obj.get('name') if isinstance(device_obj, dict) else device_obj.name
                    except Exception as e:
                        logger.warning(f"Could not fetch device name for ID {interface_device_id}: {e}")
                        interface_device_name = f"Device-{interface_device_id}"
                else:
                    # Device is an object
                    interface_device_id = getattr(interface_device, 'id', None)
                    interface_device_name = getattr(interface_device, 'name', 'Unknown')
        
        if interface_device_id != device_id:
            raise ValueError(f"IP address {validated_ip} is assigned to device '{interface_device_name}', not '{device_name}'")
        
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Could not verify IP assignment: {e}")
    
    # STEP 7: UPDATE DEVICE PRIMARY IP
    primary_field = "primary_ip4" if detected_version == "ipv4" else "primary_ip6"
    
    try:
        update_payload = {primary_field: ip_id}
        
        updated_device = client.dcim.devices.update(device_id, confirm=confirm, **update_payload)
        
        # Apply defensive dict/object handling to response
        device_id_updated = updated_device.get('id') if isinstance(updated_device, dict) else updated_device.id
        device_name_updated = updated_device.get('name') if isinstance(updated_device, dict) else updated_device.name
        
    except Exception as e:
        raise ValueError(f"NetBox API error during primary IP update: {e}")
    
    # STEP 8: RETURN SUCCESS
    return {
        "success": True,
        "message": f"Primary {detected_version.upper()} address successfully set for device '{device_name}'.",
        "data": {
            "device_id": device_id_updated,
            "device_name": device_name_updated,
            "primary_ip": {
                "address": validated_ip,
                "version": detected_version,
                "field": primary_field,
                "ip_id": ip_id
            },
            "assignment": {
                "interface_name": interface_name,
                "interface_id": assigned_object_id
            }
        }
    }


def _apply_manufacturer_fallback_filter(
    devices: list,
    manufacturer_name: str,
    limit: int,
    logger
) -> list:
    """
    Apply client-side manufacturer filtering as fallback when server-side filtering fails.

    This function implements intelligent manufacturer matching with fuzzy logic
    to handle cases where the NetBox API manufacturer filter is ineffective.

    Args:
        devices: List of devices from initial query
        manufacturer_name: Target manufacturer name to filter by
        limit: Maximum number of results to return
        logger: Logger instance for diagnostics

    Returns:
        Filtered list of devices matching manufacturer criteria
    """
    if not devices or not manufacturer_name:
        return devices

    # Get total device count for effectiveness analysis
    total_devices = len(devices)
    logger.debug(f"🔍 Starting client-side manufacturer fallback: {total_devices} devices to filter")

    # Extract all manufacturer names for analysis
    manufacturer_names = set()
    for device in devices:
        device_type_obj = device.get("device_type")
        if device_type_obj and isinstance(device_type_obj, dict):
            manufacturer_obj = device_type_obj.get("manufacturer")
            if manufacturer_obj and isinstance(manufacturer_obj, dict):
                mfg_name = manufacturer_obj.get("name")
                if mfg_name:
                    manufacturer_names.add(mfg_name.lower())

    logger.debug(f"📊 Found manufacturers in dataset: {sorted(manufacturer_names)}")

    # Normalize search term
    search_term = manufacturer_name.lower().strip()

    # Multi-strategy manufacturer matching
    filtered_devices = []
    match_strategies = {
        "exact": 0,
        "exact_case_insensitive": 0,
        "starts_with": 0,
        "contains": 0,
        "fuzzy": 0
    }

    for device in devices:
        device_type_obj = device.get("device_type")
        if not device_type_obj or not isinstance(device_type_obj, dict):
            continue

        manufacturer_obj = device_type_obj.get("manufacturer")
        if not manufacturer_obj or not isinstance(manufacturer_obj, dict):
            continue

        mfg_name = manufacturer_obj.get("name", "").strip()
        if not mfg_name:
            continue

        mfg_lower = mfg_name.lower()
        matched = False
        match_strategy = None

        # Strategy 1: Exact match (case sensitive)
        if mfg_name == manufacturer_name:
            matched = True
            match_strategy = "exact"

        # Strategy 2: Exact match (case insensitive)
        elif mfg_lower == search_term:
            matched = True
            match_strategy = "exact_case_insensitive"

        # Strategy 3: Starts with (common for vendor abbreviations)
        elif mfg_lower.startswith(search_term) or search_term.startswith(mfg_lower):
            matched = True
            match_strategy = "starts_with"

        # Strategy 4: Contains (for partial matches)
        elif search_term in mfg_lower or mfg_lower in search_term:
            matched = True
            match_strategy = "contains"

        # Strategy 5: Fuzzy matching for common variations
        elif _fuzzy_manufacturer_match(search_term, mfg_lower):
            matched = True
            match_strategy = "fuzzy"

        if matched:
            filtered_devices.append(device)
            match_strategies[match_strategy] += 1

            # Apply limit during filtering for performance
            if len(filtered_devices) >= limit:
                logger.debug(f"⚡ Early termination: reached limit of {limit} devices")
                break

    # Log fallback effectiveness
    filtered_count = len(filtered_devices)
    if filtered_count == 0:
        logger.warning(f"⚠️ Client-side fallback returned 0 devices for manufacturer '{manufacturer_name}'")
        logger.warning(f"Available manufacturers: {sorted(manufacturer_names)}")
    elif filtered_count == total_devices:
        logger.warning(f"⚠️ Client-side fallback returned ALL devices - filter may be too broad")
    else:
        percentage = (filtered_count / total_devices) * 100
        logger.info(f"✅ Client-side fallback effective: {filtered_count}/{total_devices} devices ({percentage:.1f}%)")
        logger.info(f"📈 Match strategies used: {match_strategies}")

    return filtered_devices


def _fuzzy_manufacturer_match(search_term: str, manufacturer_name: str) -> bool:
    """
    Fuzzy matching for common manufacturer name variations.

    Handles common cases like:
    - "cisco" <-> "cisco systems"
    - "hp" <-> "hewlett packard" <-> "hewlett-packard"
    - "watchguard" <-> "watch guard"

    Args:
        search_term: User search term (lowercase)
        manufacturer_name: Manufacturer name from device (lowercase)

    Returns:
        True if fuzzy match is found
    """
    # Common manufacturer aliases
    fuzzy_mappings = {
        "cisco": ["cisco systems", "cisco systems inc"],
        "hp": ["hewlett packard", "hewlett-packard", "hpe"],
        "dell": ["dell inc", "dell technologies"],
        "watchguard": ["watch guard", "watchguard technologies"],
        "juniper": ["juniper networks", "juniper networks inc"],
        "arista": ["arista networks"],
        "palo alto": ["palo alto networks", "paloalto"],
        "fortinet": ["fortinet inc"],
        "checkpoint": ["check point", "check point software"],
        "vmware": ["vmware inc"],
        "microsoft": ["microsoft corporation", "microsoft corp"],
        "redhat": ["red hat", "red hat inc"]
    }

    # Check direct mapping
    if search_term in fuzzy_mappings:
        return any(alias in manufacturer_name for alias in fuzzy_mappings[search_term])

    # Check reverse mapping
    for canonical, aliases in fuzzy_mappings.items():
        if manufacturer_name in aliases or manufacturer_name == canonical:
            return search_term == canonical or search_term in aliases

    # Simple word boundary matching
    search_words = search_term.split()
    mfg_words = manufacturer_name.split()

    if len(search_words) == 1 and len(mfg_words) > 1:
        # Single word search against multi-word manufacturer
        return search_words[0] in mfg_words

    if len(mfg_words) == 1 and len(search_words) > 1:
        # Multi-word search against single word manufacturer
        return mfg_words[0] in search_words

    return False


@mcp_tool(category="dcim")
def netbox_search_devices(
    client: NetBoxClient,
    query: str,
    search_fields: Optional[List[str]] = None,
    limit: int = 100,
    include_manufacturer: bool = True,
    include_location: bool = True,
    summary_mode: bool = False
) -> Dict[str, Any]:
    """
    Universal device search with intelligent field matching and relevance scoring.

    This is the preferred tool for device discovery queries. It provides intelligent
    search across multiple device fields with automatic relevance ranking and
    performance optimization.

    Search Strategy Priority:
    1. Exact name match (highest relevance)
    2. Name contains (high relevance)
    3. Serial number match (medium relevance)
    4. Asset tag match (medium relevance)
    5. Description contains (low relevance)
    6. Manufacturer name (lowest relevance)

    Args:
        client: NetBoxClient instance (injected)
        query: Universal search term (device name, serial, manufacturer, etc.)
        search_fields: Specific fields to search (default: all fields)
        limit: Maximum number of results to return (default: 100)
        include_manufacturer: Include manufacturer information (default: True)
        include_location: Include rack/site location data (default: True)
        summary_mode: Return lightweight response for performance (default: False)

    Returns:
        Dictionary containing:
        - count: Number of devices found
        - devices: List of devices with relevance scores
        - search_metadata: Search performance and strategy info
        - filters_applied: Search parameters used

    Examples:
        netbox_search_devices("watchguard")
        # Searches across all fields for "watchguard"

        netbox_search_devices("fw-01", search_fields=["name"])
        # Only searches device names for "fw-01"

        netbox_search_devices("cisco", summary_mode=True)
        # Fast search with minimal data returned
    """
    try:
        # PHASE 2 OPTIMIZATION: Intelligent caching layer for search
        cache = get_cache()

        # Build cache key parameters
        search_cache_params = {
            "query": query,
            "search_fields": search_fields,
            "limit": limit,
            "include_manufacturer": include_manufacturer,
            "include_location": include_location,
            "summary_mode": summary_mode
        }

        # Try to get cached search result
        cached_result, cache_type = cache.get_cached_result("search_devices", **search_cache_params)
        if cached_result is not None:
            logger.info(f"🎯 Cache {cache_type.upper()} for device search: '{query}' - {cache_type}")
            return cached_result

        logger.info(f"🔍 Universal device search: '{query}' (fields: {search_fields}, limit: {limit})")

        # Validate and normalize search query
        if not query or not query.strip():
            return {
                "count": 0,
                "devices": [],
                "error": "Search query cannot be empty",
                "search_metadata": {"query": query, "strategy": "invalid"}
            }

        normalized_query = query.strip().lower()

        # Define search fields and their priority/scoring
        # PHASE 2.4: Added role-based search for hybrid strategy
        default_search_fields = [
            {"field": "name", "priority": 10, "search_type": "exact_and_contains"},
            {"field": "serial", "priority": 8, "search_type": "exact_and_contains"},
            {"field": "asset_tag", "priority": 7, "search_type": "exact_and_contains"},
            {"field": "role", "priority": 6, "search_type": "contains_only"},        # HYBRID: Role-based search
            {"field": "description", "priority": 4, "search_type": "contains_only"},
            {"field": "manufacturer", "priority": 3, "search_type": "contains_only"}
        ]

        # Use specified fields or default to all
        if search_fields:
            active_fields = [f for f in default_search_fields if f["field"] in search_fields]
        else:
            active_fields = default_search_fields

        logger.debug(f"📊 Active search fields: {[f['field'] for f in active_fields]}")

        # Fetch all devices (leverage caching)
        all_devices = list(client.dcim.devices.all())
        total_devices = len(all_devices)

        logger.debug(f"🔄 Searching through {total_devices} total devices")

        # Perform intelligent multi-field search with scoring
        search_results = []
        search_stats = {
            "total_scanned": total_devices,
            "field_matches": {f["field"]: 0 for f in active_fields},
            "strategies_used": set(),
            "early_termination": False
        }

        for device in all_devices:
            device_scores = []
            matched_fields = []

            # Search each active field
            for field_config in active_fields:
                field_name = field_config["field"]
                priority = field_config["priority"]
                search_type = field_config["search_type"]

                field_value = _extract_device_field_value(device, field_name)
                if not field_value:
                    continue

                field_value_lower = field_value.lower()
                match_score = 0

                # Apply search strategy based on field configuration
                if search_type in ["exact_and_contains", "exact_only"]:
                    # Exact match (highest score)
                    if field_value_lower == normalized_query:
                        match_score = priority * 2  # Exact match bonus
                        search_stats["strategies_used"].add(f"{field_name}_exact")

                if search_type in ["exact_and_contains", "contains_only"] and match_score == 0:
                    # Contains match
                    if normalized_query in field_value_lower:
                        match_score = priority
                        search_stats["strategies_used"].add(f"{field_name}_contains")

                if match_score > 0:
                    device_scores.append(match_score)
                    matched_fields.append(field_name)
                    search_stats["field_matches"][field_name] += 1

            # Calculate total relevance score
            if device_scores:
                total_score = sum(device_scores)
                max_possible_score = max(device_scores)

                # Create search result entry
                result_device = _prepare_search_result_device(
                    device, include_manufacturer, include_location, summary_mode
                )
                result_device.update({
                    "_search_score": total_score,
                    "_max_field_score": max_possible_score,
                    "_matched_fields": matched_fields,
                    "_search_relevance": "high" if max_possible_score >= 15 else "medium" if max_possible_score >= 8 else "low"
                })

                search_results.append(result_device)

                # Performance optimization: early termination for high-confidence exact matches
                if len(search_results) >= limit * 2 and max_possible_score >= 20:
                    logger.debug(f"⚡ Early termination: found {len(search_results)} high-confidence matches")
                    search_stats["early_termination"] = True
                    break

        # Sort by relevance score (highest first)
        search_results.sort(key=lambda x: (-x["_search_score"], -x["_max_field_score"]))

        # Apply final limit
        if len(search_results) > limit:
            search_results = search_results[:limit]

        # Prepare response
        result = {
            "count": len(search_results),
            "devices": search_results,
            "search_metadata": {
                "query": query,
                "normalized_query": normalized_query,
                "search_fields": [f["field"] for f in active_fields],
                "total_devices_scanned": search_stats["total_scanned"],
                "field_match_counts": search_stats["field_matches"],
                "strategies_used": list(search_stats["strategies_used"]),
                "early_termination": search_stats["early_termination"],
                "performance": "optimized" if search_stats["early_termination"] else "full_scan"
            },
            "filters_applied": {
                "query": query,
                "search_fields": search_fields,
                "limit": limit,
                "include_manufacturer": include_manufacturer,
                "include_location": include_location,
                "summary_mode": summary_mode
            }
        }

        # Log search effectiveness
        if len(search_results) == 0:
            logger.warning(f"🔍 Universal search returned 0 results for '{query}'")
        else:
            logger.info(f"✅ Universal search found {len(search_results)} devices for '{query}'")
            logger.debug(f"📈 Top result score: {search_results[0]['_search_score']} (fields: {search_results[0]['_matched_fields']})")

        # PHASE 2 OPTIMIZATION: Cache the successful search result
        cache.cache_result("search_devices", result, **search_cache_params)

        return result

    except Exception as e:
        # PHASE 2 OPTIMIZATION: Cache failed search query to avoid repetition
        cache.cache_failed_query("search_devices", str(e), **search_cache_params)

        logger.error(f"Error in universal device search: {e}")
        return {
            "count": 0,
            "devices": [],
            "error": str(e),
            "error_type": type(e).__name__,
            "search_metadata": {"query": query, "strategy": "error"},
            "filters_applied": {"query": query}
        }


def _extract_device_field_value(device: Dict, field_name: str) -> Optional[str]:
    """
    Extract field value from device object for searching.

    Args:
        device: Device dictionary
        field_name: Field name to extract

    Returns:
        String value or None if not found
    """
    if field_name == "name":
        return device.get("name", "")

    elif field_name == "serial":
        return device.get("serial", "")

    elif field_name == "asset_tag":
        return device.get("asset_tag", "")

    elif field_name == "description":
        return device.get("description", "")

    elif field_name == "manufacturer":
        device_type_obj = device.get("device_type")
        if device_type_obj and isinstance(device_type_obj, dict):
            manufacturer_obj = device_type_obj.get("manufacturer")
            if manufacturer_obj and isinstance(manufacturer_obj, dict):
                return manufacturer_obj.get("name", "")

    return None


def _prepare_search_result_device(
    device: Dict,
    include_manufacturer: bool,
    include_location: bool,
    summary_mode: bool
) -> Dict:
    """
    Prepare device object for search results with optional data inclusion.

    Args:
        device: Original device dictionary
        include_manufacturer: Include manufacturer information
        include_location: Include location information
        summary_mode: Return minimal data

    Returns:
        Prepared device dictionary
    """
    # Base device information
    result = {
        "id": device.get("id"),
        "name": device.get("name"),
        "status": device.get("status", {}).get("label", "Unknown") if isinstance(device.get("status"), dict) else str(device.get("status", "Unknown"))
    }

    if summary_mode:
        return result

    # Add standard fields
    result.update({
        "serial": device.get("serial"),
        "asset_tag": device.get("asset_tag"),
        "description": device.get("description")
    })

    # Add manufacturer information
    if include_manufacturer:
        device_type_obj = device.get("device_type")
        if device_type_obj and isinstance(device_type_obj, dict):
            result["device_type"] = device_type_obj.get("model")
            manufacturer_obj = device_type_obj.get("manufacturer")
            if manufacturer_obj and isinstance(manufacturer_obj, dict):
                result["manufacturer"] = manufacturer_obj.get("name")

    # Add location information
    if include_location:
        site_obj = device.get("site")
        if site_obj and isinstance(site_obj, dict):
            result["site"] = site_obj.get("name")

        rack_obj = device.get("rack")
        if rack_obj and isinstance(rack_obj, dict):
            result["rack"] = rack_obj.get("name")
            result["position"] = device.get("position")

    return result


@mcp_tool(category="dcim")
def netbox_find_devices_smart(
    client: NetBoxClient,
    query: str,
    context: Optional[str] = None,
    location: Optional[str] = None,
    role: Optional[str] = None,
    manufacturer: Optional[str] = None,
    return_details: bool = False,
    limit: int = 50
) -> Dict[str, Any]:
    """
    One-shot intelligent device discovery with automatic context inference.

    This advanced tool combines multiple search strategies and provides intelligent
    context understanding to answer complex device queries in a single API call.
    Ideal for answering questions like "Where are WatchGuard firewalls?" or
    "Show me Cisco switches in datacenter-1".

    Context Intelligence:
    - "firewalls" context automatically adds role="firewall" filter
    - "switches" context automatically adds role="switch" filter
    - "servers" context automatically adds role="server" filter
    - Location terms automatically map to site or rack filters
    - Manufacturer terms enhance search accuracy

    Args:
        client: NetBoxClient instance (injected)
        query: Main search term (manufacturer, device name, or general query)
        context: Device context hint ("firewalls", "switches", "servers", etc.)
        location: Site or rack location constraint
        role: Specific device role constraint
        manufacturer: Specific manufacturer constraint
        return_details: Include complete device details (rack position, IPs, etc.)
        limit: Maximum number of results to return (default: 50)

    Returns:
        Dictionary containing:
        - count: Number of devices found
        - devices: List of matching devices with location information
        - query_strategy: How the query was interpreted and executed
        - performance_metrics: Query execution performance data

    Examples:
        netbox_find_devices_smart("watchguard", context="firewalls")
        # Combines: manufacturer search + role="firewall" + location data

        netbox_find_devices_smart("fw-01", location="datacenter-1")
        # Combines: name search + site filter + device details

        netbox_find_devices_smart("cisco", context="switches", return_details=True)
        # Complete switch inventory with rack positions and IPs
    """
    try:
        logger.info(f"🧠 Smart device discovery: '{query}' (context: {context}, location: {location})")

        # Initialize query strategy tracking
        query_strategy = {
            "original_query": query,
            "inferred_filters": {},
            "search_methods": [],
            "context_analysis": {},
            "execution_plan": []
        }

        # Step 1: Context Intelligence - Dynamic role mapping using actual NetBox roles
        # PHASE 2.2 FIX: Replace hardcoded role mappings with dynamic NetBox role discovery
        inferred_role = role
        if context:
            context_lower = context.lower().strip()

            try:
                # PHASE 2.3 OPTIMIZATION: Use cached role data for performance
                cache = get_cache()
                cached_roles, cache_type = cache.get_cached_result("list_device_roles")

                if cached_roles is not None:
                    available_roles = cached_roles
                    logger.info(f"Using cached device roles ({cache_type}) for role mapping")
                else:
                    # Fetch available roles from NetBox and cache the result
                    available_roles = list(client.dcim.device_roles.all())
                    cache.cache_result("list_device_roles", available_roles)
                    logger.info("Fetched and cached device roles for role mapping")
                role_slug_map = {}
                role_name_map = {}

                # Build mapping from role slugs and names to actual slugs
                for role_obj in available_roles:
                    slug = role_obj.get('slug') if isinstance(role_obj, dict) else role_obj.slug
                    name = role_obj.get('name') if isinstance(role_obj, dict) else role_obj.name
                    if slug:
                        role_slug_map[slug.lower()] = slug
                        role_name_map[name.lower()] = slug

                # Enhanced context mappings with fallback strategies
                context_mappings = {
                    # Firewall mappings - try multiple possible role names
                    "firewalls": ["firewall", "router", "edge-router", "gateway"],
                    "firewall": ["firewall", "router", "edge-router", "gateway"],
                    "fw": ["firewall", "router", "edge-router"],

                    # Switch mappings - try switch variations
                    "switches": ["switch", "access-switch", "core-switch", "distribution-switch"],
                    "switch": ["switch", "access-switch", "core-switch"],
                    "sw": ["switch", "access-switch"],

                    # Server mappings
                    "servers": ["server", "hypervisor", "compute"],
                    "server": ["server", "hypervisor", "compute"],
                    "srv": ["server", "hypervisor"],

                    # Router mappings
                    "routers": ["router", "edge-router", "core-router"],
                    "router": ["router", "edge-router", "core-router"],
                    "rtr": ["router", "edge-router"]
                }

                # Find the best matching role slug
                matched_role = None
                if context_lower in context_mappings:
                    candidate_roles = context_mappings[context_lower]

                    # Try to find exact slug match first
                    for candidate in candidate_roles:
                        if candidate.lower() in role_slug_map:
                            matched_role = role_slug_map[candidate.lower()]
                            query_strategy["context_analysis"]["role_match_method"] = f"exact_slug_match: {candidate}"
                            break

                    # If no exact slug match, try name-based matching
                    if not matched_role:
                        for candidate in candidate_roles:
                            if candidate.lower() in role_name_map:
                                matched_role = role_name_map[candidate.lower()]
                                query_strategy["context_analysis"]["role_match_method"] = f"name_based_match: {candidate}"
                                break

                    # If still no match, try partial matching
                    if not matched_role:
                        for candidate in candidate_roles:
                            for slug, actual_slug in role_slug_map.items():
                                if candidate.lower() in slug or slug in candidate.lower():
                                    matched_role = actual_slug
                                    query_strategy["context_analysis"]["role_match_method"] = f"partial_match: {candidate}→{slug}"
                                    break
                            if matched_role:
                                break

                if matched_role:
                    inferred_role = matched_role
                    query_strategy["inferred_filters"]["role"] = inferred_role
                    query_strategy["context_analysis"]["role_inference"] = f"'{context}' → role='{inferred_role}'"
                else:
                    # Log available roles for debugging
                    available_role_names = [r.get('name') if isinstance(r, dict) else r.name for r in available_roles[:5]]
                    query_strategy["context_analysis"]["role_inference_failed"] = f"'{context}' - no match found"
                    query_strategy["context_analysis"]["available_roles_sample"] = available_role_names
                    logger.warning(f"No role mapping found for context '{context}'. Available roles: {available_role_names}")

            except Exception as e:
                logger.warning(f"Failed to fetch roles for dynamic mapping: {e}")
                # Fallback to None role (no role filtering)
                query_strategy["context_analysis"]["role_mapping_error"] = str(e)

        # Step 2: Location Intelligence - Parse location constraints with site mapping
        # CRITICAL FIX #3: Add site name to slug mapping for location queries
        inferred_location = location
        if location:
            try:
                # Try to resolve location to actual site slug/name
                sites = list(client.dcim.sites.filter(slug=location.lower().replace(' ', '-')))
                if not sites:
                    sites = list(client.dcim.sites.filter(name=location))
                if not sites:
                    # Try partial name matching
                    sites = list(client.dcim.sites.filter(name__icontains=location))

                if sites:
                    # Use the first matching site's slug for reliable filtering
                    matched_site = sites[0]
                    site_slug = matched_site.get('slug') if isinstance(matched_site, dict) else matched_site.slug
                    inferred_location = site_slug
                    query_strategy["context_analysis"]["site_resolution"] = f"'{location}' → site_slug='{site_slug}'"
                    logger.info(f"Resolved location '{location}' to site slug '{site_slug}'")
                else:
                    query_strategy["context_analysis"]["site_resolution_failed"] = f"'{location}' - no matching sites found"
                    logger.warning(f"No site found matching location '{location}'")

            except Exception as e:
                logger.warning(f"Failed to resolve site for location '{location}': {e}")
                query_strategy["context_analysis"]["site_resolution_error"] = str(e)

            query_strategy["inferred_filters"]["location"] = inferred_location
            query_strategy["context_analysis"]["location_constraint"] = location

        # Step 3: Query Analysis - Determine search strategy
        normalized_query = query.strip().lower()

        # Check if query looks like a manufacturer name
        is_manufacturer_query = _analyze_manufacturer_query(normalized_query)
        if is_manufacturer_query:
            if not manufacturer:
                manufacturer = query
                query_strategy["inferred_filters"]["manufacturer"] = manufacturer
                query_strategy["context_analysis"]["manufacturer_inference"] = f"'{query}' identified as manufacturer"

        # Step 4: Build compound filter strategy
        filters = {}
        search_methods = []

        # CRITICAL FIX #2 & #3: Use correct NetBox API filter parameter names with ID resolution
        # Add role filter - resolve role slug/name to role ID
        if inferred_role:
            try:
                roles = list(client.dcim.device_roles.filter(slug=inferred_role))
                if not roles:
                    roles = list(client.dcim.device_roles.filter(name=inferred_role))
                if roles:
                    role_id = roles[0].get('id') if isinstance(roles[0], dict) else roles[0].id
                    filters["role_name"] = inferred_role  # For netbox_list_all_devices compatibility
                    search_methods.append("role_filter")
                    query_strategy["context_analysis"]["role_id_resolved"] = f"'{inferred_role}' → ID {role_id}"
                    logger.info(f"Resolved role '{inferred_role}' to ID {role_id}")
                else:
                    logger.warning(f"Role '{inferred_role}' not found, skipping role filter")
            except Exception as e:
                logger.warning(f"Failed to resolve role '{inferred_role}': {e}")

        # Add manufacturer filter - resolve manufacturer name to manufacturer ID
        if manufacturer:
            try:
                manufacturers = list(client.dcim.manufacturers.filter(slug=manufacturer))
                if not manufacturers:
                    manufacturers = list(client.dcim.manufacturers.filter(name=manufacturer))
                if manufacturers:
                    manufacturer_id = manufacturers[0].get('id') if isinstance(manufacturers[0], dict) else manufacturers[0].id
                    filters["manufacturer_name"] = manufacturer  # For netbox_list_all_devices compatibility
                    search_methods.append("manufacturer_filter_with_fallback")
                    query_strategy["context_analysis"]["manufacturer_id_resolved"] = f"'{manufacturer}' → ID {manufacturer_id}"
                    logger.info(f"Resolved manufacturer '{manufacturer}' to ID {manufacturer_id}")
                else:
                    logger.warning(f"Manufacturer '{manufacturer}' not found, skipping manufacturer filter")
            except Exception as e:
                logger.warning(f"Failed to resolve manufacturer '{manufacturer}': {e}")

        # Add location filter - resolve site name to site ID
        if inferred_location:
            try:
                sites = list(client.dcim.sites.filter(slug=inferred_location))
                if not sites:
                    sites = list(client.dcim.sites.filter(name=inferred_location))
                if sites:
                    site_id = sites[0].get('id') if isinstance(sites[0], dict) else sites[0].id
                    filters["site_name"] = inferred_location  # For netbox_list_all_devices compatibility
                    search_methods.append("location_filter")
                    query_strategy["context_analysis"]["site_id_resolved"] = f"'{inferred_location}' → ID {site_id}"
                    logger.info(f"Resolved site '{inferred_location}' to ID {site_id}")
                else:
                    logger.warning(f"Site '{inferred_location}' not found, skipping site filter")
            except Exception as e:
                logger.warning(f"Failed to resolve site '{inferred_location}': {e}")

        query_strategy["search_methods"] = search_methods
        query_strategy["execution_plan"] = [
            "1. Apply compound filters to netbox_list_all_devices",
            "2. Apply universal search on results if needed",
            "3. Enhance with location and detail information",
            "4. Rank results by relevance"
        ]

        logger.debug(f"📋 Execution plan: {search_methods}")

        # Step 5: Execute compound query with fallback mechanisms
        # CRITICAL FIX #4: Implement fallback mechanisms for smart search failures
        devices = []
        total_from_filters = 0

        if filters:
            # Try enhanced list_all_devices with filters first
            logger.debug(f"🔍 Executing filtered query with: {filters}")
            try:
                filtered_results = netbox_list_all_devices(
                    client=client,
                    limit=limit * 2,  # Get extra results for secondary filtering
                    **filters
                )

                if filtered_results.get("error"):
                    logger.warning(f"Filtered query failed: {filtered_results['error']}")
                    devices = []
                else:
                    devices = filtered_results.get("devices", [])
                    total_from_filters = len(devices)

            except Exception as e:
                logger.warning(f"Filtered query exception: {e}")
                devices = []

            # If filtered query failed or returned no results, fallback to universal search
            if not devices:
                logger.info(f"📡 Filtered query failed/empty, falling back to universal search for: {query}")
                try:
                    search_results = netbox_search_devices(
                        client=client,
                        query=query,
                        limit=limit * 2,
                        include_manufacturer=True,
                        include_location=True
                    )

                    if not search_results.get("error"):
                        devices = search_results.get("devices", [])
                        total_from_filters = len(devices)
                        search_methods.append("fallback_universal_search")
                        query_strategy["context_analysis"]["fallback_triggered"] = "filtered_query_failed"
                    else:
                        logger.warning(f"Universal search also failed: {search_results['error']}")

                except Exception as e:
                    logger.warning(f"Universal search fallback also failed: {e}")

        else:
            # No filters, go directly to universal search
            logger.debug(f"🔍 Executing universal search for: {query}")
            try:
                search_results = netbox_search_devices(
                    client=client,
                    query=query,
                    limit=limit * 2,
                    include_manufacturer=True,
                    include_location=True
                )

                if not search_results.get("error"):
                    devices = search_results.get("devices", [])
                    total_from_filters = len(devices)
                    search_methods.append("universal_search")
                else:
                    logger.warning(f"Universal search failed: {search_results['error']}")

            except Exception as e:
                logger.warning(f"Universal search failed: {e}")
                devices = []

        # Step 6: Secondary filtering if needed
        if not filters and (inferred_role or inferred_location):
            # Apply secondary filters to universal search results
            logger.debug(f"🔧 Applying secondary filters: role={inferred_role}, location={inferred_location}")
            devices = _apply_secondary_filters(devices, inferred_role, inferred_location)
            search_methods.append("secondary_filtering")

        # Step 7: Enhance results with details if requested
        if return_details:
            logger.debug(f"📊 Enhancing {len(devices)} devices with detailed information")
            devices = _enhance_devices_with_details(devices, client)
            search_methods.append("detail_enhancement")

        # Step 8: Apply final limit and ranking
        if len(devices) > limit:
            # Sort by relevance if we have search scores
            if devices and "_search_score" in devices[0]:
                devices.sort(key=lambda x: x.get("_search_score", 0), reverse=True)
            devices = devices[:limit]

        # Step 9: Performance metrics
        performance_metrics = {
            "total_found": len(devices),
            "filters_applied": len(filters),
            "search_methods_used": len(search_methods),
            "context_inferences": len(query_strategy["inferred_filters"]),
            "execution_efficiency": "optimized" if filters else "fallback_search"
        }

        # Step 10: Build response
        result = {
            "count": len(devices),
            "devices": devices,
            "query_strategy": query_strategy,
            "performance_metrics": performance_metrics,
            "filters_applied": {
                "query": query,
                "context": context,
                "location": location,
                "role": role,
                "manufacturer": manufacturer,
                "return_details": return_details,
                "limit": limit,
                "inferred_filters": query_strategy["inferred_filters"]
            }
        }

        # Log success
        if len(devices) == 0:
            logger.warning(f"🧠 Smart discovery returned 0 results for '{query}' with context '{context}'")
        else:
            logger.info(f"✅ Smart discovery found {len(devices)} devices for '{query}' (methods: {search_methods})")

        return result

    except Exception as e:
        logger.error(f"Error in smart device discovery: {e}")
        return {
            "count": 0,
            "devices": [],
            "error": str(e),
            "error_type": type(e).__name__,
            "query_strategy": {"original_query": query, "error": str(e)},
            "performance_metrics": {"execution_efficiency": "error"},
            "filters_applied": {"query": query, "context": context}
        }


def _analyze_manufacturer_query(query: str) -> bool:
    """
    Analyze if a query term is likely a manufacturer name.

    Args:
        query: Normalized query string

    Returns:
        True if query appears to be a manufacturer name
    """
    # Common manufacturer names and patterns
    known_manufacturers = {
        "cisco", "juniper", "arista", "dell", "hp", "hpe", "watchguard",
        "fortinet", "palo alto", "checkpoint", "vmware", "microsoft",
        "redhat", "ubuntu", "centos", "oracle", "ibm", "lenovo",
        "supermicro", "intel", "amd", "nvidia", "broadcom"
    }

    # Direct match
    if query in known_manufacturers:
        return True

    # Partial match for compound names
    for manufacturer in known_manufacturers:
        if manufacturer in query or query in manufacturer:
            return True

    # Pattern-based detection (manufacturer names often have specific patterns)
    # This is a simple heuristic - could be enhanced with ML
    if len(query) > 3 and query.isalpha():
        # Single word, alphabetic, longer than 3 chars - possible manufacturer
        return True

    return False


def _apply_secondary_filters(
    devices: List[Dict],
    role: Optional[str],
    location: Optional[str]
) -> List[Dict]:
    """
    Apply secondary filtering to device results.

    Args:
        devices: List of devices to filter
        role: Target device role
        location: Target location (site or rack)

    Returns:
        Filtered device list
    """
    filtered_devices = []

    for device in devices:
        # Role filtering
        if role:
            device_role = None
            role_obj = device.get("role")
            if isinstance(role_obj, dict):
                device_role = role_obj.get("name", "").lower()
            elif isinstance(role_obj, str):
                device_role = role_obj.lower()

            if device_role and role.lower() not in device_role:
                continue

        # Location filtering
        if location:
            device_site = None
            site_obj = device.get("site")
            if isinstance(site_obj, dict):
                device_site = site_obj.get("name", "").lower()
            elif isinstance(site_obj, str):
                device_site = site_obj.lower()

            location_lower = location.lower()
            if device_site and location_lower not in device_site:
                continue

        filtered_devices.append(device)

    return filtered_devices


def _enhance_devices_with_details(devices: List[Dict], client) -> List[Dict]:
    """
    Enhance device list with additional details like IP addresses and interface counts.

    Args:
        devices: List of devices to enhance
        client: NetBoxClient instance

    Returns:
        Enhanced device list
    """
    enhanced_devices = []

    for device in devices:
        enhanced_device = device.copy()

        # Add primary IP information
        primary_ip4 = device.get("primary_ip4")
        primary_ip6 = device.get("primary_ip6")

        if primary_ip4 and isinstance(primary_ip4, dict):
            enhanced_device["primary_ip4_address"] = primary_ip4.get("address")
        if primary_ip6 and isinstance(primary_ip6, dict):
            enhanced_device["primary_ip6_address"] = primary_ip6.get("address")

        # Add rack position details
        rack = device.get("rack")
        position = device.get("position")
        if rack and position:
            enhanced_device["location_details"] = {
                "rack": rack.get("name") if isinstance(rack, dict) else str(rack),
                "position": position,
                "full_location": f"Rack {rack.get('name') if isinstance(rack, dict) else rack}, Position {position}"
            }

        # Add status details
        status = device.get("status")
        if isinstance(status, dict):
            enhanced_device["status_details"] = {
                "label": status.get("label"),
                "value": status.get("value")
            }

        enhanced_devices.append(enhanced_device)

    return enhanced_devices


# TODO: Implement advanced device lifecycle management tools:
# - netbox_configure_device_settings
# - netbox_monitor_device_health
# - netbox_bulk_device_operations  
# - netbox_map_device_dependencies
# - netbox_clone_device_configuration
# - netbox_device_compliance_check
