#!/usr/bin/env python3
"""
DCIM Power Ports Management Tools

This module provides enterprise-grade tools for managing NetBox power ports
including creation, updates, deletion, and information retrieval.
"""

from typing import Dict, Any, Optional, List
import logging

from src.registry import mcp_tool
from src.client import NetBoxClient
from src.exceptions import NetBoxValidationError, NetBoxNotFoundError, NetBoxConflictError

logger = logging.getLogger(__name__)


@mcp_tool(category="dcim")
def netbox_create_power_port(
    client: NetBoxClient,
    name: str,
    device_name: str,
    site: str,
    port_type: str = "iec-60320-c14",
    maximum_draw: Optional[int] = None,
    allocated_draw: Optional[int] = None,
    description: Optional[str] = None,
    mark_connected: bool = False,
    tags: Optional[List[str]] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Create a new power port in NetBox.
    
    This enterprise-grade function creates power ports for devices that
    consume power from power outlets and feeds.
    
    Args:
        name: Power port name/identifier
        device_name: Device name where port is located (foreign key resolved)
        site: Site name for device validation (foreign key resolved)
        port_type: Port type (iec-60320-c14, iec-60320-c20, nema-5-15p, etc.)
        maximum_draw: Maximum power draw in watts (optional)
        allocated_draw: Allocated power draw in watts (optional)
        description: Port description
        mark_connected: Mark port as connected
        tags: List of tags to assign
        client: NetBox client (injected)
        confirm: Must be True to execute
        
    Returns:
        Dict containing operation result and power port details
        
    Examples:
        # Dry run
        netbox_create_power_port("PSU1", "server-01", "datacenter-1")
        
        # Create port with power specifications
        netbox_create_power_port("PSU1", "server-01", "datacenter-1",
                                maximum_draw=800, allocated_draw=600, confirm=True)
    """
    
    # DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Power port would be created. Set confirm=True to execute.",
            "would_create": {
                "name": name,
                "device_name": device_name,
                "site": site,
                "type": port_type,
                "maximum_draw": maximum_draw,
                "allocated_draw": allocated_draw,
                "description": description,
                "mark_connected": mark_connected,
                "tags": tags
            }
        }
    
    # PARAMETER VALIDATION
    if not name or not name.strip():
        raise NetBoxValidationError("Power port name cannot be empty")
    
    if not device_name or not device_name.strip():
        raise NetBoxValidationError("Device name is required for power port creation")
    
    if not site or not site.strip():
        raise NetBoxValidationError("Site is required for power port creation")
    
    # Validate port type (common types)
    valid_types = [
        "iec-60320-c6", "iec-60320-c8", "iec-60320-c14", "iec-60320-c16", 
        "iec-60320-c20", "iec-60320-c22", "iec-60309-p-n-e-4h", "iec-60309-p-n-e-6h", 
        "iec-60309-2p-e-4h", "iec-60309-2p-e-6h", "iec-60309-3p-e-4h", "iec-60309-3p-e-6h",
        "iec-60309-3p-n-e-4h", "iec-60309-3p-n-e-6h", "nema-1-15p", "nema-5-15p", 
        "nema-5-20p", "nema-5-30p", "nema-5-50p", "nema-6-15p", "nema-6-20p", 
        "nema-6-30p", "nema-6-50p", "nema-10-30p", "nema-10-50p", "nema-14-20p", 
        "nema-14-30p", "nema-14-50p", "nema-14-60p", "nema-15-15p", "nema-15-20p", 
        "nema-15-30p", "nema-15-50p", "nema-15-60p", "nema-l1-15p", "nema-l5-15p", 
        "nema-l5-20p", "nema-l5-30p", "nema-l5-50p", "nema-l6-15p", "nema-l6-20p", 
        "nema-l6-30p", "nema-l6-50p", "nema-l10-30p", "nema-l14-20p", "nema-l14-30p", 
        "nema-l15-20p", "nema-l15-30p", "nema-l21-20p", "nema-l21-30p", "nema-l22-30p"
    ]
    
    if port_type not in valid_types:
        logger.warning(f"Port type '{port_type}' may not be valid. Common types: {', '.join(valid_types[:10])}...")
    
    # Validate power values
    if maximum_draw is not None and maximum_draw < 0:
        raise NetBoxValidationError("Maximum draw cannot be negative")
    
    if allocated_draw is not None and allocated_draw < 0:
        raise NetBoxValidationError("Allocated draw cannot be negative")
    
    if maximum_draw is not None and allocated_draw is not None and allocated_draw > maximum_draw:
        raise NetBoxValidationError("Allocated draw cannot exceed maximum draw")
    
    # LOOKUP SITE (with defensive dict/object handling)
    try:
        # ULTRATHINK FIX 1: Expand search parameters with comprehensive relationship data\n        site_search_params = {\n            \"expand\": [\"region\", \"tenant\"],\n            \"limit\": 50\n        }\n\n        # ULTRATHINK FIX 2: ID resolution with fallback patterns\n        sites = None\n        if site.isdigit():\n            sites = list(client.dcim.sites.filter(id=int(site), **site_search_params))\n\n        if not sites:\n            sites = list(client.dcim.sites.filter(name=site, **site_search_params))\n\n        # ULTRATHINK FIX 4: Slug-based fallback mechanisms\n        if not sites:\n            sites = list(client.dcim.sites.filter(slug=site, **site_search_params))
        if not sites:
            raise NetBoxNotFoundError(f"Site '{site}' not found")
        
        site_obj = sites[0]
        site_id = site_obj.get('id') if isinstance(site_obj, dict) else site_obj.id
        site_display = site_obj.get('display', site) if isinstance(site_obj, dict) else getattr(site_obj, 'display', site)
        
    except Exception as e:
        raise NetBoxNotFoundError(f"Could not find site '{site}': {e}")
    
    # LOOKUP DEVICE (with site validation)
    try:
        # ULTRATHINK FIX 1: Expand search parameters with comprehensive relationship data\n        device_search_params = {\n            \"expand\": [\"device_type\", \"device_type__manufacturer\", \"site\", \"rack\", \"tenant\", \"role\"],\n            \"limit\": 50\n        }\n\n        # ULTRATHINK FIX 2: ID resolution with fallback patterns\n        devices = None\n        if device_name.isdigit():\n            devices = list(client.dcim.devices.filter(site_id=site_id, id=int(device_name), **device_search_params))\n\n        if not devices:\n            devices = list(client.dcim.devices.filter(site_id=site_id, name=device_name, **device_search_params))\n\n        # ULTRATHINK FIX 4: Slug-based fallback mechanisms\n        if not devices:\n            devices = list(client.dcim.devices.filter(site_id=site_id, name__icontains=device_name, **device_search_params))
        if not devices:
            raise NetBoxNotFoundError(f"Device '{device_name}' not found in site '{site}'")
        
        device_obj = devices[0]
        device_id = device_obj.get('id') if isinstance(device_obj, dict) else device_obj.id
        device_display = device_obj.get('display', device_name) if isinstance(device_obj, dict) else getattr(device_obj, 'display', device_name)
        
    except Exception as e:
        raise NetBoxValidationError(f"Failed to resolve device '{device_name}': {e}")
    
    # CONFLICT DETECTION
    try:
        existing_ports = client.dcim.power_ports.filter(
            device_id=device_id,
            name=name,
            no_cache=True
        )
        
        if existing_ports:
            existing_port = existing_ports[0]
            existing_id = existing_port.get('id') if isinstance(existing_port, dict) else existing_port.id
            raise NetBoxConflictError(
                resource_type="Power Port",
                identifier=f"{name} on device {device_name}",
                existing_id=existing_id
            )
    except NetBoxConflictError:
        raise
    except Exception as e:
        logger.warning(f"Could not check for existing power ports: {e}")
    
    # CREATE POWER PORT
    create_payload = {
        "name": name,
        "device": device_id,
        "type": port_type,
        "description": description or ""
    }
    
    # Add optional power specifications
    if maximum_draw is not None:
        create_payload["maximum_draw"] = maximum_draw
    if allocated_draw is not None:
        create_payload["allocated_draw"] = allocated_draw
    if mark_connected:
        create_payload["mark_connected"] = mark_connected
    if tags:
        create_payload["tags"] = tags
    
    try:
        logger.debug(f"Creating power port with payload: {create_payload}")
        new_port = client.dcim.power_ports.create(confirm=confirm, **create_payload)
        port_id = new_port.get('id') if isinstance(new_port, dict) else new_port.id
        
    except Exception as e:
        raise NetBoxValidationError(f"NetBox API error during power port creation: {e}")
    
    # RETURN SUCCESS
    return {
        "success": True,
        "message": f"Power port '{name}' successfully created on device '{device_name}'.",
        "data": {
            "port_id": port_id,
            "port_name": new_port.get('name') if isinstance(new_port, dict) else new_port.name,
            "device_id": device_id,
            "device_name": device_name,
            "site_id": site_id,
            "site_name": site,
            "type": port_type,
            "maximum_draw": maximum_draw,
            "allocated_draw": allocated_draw,
            "url": f"{client.config.url}/dcim/power-ports/{port_id}/"
        }
    }


@mcp_tool(category="dcim")
def netbox_get_power_port_info(
    client: NetBoxClient,
    port_identifier: str,
    device_name: Optional[str] = None,
    site: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get detailed information about a specific power port.
    
    This inspection tool provides comprehensive power port details including
    power specifications, connection status, and related device information.
    
    Args:
        port_identifier: Power port name or ID
        device_name: Device name for port lookup (improves search accuracy)
        site: Site name for device lookup (improves search accuracy)
        client: NetBox client (injected)
        
    Returns:
        Dict containing detailed power port information
        
    Examples:
        # Search by name
        netbox_get_power_port_info("PSU1")
        
        # Search with device context
        netbox_get_power_port_info("PSU1", device_name="server-01")
        
        # Search with full context
        netbox_get_power_port_info("PSU1", device_name="server-01", site="datacenter-1")
    """
    
    # LOOKUP POWER PORT
    try:
        # Try lookup by ID first
        if port_identifier.isdigit():
            port_id = int(port_identifier)
            # ULTRATHINK FIX 1: Add expand parameters for power port lookups\n            power_port_search_params = {\n                \"expand\": [\"device\", \"cable\"],\n                \"limit\": 50\n            }\n            ports = list(client.dcim.power_ports.filter(id=port_id, **power_port_search_params))
        else:
            # Search by name with optional device/site context
            filter_params = {"name": port_identifier}
            
            if device_name:
                # Resolve device
                device_filter = {"name": device_name}
                if site:
                    # ULTRATHINK FIX 1: Expand search parameters with comprehensive relationship data\n        site_search_params = {\n            \"expand\": [\"region\", \"tenant\"],\n            \"limit\": 50\n        }\n\n        # ULTRATHINK FIX 2: ID resolution with fallback patterns\n        sites = None\n        if site.isdigit():\n            sites = list(client.dcim.sites.filter(id=int(site), **site_search_params))\n\n        if not sites:\n            sites = list(client.dcim.sites.filter(name=site, **site_search_params))\n\n        # ULTRATHINK FIX 4: Slug-based fallback mechanisms\n        if not sites:\n            sites = list(client.dcim.sites.filter(slug=site, **site_search_params))
                    if sites:
                        site_obj = sites[0]
                        site_id = site_obj.get('id') if isinstance(site_obj, dict) else site_obj.id
                        device_filter["site_id"] = site_id
                
                # ULTRATHINK FIX 1: Add expand parameters to dynamic device filter\n                if 'expand' not in device_filter:\n                    device_filter['expand'] = [\"device_type\", \"device_type__manufacturer\", \"site\", \"rack\", \"tenant\", \"role\"]\n                if 'limit' not in device_filter:\n                    device_filter['limit'] = 50\n                devices = list(client.dcim.devices.filter(**device_filter))"
                if devices:
                    device_obj = devices[0]
                    device_id = device_obj.get('id') if isinstance(device_obj, dict) else device_obj.id
                    filter_params["device_id"] = device_id
            
            # ULTRATHINK FIX 1: Add expand parameters to dynamic power port filter\n            if 'expand' not in filter_params:\n                filter_params['expand'] = [\"device\", \"cable\"]\n            if 'limit' not in filter_params:\n                filter_params['limit'] = 50\n            ports = list(client.dcim.power_ports.filter(**filter_params))
        
        if not ports:
            identifier_desc = f"power port '{port_identifier}'"
            if device_name:
                identifier_desc += f" on device '{device_name}'"
            if site:
                identifier_desc += f" in site '{site}'"
            raise NetBoxNotFoundError(f"Could not find {identifier_desc}")
        
        port = ports[0]
        port_id = port.get('id') if isinstance(port, dict) else port.id
        port_name = port.get('name') if isinstance(port, dict) else port.name
        
    except Exception as e:
        raise NetBoxNotFoundError(f"Failed to find power port: {e}")
    
    # GET CABLE CONNECTION
    cable_info = {}
    try:
        cable_data = port.get('cable') if isinstance(port, dict) else getattr(port, 'cable', None)
        if cable_data:
            cable_info = {
                "id": cable_data.get('id') if isinstance(cable_data, dict) else getattr(cable_data, 'id', None),
                "label": cable_data.get('label') if isinstance(cable_data, dict) else getattr(cable_data, 'label', None),
                "status": cable_data.get('status', {}).get('label') if isinstance(cable_data, dict) else str(getattr(cable_data, 'status', 'N/A')),
                "type": cable_data.get('type', {}).get('label') if isinstance(cable_data, dict) else str(getattr(cable_data, 'type', 'N/A'))
            }
    except Exception as e:
        logger.warning(f"Could not retrieve cable information for port {port_id}: {e}")
    
    # GET DEVICE INFORMATION
    device_info = {}
    try:
        device_data = port.get('device') if isinstance(port, dict) else getattr(port, 'device', None)
        if device_data:
            device_info = {
                "id": device_data.get('id') if isinstance(device_data, dict) else getattr(device_data, 'id', None),
                "name": device_data.get('name') if isinstance(device_data, dict) else getattr(device_data, 'name', None),
                "display": device_data.get('display') if isinstance(device_data, dict) else getattr(device_data, 'display', None),
                "device_type": device_data.get('device_type', {}).get('display') if isinstance(device_data, dict) else str(getattr(device_data, 'device_type', 'N/A'))
            }
    except Exception as e:
        logger.warning(f"Could not retrieve device information for port {port_id}: {e}")
    
    # GET POWER SPECIFICATIONS
    power_specs = {}
    try:
        power_specs = {
            "maximum_draw": port.get('maximum_draw') if isinstance(port, dict) else getattr(port, 'maximum_draw', None),
            "allocated_draw": port.get('allocated_draw') if isinstance(port, dict) else getattr(port, 'allocated_draw', None),
            "type": port.get('type', {}).get('label') if isinstance(port, dict) else str(getattr(port, 'type', 'N/A'))
        }
    except Exception as e:
        logger.warning(f"Could not retrieve power specifications for port {port_id}: {e}")
    
    # RETURN COMPREHENSIVE INFORMATION
    return {
        "success": True,
        "data": {
            "port_id": port_id,
            "name": port_name,
            "device": device_info,
            "power_specifications": power_specs,
            "cable_connection": cable_info if cable_info else None,
            "description": port.get('description') if isinstance(port, dict) else getattr(port, 'description', ''),
            "tags": port.get('tags', []) if isinstance(port, dict) else getattr(port, 'tags', []),
            "mark_connected": port.get('mark_connected') if isinstance(port, dict) else getattr(port, 'mark_connected', False),
            "created": port.get('created') if isinstance(port, dict) else getattr(port, 'created', None),
            "last_updated": port.get('last_updated') if isinstance(port, dict) else getattr(port, 'last_updated', None),
            "url": f"{client.config.url}/dcim/power-ports/{port_id}/"
        }
    }


@mcp_tool(category="dcim")
def netbox_list_all_power_ports(
    client: NetBoxClient,
    device_name: Optional[str] = None,
    site: Optional[str] = None,
    port_type: Optional[str] = None,
    connected: Optional[bool] = None,
    limit: int = 50
) -> Dict[str, Any]:
    """
    List all power ports with optional filtering.
    
    This bulk discovery tool helps explore and analyze power consumption
    infrastructure across devices and sites.
    
    Args:
        device_name: Filter by device name (optional)
        site: Filter by site name (optional)
        port_type: Filter by port type (optional)
        connected: Filter by connection status (optional)
        limit: Maximum number of ports to return (default: 50)
        client: NetBox client (injected)
        
    Returns:
        Dict containing list of power ports with summary statistics
        
    Examples:
        # List all ports
        netbox_list_all_power_ports()
        
        # Filter by device
        netbox_list_all_power_ports(device_name="server-01")
        
        # Filter by site and connection status
        netbox_list_all_power_ports(site="datacenter-1", connected=True)
    """
    
    filter_params = {}
    
    # RESOLVE SITE FILTER
    if site:
        try:
            # ULTRATHINK FIX 1: Expand search parameters with comprehensive relationship data\n        site_search_params = {\n            \"expand\": [\"region\", \"tenant\"],\n            \"limit\": 50\n        }\n\n        # ULTRATHINK FIX 2: ID resolution with fallback patterns\n        sites = None\n        if site.isdigit():\n            sites = list(client.dcim.sites.filter(id=int(site), **site_search_params))\n\n        if not sites:\n            sites = list(client.dcim.sites.filter(name=site, **site_search_params))\n\n        # ULTRATHINK FIX 4: Slug-based fallback mechanisms\n        if not sites:\n            sites = list(client.dcim.sites.filter(slug=site, **site_search_params))
            if sites:
                site_obj = sites[0]
                site_id = site_obj.get('id') if isinstance(site_obj, dict) else site_obj.id
                filter_params["site_id"] = site_id
            else:
                return {
                    "success": True,
                    "data": {
                        "ports": [],
                        "total_count": 0,
                        "message": f"No ports found - site '{site}' not found"
                    }
                }
        except Exception as e:
            logger.warning(f"Could not resolve site filter '{site}': {e}")
    
    # RESOLVE DEVICE FILTER
    if device_name:
        try:
            device_filter = {"name": device_name}
            if "site_id" in filter_params:
                device_filter["site_id"] = filter_params["site_id"]
            
            devices = client.dcim.devices.filter(**device_filter)
            if devices:
                device_obj = devices[0]
                device_id = device_obj.get('id') if isinstance(device_obj, dict) else device_obj.id
                filter_params["device_id"] = device_id
            else:
                return {
                    "success": True,
                    "data": {
                        "ports": [],
                        "total_count": 0,
                        "message": f"No ports found - device '{device_name}' not found"
                    }
                }
        except Exception as e:
            logger.warning(f"Could not resolve device filter '{device_name}': {e}")
    
    # ADD OTHER FILTERS
    if port_type:
        filter_params["type"] = port_type
    
    if connected is not None:
        filter_params["cabled"] = connected
    
    # GET POWER PORTS
    try:
        # ULTRATHINK FIX 1: Add expand parameters to power port filter\n        if 'expand' not in filter_params:\n            filter_params['expand'] = [\"device\", \"cable\"]\n        if 'limit' not in filter_params:\n            filter_params['limit'] = 100\n        ports = list(client.dcim.power_ports.filter(**filter_params))
        total_count = len(ports)
        
        # Apply limit
        limited_ports = ports[:limit]
        
        ports_data = []
        power_stats = {"total_draw": 0, "allocated_draw": 0, "connected_count": 0}
        
        for port in limited_ports:
            try:
                # Get basic port info
                port_id = port.get('id') if isinstance(port, dict) else port.id
                port_name = port.get('name') if isinstance(port, dict) else port.name
                
                # Get device info
                device_data = port.get('device') if isinstance(port, dict) else getattr(port, 'device', {})
                device_name = device_data.get('name') if isinstance(device_data, dict) else getattr(device_data, 'name', 'N/A')
                
                # Get site info through device
                site_data = device_data.get('site') if isinstance(device_data, dict) else getattr(device_data, 'site', {})
                site_name = site_data.get('name') if isinstance(site_data, dict) else getattr(site_data, 'name', 'N/A')
                
                # Get power specifications
                max_draw = port.get('maximum_draw') if isinstance(port, dict) else getattr(port, 'maximum_draw', None)
                alloc_draw = port.get('allocated_draw') if isinstance(port, dict) else getattr(port, 'allocated_draw', None)
                
                if max_draw:
                    power_stats["total_draw"] += max_draw
                if alloc_draw:
                    power_stats["allocated_draw"] += alloc_draw
                
                # Check connection status
                cable_data = port.get('cable') if isinstance(port, dict) else getattr(port, 'cable', None)
                is_connected = cable_data is not None
                if is_connected:
                    power_stats["connected_count"] += 1
                
                # Get port type
                type_data = port.get('type') if isinstance(port, dict) else getattr(port, 'type', {})
                port_type_label = type_data.get('label') if isinstance(type_data, dict) else str(type_data)
                
                port_info = {
                    "id": port_id,
                    "name": port_name,
                    "device": device_name,
                    "site": site_name,
                    "type": port_type_label,
                    "power": {
                        "maximum_draw": max_draw,
                        "allocated_draw": alloc_draw
                    },
                    "connected": is_connected,
                    "url": f"{client.config.url}/dcim/power-ports/{port_id}/"
                }
                
                ports_data.append(port_info)
                
            except Exception as e:
                logger.warning(f"Error processing port data: {e}")
                continue
        
        # Build filter description
        filter_description = []
        if device_name:
            filter_description.append(f"device: {device_name}")
        if site:
            filter_description.append(f"site: {site}")
        if port_type:
            filter_description.append(f"type: {port_type}")
        if connected is not None:
            filter_description.append(f"connected: {connected}")
        
        filter_text = f" (filtered by {', '.join(filter_description)})" if filter_description else ""
        
        return {
            "success": True,
            "data": {
                "ports": ports_data,
                "total_count": total_count,
                "returned_count": len(ports_data),
                "limit_applied": limit if total_count > limit else None,
                "filters": filter_text,
                "statistics": {
                    "total_maximum_draw_watts": power_stats["total_draw"],
                    "total_allocated_draw_watts": power_stats["allocated_draw"],
                    "connected_ports": power_stats["connected_count"],
                    "disconnected_ports": len(ports_data) - power_stats["connected_count"],
                    "average_max_draw_per_port": round(power_stats["total_draw"] / len(ports_data), 1) if ports_data and power_stats["total_draw"] > 0 else 0
                }
            }
        }
        
    except Exception as e:
        raise NetBoxValidationError(f"Failed to retrieve power ports: {e}")


@mcp_tool(category="dcim")
def netbox_update_power_port(
    client: NetBoxClient,
    port_identifier: str,
    device_name: Optional[str] = None,
    site: Optional[str] = None,
    new_name: Optional[str] = None,
    port_type: Optional[str] = None,
    maximum_draw: Optional[int] = None,
    allocated_draw: Optional[int] = None,
    description: Optional[str] = None,
    mark_connected: Optional[bool] = None,
    tags: Optional[List[str]] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Update an existing power port.
    
    This enterprise-grade function updates power port configuration
    with comprehensive validation and safety checks.
    
    Args:
        port_identifier: Power port name or ID to update
        device_name: Device name for port lookup (improves search accuracy)
        site: Site name for device lookup (improves search accuracy)
        new_name: New name for the power port (optional)
        port_type: Update port type (optional)
        maximum_draw: Update maximum power draw in watts (optional)
        allocated_draw: Update allocated power draw in watts (optional)
        description: Update description (optional)
        mark_connected: Update connection marking (optional)
        tags: Update tags list (optional)
        client: NetBox client (injected)
        confirm: Must be True to execute
        
    Returns:
        Dict containing operation result and updated port details
        
    Examples:
        # Dry run update
        netbox_update_power_port("PSU1", device_name="server-01", maximum_draw=1000)
        
        # Update with confirmation
        netbox_update_power_port("PSU1", device_name="server-01", 
                                maximum_draw=1000, allocated_draw=800, confirm=True)
    """
    
    # DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Power port would be updated. Set confirm=True to execute.",
            "would_update": {
                "port_identifier": port_identifier,
                "device_name": device_name,
                "site": site,
                "new_name": new_name,
                "port_type": port_type,
                "maximum_draw": maximum_draw,
                "allocated_draw": allocated_draw,
                "description": description,
                "mark_connected": mark_connected,
                "tags": tags
            }
        }
    
    # FIND EXISTING POWER PORT
    try:
        # Try lookup by ID first
        if port_identifier.isdigit():
            port_id = int(port_identifier)
            # ULTRATHINK FIX 1: Add expand parameters for power port lookups\n            power_port_search_params = {\n                \"expand\": [\"device\", \"cable\"],\n                \"limit\": 50\n            }\n            ports = list(client.dcim.power_ports.filter(id=port_id, **power_port_search_params))
        else:
            # Search by name with optional device/site context
            filter_params = {"name": port_identifier}
            
            if device_name:
                device_filter = {"name": device_name}
                if site:
                    # ULTRATHINK FIX 1: Expand search parameters with comprehensive relationship data\n        site_search_params = {\n            \"expand\": [\"region\", \"tenant\"],\n            \"limit\": 50\n        }\n\n        # ULTRATHINK FIX 2: ID resolution with fallback patterns\n        sites = None\n        if site.isdigit():\n            sites = list(client.dcim.sites.filter(id=int(site), **site_search_params))\n\n        if not sites:\n            sites = list(client.dcim.sites.filter(name=site, **site_search_params))\n\n        # ULTRATHINK FIX 4: Slug-based fallback mechanisms\n        if not sites:\n            sites = list(client.dcim.sites.filter(slug=site, **site_search_params))
                    if sites:
                        site_obj = sites[0]
                        site_id = site_obj.get('id') if isinstance(site_obj, dict) else site_obj.id
                        device_filter["site_id"] = site_id
                
                # ULTRATHINK FIX 1: Add expand parameters to dynamic device filter\n                if 'expand' not in device_filter:\n                    device_filter['expand'] = [\"device_type\", \"device_type__manufacturer\", \"site\", \"rack\", \"tenant\", \"role\"]\n                if 'limit' not in device_filter:\n                    device_filter['limit'] = 50\n                devices = list(client.dcim.devices.filter(**device_filter))"
                if devices:
                    device_obj = devices[0]
                    device_id = device_obj.get('id') if isinstance(device_obj, dict) else device_obj.id
                    filter_params["device_id"] = device_id
            
            # ULTRATHINK FIX 1: Add expand parameters to dynamic power port filter\n            if 'expand' not in filter_params:\n                filter_params['expand'] = [\"device\", \"cable\"]\n            if 'limit' not in filter_params:\n                filter_params['limit'] = 50\n            ports = list(client.dcim.power_ports.filter(**filter_params))
        
        if not ports:
            identifier_desc = f"power port '{port_identifier}'"
            if device_name:
                identifier_desc += f" on device '{device_name}'"
            if site:
                identifier_desc += f" in site '{site}'"
            raise NetBoxNotFoundError(f"Could not find {identifier_desc}")
        
        existing_port = ports[0]
        port_id = existing_port.get('id') if isinstance(existing_port, dict) else existing_port.id
        current_name = existing_port.get('name') if isinstance(existing_port, dict) else existing_port.name
        
    except Exception as e:
        raise NetBoxNotFoundError(f"Failed to find power port: {e}")
    
    # BUILD UPDATE PAYLOAD
    update_payload = {}
    
    # Handle name update
    if new_name:
        if not new_name.strip():
            raise NetBoxValidationError("New power port name cannot be empty")
        update_payload["name"] = new_name.strip()
    
    # Handle type update
    if port_type:
        update_payload["type"] = port_type
    
    # Handle power specifications
    if maximum_draw is not None:
        if maximum_draw < 0:
            raise NetBoxValidationError("Maximum draw cannot be negative")
        update_payload["maximum_draw"] = maximum_draw
    
    if allocated_draw is not None:
        if allocated_draw < 0:
            raise NetBoxValidationError("Allocated draw cannot be negative")
        update_payload["allocated_draw"] = allocated_draw
    
    # Validate power relationship
    if maximum_draw is not None and allocated_draw is not None:
        if allocated_draw > maximum_draw:
            raise NetBoxValidationError("Allocated draw cannot exceed maximum draw")
    elif maximum_draw is not None:
        # Check against existing allocated draw
        existing_allocated = existing_port.get('allocated_draw') if isinstance(existing_port, dict) else getattr(existing_port, 'allocated_draw', None)
        if existing_allocated and existing_allocated > maximum_draw:
            raise NetBoxValidationError(f"Maximum draw ({maximum_draw}W) cannot be less than existing allocated draw ({existing_allocated}W)")
    elif allocated_draw is not None:
        # Check against existing maximum draw
        existing_maximum = existing_port.get('maximum_draw') if isinstance(existing_port, dict) else getattr(existing_port, 'maximum_draw', None)
        if existing_maximum and allocated_draw > existing_maximum:
            raise NetBoxValidationError(f"Allocated draw ({allocated_draw}W) cannot exceed existing maximum draw ({existing_maximum}W)")
    
    # Handle other updates
    if description is not None:
        update_payload["description"] = description
    
    if mark_connected is not None:
        update_payload["mark_connected"] = mark_connected
    
    if tags is not None:
        update_payload["tags"] = tags
    
    # Check if any updates provided
    if not update_payload:
        raise NetBoxValidationError("No update parameters provided")
    
    # CONFLICT DETECTION (if name is being changed)
    if "name" in update_payload:
        try:
            # Get device ID from existing port
            device_data = existing_port.get('device') if isinstance(existing_port, dict) else getattr(existing_port, 'device', {})
            device_id = device_data.get('id') if isinstance(device_data, dict) else getattr(device_data, 'id', None)
            
            if device_id:
                existing_ports = client.dcim.power_ports.filter(
                    device_id=device_id,
                    name=update_payload["name"],
                    no_cache=True
                )
                
                # Check if found port is different from current port
                for existing in existing_ports:
                    existing_id = existing.get('id') if isinstance(existing, dict) else existing.id
                    if existing_id != port_id:
                        raise NetBoxConflictError(
                            resource_type="Power Port",
                            identifier=f"{update_payload['name']} on same device",
                            existing_id=existing_id
                        )
        except NetBoxConflictError:
            raise
        except Exception as e:
            logger.warning(f"Could not check for naming conflicts: {e}")
    
    # PERFORM UPDATE
    try:
        logger.debug(f"Updating power port {port_id} with payload: {update_payload}")
        updated_port = client.dcim.power_ports.update(port_id, confirm=confirm, **update_payload)
        updated_name = updated_port.get('name') if isinstance(updated_port, dict) else updated_port.name
        
    except Exception as e:
        raise NetBoxValidationError(f"NetBox API error during power port update: {e}")
    
    # RETURN SUCCESS
    return {
        "success": True,
        "message": f"Power port successfully updated from '{current_name}' to '{updated_name}'.",
        "data": {
            "port_id": port_id,
            "old_name": current_name,
            "new_name": updated_name,
            "updates_applied": list(update_payload.keys()),
            "url": f"{client.config.url}/dcim/power-ports/{port_id}/"
        }
    }


@mcp_tool(category="dcim")
def netbox_delete_power_port(
    client: NetBoxClient,
    port_identifier: str,
    device_name: Optional[str] = None,
    site: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Delete a power port from NetBox.
    
    This enterprise-grade function deletes power ports with comprehensive
    safety checks including cable connection validation.
    
    Args:
        port_identifier: Power port name or ID to delete
        device_name: Device name for port lookup (improves search accuracy)
        site: Site name for device lookup (improves search accuracy)
        client: NetBox client (injected)
        confirm: Must be True to execute
        
    Returns:
        Dict containing operation result and deletion details
        
    Examples:
        # Dry run deletion
        netbox_delete_power_port("PSU1", device_name="server-01")
        
        # Delete with confirmation
        netbox_delete_power_port("PSU1", device_name="server-01", 
                                site="datacenter-1", confirm=True)
    """
    
    # DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Power port would be deleted. Set confirm=True to execute.",
            "would_delete": {
                "port_identifier": port_identifier,
                "device_name": device_name,
                "site": site
            }
        }
    
    # FIND POWER PORT TO DELETE
    try:
        # Try lookup by ID first
        if port_identifier.isdigit():
            port_id = int(port_identifier)
            # ULTRATHINK FIX 1: Add expand parameters for power port lookups\n            power_port_search_params = {\n                \"expand\": [\"device\", \"cable\"],\n                \"limit\": 50\n            }\n            ports = list(client.dcim.power_ports.filter(id=port_id, **power_port_search_params))
        else:
            # Search by name with optional device/site context
            filter_params = {"name": port_identifier}
            
            if device_name:
                device_filter = {"name": device_name}
                if site:
                    # ULTRATHINK FIX 1: Expand search parameters with comprehensive relationship data\n        site_search_params = {\n            \"expand\": [\"region\", \"tenant\"],\n            \"limit\": 50\n        }\n\n        # ULTRATHINK FIX 2: ID resolution with fallback patterns\n        sites = None\n        if site.isdigit():\n            sites = list(client.dcim.sites.filter(id=int(site), **site_search_params))\n\n        if not sites:\n            sites = list(client.dcim.sites.filter(name=site, **site_search_params))\n\n        # ULTRATHINK FIX 4: Slug-based fallback mechanisms\n        if not sites:\n            sites = list(client.dcim.sites.filter(slug=site, **site_search_params))
                    if sites:
                        site_obj = sites[0]
                        site_id = site_obj.get('id') if isinstance(site_obj, dict) else site_obj.id
                        device_filter["site_id"] = site_id
                
                # ULTRATHINK FIX 1: Add expand parameters to dynamic device filter\n                if 'expand' not in device_filter:\n                    device_filter['expand'] = [\"device_type\", \"device_type__manufacturer\", \"site\", \"rack\", \"tenant\", \"role\"]\n                if 'limit' not in device_filter:\n                    device_filter['limit'] = 50\n                devices = list(client.dcim.devices.filter(**device_filter))"
                if devices:
                    device_obj = devices[0]
                    device_id = device_obj.get('id') if isinstance(device_obj, dict) else device_obj.id
                    filter_params["device_id"] = device_id
            
            # ULTRATHINK FIX 1: Add expand parameters to dynamic power port filter\n            if 'expand' not in filter_params:\n                filter_params['expand'] = [\"device\", \"cable\"]\n            if 'limit' not in filter_params:\n                filter_params['limit'] = 50\n            ports = list(client.dcim.power_ports.filter(**filter_params))
        
        if not ports:
            identifier_desc = f"power port '{port_identifier}'"
            if device_name:
                identifier_desc += f" on device '{device_name}'"
            if site:
                identifier_desc += f" in site '{site}'"
            raise NetBoxNotFoundError(f"Could not find {identifier_desc}")
        
        port_to_delete = ports[0]
        port_id = port_to_delete.get('id') if isinstance(port_to_delete, dict) else port_to_delete.id
        port_name = port_to_delete.get('name') if isinstance(port_to_delete, dict) else port_to_delete.name
        
        # Get device information for reporting
        device_data = port_to_delete.get('device') if isinstance(port_to_delete, dict) else getattr(port_to_delete, 'device', {})
        device_name_actual = device_data.get('name') if isinstance(device_data, dict) else getattr(device_data, 'name', 'Unknown')
        
    except Exception as e:
        raise NetBoxNotFoundError(f"Failed to find power port: {e}")
    
    # DEPENDENCY VALIDATION
    dependencies = []
    
    try:
        # Check for cable connections
        cable_data = port_to_delete.get('cable') if isinstance(port_to_delete, dict) else getattr(port_to_delete, 'cable', None)
        if cable_data:
            cable_id = cable_data.get('id') if isinstance(cable_data, dict) else getattr(cable_data, 'id', None)
            cable_label = cable_data.get('label') if isinstance(cable_data, dict) else getattr(cable_data, 'label', f"Cable {cable_id}")
            
            dependencies.append({
                "type": "Cable Connection",
                "count": 1,
                "description": f"Connected cable: {cable_label}"
            })
        
    except Exception as e:
        logger.warning(f"Could not check cable dependencies: {e}")
    
    # If dependencies found, prevent deletion
    if dependencies:
        dependency_list = []
        for dep in dependencies:
            dependency_list.append(f"- {dep['description']}")
        
        raise NetBoxValidationError(
            f"Cannot delete power port '{port_name}' - it has active dependencies:\\n" +
            "\\n".join(dependency_list) +
            "\\n\\nPlease disconnect cables before deleting the power port."
        )
    
    # PERFORM DELETION
    try:
        logger.debug(f"Deleting power port {port_id} ({port_name})")
        client.dcim.power_ports.delete(port_id, confirm=confirm)
        
    except Exception as e:
        raise NetBoxValidationError(f"NetBox API error during power port deletion: {e}")
    
    # RETURN SUCCESS
    return {
        "success": True,
        "message": f"Power port '{port_name}' successfully deleted from device '{device_name_actual}'.",
        "data": {
            "deleted_port_id": port_id,
            "deleted_port_name": port_name,
            "device_name": device_name_actual,
            "dependencies_checked": len(dependencies) == 0
        }
    }