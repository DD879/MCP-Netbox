#\!/usr/bin/env python3
"""
DCIM Rack Management Tools

High-level tools for managing NetBox racks, rack units, rack elevations,
and rack capacity management with enterprise-grade functionality.
"""

from typing import Dict, Optional, Any
import logging
from ...registry import mcp_tool
from ...client import NetBoxClient

logger = logging.getLogger(__name__)


@mcp_tool(category="dcim")
def netbox_create_rack(
    client: NetBoxClient,
    name: str,
    site: str,
    u_height: int = 42,
    width: int = 19,
    status: str = "active",
    role: Optional[str] = None,
    facility_id: Optional[str] = None,
    description: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Create a new rack in NetBox DCIM.
    
    Args:
        client: NetBoxClient instance (injected)
        name: Rack name
        site: Site name or slug
        u_height: Height in rack units (1-100)
        width: Width in inches (10, 19, 21, 23)
        status: Rack status (active, planned, reserved, available, deprecated)
        role: Optional rack role
        facility_id: Facility identifier
        description: Optional description
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Created rack information or error details
        
    Example:
        netbox_create_rack("Rack-A01", "amsterdam-dc", u_height=42, confirm=True)
    """
    try:
        if not name or not site:
            return {
                "success": False,
                "error": "Rack name and site are required",
                "error_type": "ValidationError"
            }
        
        if not (1 <= u_height <= 100):
            return {
                "success": False,
                "error": "U-height must be between 1 and 100",
                "error_type": "ValidationError"
            }
        
        if width not in [10, 19, 21, 23]:
            return {
                "success": False,
                "error": "Width must be 10, 19, 21, or 23 inches",
                "error_type": "ValidationError"
            }
        
        logger.info(f"Creating rack: {name} at {site}")
        
        # Resolve site reference
        site_id = site
        if isinstance(site, str) and not site.isdigit():
            # ULTRATHINK FIX 1: Expand search parameters with comprehensive relationship data
            site_search_params = {
                "expand": ["region", "tenant"],
                "limit": 50
            }

            # ULTRATHINK FIX 2: ID resolution with fallback patterns
            sites = None
            if site.isdigit():
                sites = list(client.dcim.sites.filter(id=int(site), **site_search_params))

            if not sites:
                sites = list(client.dcim.sites.filter(slug=site, **site_search_params))

            # ULTRATHINK FIX 4: Name-based fallback
            if not sites:
                sites = list(client.dcim.sites.filter(name=site, **site_search_params))
            if sites:
                site_id = sites[0]["id"]
            else:
                return {
                    "success": False,
                    "error": f"Site '{site}' not found",
                    "error_type": "SiteNotFound"
                }
        
        # Build rack data
        rack_data = {
            "name": name,
            "site": site_id,
            "u_height": u_height,
            "width": width,
            "status": status
        }
        
        if role:
            rack_data["role"] = role
        if facility_id:
            rack_data["facility_id"] = facility_id
        if description:
            rack_data["description"] = description
        
        # Use dynamic API with safety
        result = client.dcim.racks.create(confirm=confirm, **rack_data)
        
        return {
            "success": True,
            "action": "created",
            "object_type": "rack",
            "rack": result,
            "dry_run": result.get("dry_run", False)
        }
        
    except Exception as e:
        logger.error(f"Failed to create rack {name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@mcp_tool(category="dcim")
def netbox_get_rack_elevation(
    client: NetBoxClient,
    rack_name: str,
    site: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get rack elevation showing device positions.
    
    Args:
        client: NetBoxClient instance (injected)
        rack_name: Name of the rack
        site: Optional site for filtering
        
    Returns:
        Rack elevation with device positions
        
    Example:
        netbox_get_rack_elevation("Rack-A01", site="amsterdam-dc")
    """
    try:
        logger.info(f"Getting rack elevation: {rack_name}")
        
        # Build filter
        rack_filter = {"name": rack_name}
        if site:
            rack_filter["site"] = site
        
        # Find the rack
        racks = client.dcim.racks.filter(**rack_filter)
        
        if not racks:
            return {
                "success": False,
                "error": f"Rack '{rack_name}' not found" + (f" in site '{site}'" if site else ""),
                "error_type": "RackNotFound"
            }
        
        rack = racks[0]
        rack_id = rack["id"]
        
        # Get devices in rack
        devices = client.dcim.devices.filter(rack_id=rack_id)
        
        # Build elevation map
        elevation = {}
        for device in devices:
            position = device.get("position")
            if position:
                # Handle device_type as either dict or int
                device_type_info = device.get("device_type", {})
                if isinstance(device_type_info, dict):
                    device_type_model = device_type_info.get("model", "Unknown")
                    device_u_height = device_type_info.get("u_height", 1)
                else:
                    # device_type is an ID, need to resolve it
                    device_type_model = "Unknown"
                    device_u_height = 1
                
                elevation[position] = {
                    "device": device["name"],
                    "device_type": device_type_model,
                    "u_height": device_u_height,
                    "face": device.get("face", "front")
                }
        
        # Calculate used units properly
        used_units = 0
        for device in devices:
            device_type_info = device.get("device_type", {})
            if isinstance(device_type_info, dict):
                used_units += device_type_info.get("u_height", 1)
            else:
                used_units += 1  # Default to 1U if we can't determine
        
        return {
            "success": True,
            "rack": rack,
            "device_count": len(devices),
            "available_units": rack["u_height"] - used_units,
            "elevation": elevation,
            "devices": devices
        }
        
    except Exception as e:
        logger.error(f"Failed to get rack elevation for {rack_name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


# ========================================
# HIGH-LEVEL DEVICE PROVISIONING TOOLS
# ========================================



@mcp_tool(category="dcim")
def netbox_get_rack_inventory(
    client: NetBoxClient,
    site_name: str,
    rack_name: str,
    include_detailed: bool = False
) -> Dict[str, Any]:
    """
    Generate a comprehensive, human-readable inventory report for all devices in a specific rack.
    
    This reporting tool transforms raw NetBox data into a clean, organized rack inventory
    that provides essential information for capacity planning and data center documentation.
    
    Args:
        client: NetBoxClient instance (injected)
        site_name: Name of the site containing the rack
        rack_name: Name of the rack to inventory
        include_detailed: Include detailed device information (interfaces, IPs, etc.)
        
    Returns:
        Comprehensive rack inventory with utilization statistics and device details
        
    Example:
        netbox_get_rack_inventory(
            site_name="Main DC",
            rack_name="R-12",
            include_detailed=True
        )
    """
    try:
        if not all([site_name, rack_name]):
            return {
                "success": False,
                "error": "site_name and rack_name are required",
                "error_type": "ValidationError"
            }
        
        logger.info(f"Generating rack inventory for {site_name}/{rack_name}")
        
        # Step 1: Find the site
        logger.debug(f"Looking up site: {site_name}")
        # ULTRATHINK FIX 1: Expand search parameters with comprehensive relationship data
        site_search_params = {
            "expand": ["region", "tenant"],
            "limit": 50
        }

        # ULTRATHINK FIX 2: ID resolution with fallback patterns
        sites = None
        if site_name.isdigit():
            sites = list(client.dcim.sites.filter(id=int(site_name), **site_search_params))

        if not sites:
            sites = list(client.dcim.sites.filter(name=site_name, **site_search_params))

        # ULTRATHINK FIX 4: Slug-based fallback
        if not sites:
            sites = list(client.dcim.sites.filter(slug=site_name, **site_search_params))
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
        # ULTRATHINK FIX 1: Expand search parameters for comprehensive rack data
        rack_search_params = {
            "expand": ["site", "tenant", "role"],
            "limit": 50
        }

        # ULTRATHINK FIX 2: ID resolution with fallback patterns for rack name
        racks = None
        if rack_name.isdigit():
            racks = list(client.dcim.racks.filter(site_id=site_id, id=int(rack_name), **rack_search_params))

        if not racks:
            racks = list(client.dcim.racks.filter(site_id=site_id, name=rack_name, **rack_search_params))
        if not racks:
            return {
                "success": False,
                "error": f"Rack '{rack_name}' not found in site '{site['name']}'",
                "error_type": "NotFoundError"
            }
        rack = racks[0]
        rack_id = rack["id"]
        rack_height = rack["u_height"]
        logger.debug(f"Found rack: {rack['name']} (ID: {rack_id}, Height: {rack_height}U)")
        
        # Step 3: Get all devices in this rack
        logger.debug(f"Retrieving all devices in rack {rack['name']}")
        devices = client.dcim.devices.filter(rack_id=rack_id)
        logger.debug(f"Found {len(devices)} devices in rack")
        
        # Step 4: Process devices and organize by position
        device_inventory = {}
        occupied_positions = set()
        
        for device in devices:
            position = device.get("position")
            device_type = device.get("device_type")
            
            if position is not None:
                # Get device type details
                device_type_info = None
                if device_type:
                    device_types = client.dcim.device_types.filter(id=device_type)
                    if device_types:
                        device_type_info = device_types[0]
                
                # Calculate device height and occupied positions (ensure integers)
                device_height = 1
                if device_type_info:
                    device_height = int(device_type_info.get("u_height", 1))
                
                # Ensure position is also an integer
                position = int(position)
                
                # Mark all positions occupied by this device
                for u in range(position, position + device_height):
                    occupied_positions.add(u)
                
                # Get role name (handle both ID and object formats)
                role_name = "Unknown"
                role_data = device.get("role")
                if role_data:
                    if isinstance(role_data, dict):
                        role_name = role_data.get("name", "Unknown")
                    else:
                        # If it's an ID, look up the role
                        try:
                            roles = client.dcim.device_roles.filter(id=role_data)
                            if roles:
                                role_name = roles[0].get("name", "Unknown")
                        except Exception as e:
                            logger.warning(f"Could not resolve role ID {role_data}: {e}")
                
                # Get manufacturer name safely
                manufacturer_name = "Unknown"
                if device_type_info:
                    manufacturer_data = device_type_info.get("manufacturer")
                    if isinstance(manufacturer_data, dict):
                        manufacturer_name = manufacturer_data.get("name", "Unknown")
                    elif manufacturer_data:
                        # If it's an ID, look up the manufacturer
                        try:
                            manufacturers = client.dcim.manufacturers.filter(id=manufacturer_data)
                            if manufacturers:
                                manufacturer_name = manufacturers[0].get("name", "Unknown")
                        except Exception as e:
                            logger.warning(f"Could not resolve manufacturer ID {manufacturer_data}: {e}")
                
                # Get IP addresses safely
                primary_ip4 = None
                primary_ip6 = None
                primary_ip4_data = device.get("primary_ip4")
                primary_ip6_data = device.get("primary_ip6")
                
                if primary_ip4_data:
                    if isinstance(primary_ip4_data, dict):
                        primary_ip4 = primary_ip4_data.get("address")
                    else:
                        # If it's an ID, we could look it up, but for now just note it exists
                        primary_ip4 = f"IP ID: {primary_ip4_data}"
                
                if primary_ip6_data:
                    if isinstance(primary_ip6_data, dict):
                        primary_ip6 = primary_ip6_data.get("address")
                    else:
                        primary_ip6 = f"IP ID: {primary_ip6_data}"
                
                # Basic device information
                device_info = {
                    "name": device.get("name", "Unknown"),
                    "position": position,
                    "height": device_height,
                    "device_type": device_type_info.get("model", "Unknown") if device_type_info else "Unknown",
                    "manufacturer": manufacturer_name,
                    "status": device.get("status", "unknown"),
                    "serial": device.get("serial", ""),
                    "asset_tag": device.get("asset_tag", ""),
                    "role": role_name,
                    "primary_ip": None,
                    "primary_ip4": primary_ip4,
                    "primary_ip6": primary_ip6
                }
                
                # Determine primary IP
                if device_info["primary_ip4"]:
                    device_info["primary_ip"] = device_info["primary_ip4"]
                elif device_info["primary_ip6"]:
                    device_info["primary_ip"] = device_info["primary_ip6"]
                
                # Add detailed information if requested
                if include_detailed:
                    device_info["detailed"] = {
                        "description": device.get("description", ""),
                        "platform": device.get("platform", {}).get("name") if device.get("platform") else None,
                        "tenant": device.get("tenant", {}).get("name") if device.get("tenant") else None,
                        "face": device.get("face", "front"),
                        "device_id": device.get("id"),
                        "url": device.get("url", ""),
                        "created": device.get("created", ""),
                        "last_updated": device.get("last_updated", "")
                    }
                    
                    # Get interface count
                    try:
                        interfaces = client.dcim.interfaces.filter(device_id=device["id"])
                        device_info["detailed"]["interface_count"] = len(interfaces)
                    except Exception as e:
                        logger.warning(f"Could not get interface count for device {device['name']}: {e}")
                        device_info["detailed"]["interface_count"] = 0
                
                device_inventory[position] = device_info
        
        # Step 5: Generate position map
        position_map = []
        for u in range(1, rack_height + 1):
            if u in occupied_positions:
                device = device_inventory.get(u)
                position_map.append({
                    "position": u,
                    "status": "occupied",
                    "device": device
                })
            else:
                position_map.append({
                    "position": u,
                    "status": "available",
                    "device": None
                })
        
        # Step 6: Calculate utilization statistics
        total_positions = rack_height
        occupied_count = len(occupied_positions)
        available_count = total_positions - occupied_count
        utilization_percent = (occupied_count / total_positions * 100) if total_positions > 0 else 0
        
        # Step 7: Sort devices by position (ascending - bottom to top)
        devices_by_position = sorted(device_inventory.values(), key=lambda d: d["position"])
        
        # Generate status overview
        status_counts = {}
        for device in devices_by_position:
            status = device.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "success": True,
            "rack_info": {
                "site": site["name"],
                "rack_name": rack["name"],
                "rack_height": rack_height,
                "rack_width": rack.get("width", 19),
                "rack_status": rack.get("status", "unknown"),
                "rack_description": rack.get("description", ""),
                "rack_id": rack_id,
                "rack_url": rack.get("url", "")
            },
            "utilization": {
                "total_positions": total_positions,
                "occupied_positions": occupied_count,
                "available_positions": available_count,
                "utilization_percentage": round(utilization_percent, 1),
                "device_count": len(devices)
            },
            "devices": devices_by_position,
            "position_map": sorted(position_map, key=lambda p: p["position"], reverse=True),  # Top to bottom view
            "summary": {
                "rack_location": f"{site['name']} > {rack['name']}",
                "capacity": f"{occupied_count}/{total_positions}U occupied ({utilization_percent:.1f}%)",
                "device_summary": f"{len(devices)} devices installed" if devices else "Rack is empty",
                "status_overview": status_counts
            },
            "detailed": include_detailed
        }
        
    except Exception as e:
        logger.error(f"Failed to generate rack inventory for {site_name}/{rack_name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }



@mcp_tool(category="dcim")
def netbox_list_all_racks(
    client: NetBoxClient,
    limit: int = 100,
    site_name: Optional[str] = None,
    tenant_name: Optional[str] = None,
    status: Optional[str] = None,
    role: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get summarized list of racks with optional filtering.
    
    This tool provides bulk rack discovery across the NetBox infrastructure,
    enabling efficient capacity management, data center optimization, and
    rack space planning. Essential for infrastructure capacity management.
    
    Args:
        client: NetBoxClient instance (injected by dependency system)
        limit: Maximum number of results to return (default: 100)
        site_name: Filter by site name (optional)
        tenant_name: Filter by tenant name (optional)
        status: Filter by rack status (optional)
        role: Filter by rack role (optional)
        
    Returns:
        Dictionary containing:
        - count: Total number of racks found
        - racks: List of summarized rack information
        - filters_applied: Dictionary of filters that were applied
        - summary_stats: Aggregate statistics about the racks
        
    Example:
        netbox_list_all_racks(site_name="datacenter-1", status="active")
        netbox_list_all_racks(tenant_name="customer-a", limit=25)
    """
    try:
        logger.info(f"Listing racks with filters - site: {site_name}, tenant: {tenant_name}, status: {status}, role: {role}")
        
        # Build filters dictionary - only include non-None values
        filters = {}
        if site_name:
            filters['site'] = site_name
        if tenant_name:
            filters['tenant'] = tenant_name
        if status:
            filters['status'] = status
        if role:
            filters['role'] = role
        
        # Execute filtered query with limit
        racks = list(client.dcim.racks.filter(**filters))
        
        # Apply limit after fetching
        if len(racks) > limit:
            racks = racks[:limit]
        
        # Generate summary statistics
        status_counts = {}
        site_counts = {}
        tenant_counts = {}
        role_counts = {}
        
        # Capacity tracking
        total_rack_units = 0
        total_occupied_units = 0
        total_devices = 0
        
        for rack in racks:
            # Status breakdown with defensive dictionary access
            status_obj = rack.get("status", {})
            if isinstance(status_obj, dict):
                status = status_obj.get("label", "N/A")
            else:
                status = str(status_obj) if status_obj else "N/A"
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Site breakdown with defensive dictionary access
            site_obj = rack.get("site")
            if site_obj:
                if isinstance(site_obj, dict):
                    site_name = site_obj.get("name", str(site_obj))
                else:
                    site_name = str(site_obj)
                site_counts[site_name] = site_counts.get(site_name, 0) + 1
            
            # Tenant breakdown with defensive dictionary access
            tenant_obj = rack.get("tenant")
            if tenant_obj:
                if isinstance(tenant_obj, dict):
                    tenant_name = tenant_obj.get("name", str(tenant_obj))
                else:
                    tenant_name = str(tenant_obj)
                tenant_counts[tenant_name] = tenant_counts.get(tenant_name, 0) + 1
            
            # Role breakdown with defensive dictionary access
            role_obj = rack.get("role")
            if role_obj:
                if isinstance(role_obj, dict):
                    role_name = role_obj.get("name", str(role_obj))
                else:
                    role_name = str(role_obj)
                role_counts[role_name] = role_counts.get(role_name, 0) + 1
            
            # Capacity calculations with defensive dictionary access
            rack_height = rack.get("u_height", 42)
            total_rack_units += rack_height
            
            # Get devices in this rack to calculate utilization
            rack_id = rack.get("id")
            rack_devices = list(client.dcim.devices.filter(rack_id=rack_id))
            total_devices += len(rack_devices)
            
            # Calculate occupied units with defensive dictionary access
            occupied_units = 0
            for device in rack_devices:
                position = device.get("position")
                if position:
                    device_height = 1  # Default device height
                    device_type_obj = device.get("device_type")
                    if device_type_obj:
                        if isinstance(device_type_obj, dict):
                            device_height = device_type_obj.get("u_height", 1)
                        else:
                            # device_type is an ID, look it up if needed
                            try:
                                device_type_details = client.dcim.device_types.get(device_type_obj)
                                if isinstance(device_type_details, dict):
                                    device_height = device_type_details.get("u_height", 1)
                            except:
                                pass  # Use default height if lookup fails
                    occupied_units += device_height
            
            total_occupied_units += occupied_units
        
        # Create human-readable rack list
        rack_list = []
        for rack in racks:
            # Get utilization details for this specific rack
            rack_id = rack.get("id")
            rack_devices = list(client.dcim.devices.filter(rack_id=rack_id))
            rack_height = rack.get("u_height", 42)
            
            # Calculate occupied units for this rack with defensive dictionary access
            occupied_units = 0
            for device in rack_devices:
                position = device.get("position")
                if position:
                    device_height = 1  # Default
                    device_type_obj = device.get("device_type")
                    if device_type_obj:
                        if isinstance(device_type_obj, dict):
                            device_height = device_type_obj.get("u_height", 1)
                        else:
                            # device_type is an ID, look it up if needed
                            try:
                                device_type_details = client.dcim.device_types.get(device_type_obj)
                                if isinstance(device_type_details, dict):
                                    device_height = device_type_details.get("u_height", 1)
                            except:
                                pass  # Use default height if lookup fails
                    occupied_units += device_height
            
            utilization_percent = (occupied_units / rack_height * 100) if rack_height > 0 else 0
            
            # Defensive dictionary access for all rack attributes
            site_obj = rack.get("site")
            site_name = None
            if site_obj:
                if isinstance(site_obj, dict):
                    site_name = site_obj.get("name")
                else:
                    site_name = str(site_obj)
            
            tenant_obj = rack.get("tenant")
            tenant_name = None
            if tenant_obj:
                if isinstance(tenant_obj, dict):
                    tenant_name = tenant_obj.get("name")
                else:
                    tenant_name = str(tenant_obj)
            
            status_obj = rack.get("status", {})
            if isinstance(status_obj, dict):
                status = status_obj.get("label", "N/A")
            else:
                status = str(status_obj) if status_obj else "N/A"
            
            role_obj = rack.get("role")
            role_name = None
            if role_obj:
                if isinstance(role_obj, dict):
                    role_name = role_obj.get("name")
                else:
                    role_name = str(role_obj)
            
            width_obj = rack.get("width")
            width = 19  # Default width
            if width_obj:
                if isinstance(width_obj, dict):
                    width = width_obj.get("value", 19)
                else:
                    width = width_obj if isinstance(width_obj, int) else 19
            
            location_obj = rack.get("location")
            location_name = None
            if location_obj:
                if isinstance(location_obj, dict):
                    location_name = location_obj.get("name")
                else:
                    location_name = str(location_obj)
            
            rack_info = {
                "name": rack.get("name", "Unknown"),
                "site": site_name,
                "tenant": tenant_name,
                "status": status,
                "role": role_name,
                "height_units": rack_height,
                "width": width,
                "device_count": len(rack_devices),
                "occupied_units": occupied_units,
                "available_units": rack_height - occupied_units,
                "utilization_percent": round(utilization_percent, 1),
                "description": rack.get("description"),
                "location": location_name,
                "facility_id": rack.get("facility_id")
            }
            rack_list.append(rack_info)
        
        # Calculate overall utilization
        overall_utilization = (total_occupied_units / total_rack_units * 100) if total_rack_units > 0 else 0
        
        result = {
            "count": len(rack_list),
            "racks": rack_list,
            "filters_applied": {k: v for k, v in filters.items() if v is not None},
            "summary_stats": {
                "total_racks": len(rack_list),
                "status_breakdown": status_counts,
                "site_breakdown": site_counts,
                "tenant_breakdown": tenant_counts,
                "role_breakdown": role_counts,
                "capacity_overview": {
                    "total_rack_units": total_rack_units,
                    "total_occupied_units": total_occupied_units,
                    "total_available_units": total_rack_units - total_occupied_units,
                    "overall_utilization_percent": round(overall_utilization, 1),
                    "total_devices": total_devices,
                    "average_devices_per_rack": round(total_devices / len(rack_list), 1) if rack_list else 0
                },
                "racks_with_devices": len([r for r in rack_list if r['device_count'] > 0]),
                "racks_with_tenants": len([r for r in rack_list if r['tenant']]),
                "highly_utilized_racks": len([r for r in rack_list if r['utilization_percent'] > 80])
            }
        }
        
        logger.info(f"Found {len(rack_list)} racks matching criteria. Overall utilization: {overall_utilization:.1f}%")
        return result
        
    except Exception as e:
        logger.error(f"Error listing racks: {e}")
        return {
            "count": 0,
            "racks": [],
            "error": str(e),
            "error_type": type(e).__name__,
            "filters_applied": {k: v for k, v in {
                'site_name': site_name,
                'tenant_name': tenant_name,
                'status': status,
                'role': role
            }.items() if v is not None}
        }


# TODO: Implement advanced rack management tools:
# - netbox_plan_rack_capacity
# - netbox_manage_rack_power_cooling
# - netbox_optimize_rack_space  
# - netbox_bulk_rack_operations
# - netbox_report_rack_utilization
