#!/usr/bin/env python3
"""
DCIM Power Outlets Management Tools

This module provides enterprise-grade tools for managing NetBox power outlets
including creation, updates, deletion, and information retrieval.
"""

from typing import Dict, Any, Optional, List
import logging

from src.registry import mcp_tool
from src.client import NetBoxClient
from src.exceptions import NetBoxValidationError, NetBoxNotFoundError, NetBoxConflictError

logger = logging.getLogger(__name__)


@mcp_tool(category="dcim")
def netbox_create_power_outlet(
    client: NetBoxClient,
    name: str,
    device_name: str,
    site: str,
    outlet_type: str = "iec-60320-c13",
    power_feed: Optional[str] = None,
    feed_leg: Optional[str] = None,
    description: Optional[str] = None,
    mark_connected: bool = False,
    tags: Optional[List[str]] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Create a new power outlet in NetBox.
    
    This enterprise-grade function creates power outlets for PDUs and other
    power distribution equipment.
    
    Args:
        name: Power outlet name/identifier
        device_name: Device name where outlet is located (foreign key resolved)
        site: Site name for device validation (foreign key resolved)
        outlet_type: Outlet type (iec-60320-c13, iec-60320-c19, nema-5-15r, etc.)
        power_feed: Power feed name for connection (foreign key resolved, optional)
        feed_leg: Feed leg designation (A, B, C, optional)
        description: Outlet description
        mark_connected: Mark outlet as connected
        tags: List of tags to assign
        client: NetBox client (injected)
        confirm: Must be True to execute
        
    Returns:
        Dict containing operation result and power outlet details
        
    Examples:
        # Dry run
        netbox_create_power_outlet("PDU-A-01", "PDU-RACK-A-01", "datacenter-1")
        
        # Create outlet with power feed
        netbox_create_power_outlet("PDU-A-01", "PDU-RACK-A-01", "datacenter-1",
                                  power_feed="FEED-A-01", feed_leg="A", confirm=True)
    """
    
    # DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Power outlet would be created. Set confirm=True to execute.",
            "would_create": {
                "name": name,
                "device_name": device_name,
                "site": site,
                "type": outlet_type,
                "power_feed": power_feed,
                "feed_leg": feed_leg,
                "description": description,
                "mark_connected": mark_connected,
                "tags": tags
            }
        }
    
    # PARAMETER VALIDATION
    if not name or not name.strip():
        raise NetBoxValidationError("Power outlet name cannot be empty")
    
    if not device_name or not device_name.strip():
        raise NetBoxValidationError("Device name is required for power outlet creation")
    
    if not site or not site.strip():
        raise NetBoxValidationError("Site is required for power outlet creation")
    
    # Validate outlet type (common types)
    valid_types = [
        "iec-60320-c5", "iec-60320-c7", "iec-60320-c13", "iec-60320-c15", 
        "iec-60320-c19", "iec-60320-c21", "iec-60309-p-n-e-4h", "iec-60309-p-n-e-6h", 
        "iec-60309-2p-e-4h", "iec-60309-2p-e-6h", "iec-60309-3p-e-4h", "iec-60309-3p-e-6h",
        "iec-60309-3p-n-e-4h", "iec-60309-3p-n-e-6h", "nema-1-15r", "nema-5-15r", 
        "nema-5-20r", "nema-5-30r", "nema-5-50r", "nema-6-15r", "nema-6-20r", 
        "nema-6-30r", "nema-6-50r", "nema-10-30r", "nema-10-50r", "nema-14-20r", 
        "nema-14-30r", "nema-14-50r", "nema-14-60r", "nema-15-15r", "nema-15-20r", 
        "nema-15-30r", "nema-15-50r", "nema-15-60r", "nema-l1-15r", "nema-l5-15r", 
        "nema-l5-20r", "nema-l5-30r", "nema-l5-50r", "nema-l6-15r", "nema-l6-20r", 
        "nema-l6-30r", "nema-l6-50r", "nema-l10-30r", "nema-l14-20r", "nema-l14-30r", 
        "nema-l15-20r", "nema-l15-30r", "nema-l21-20r", "nema-l21-30r", "nema-l22-30r",
        "cs6360c", "cs6364c", "cs8164c", "cs8264c", "cs8364c", "cs8464c", "ita-e", 
        "ita-f", "ita-g", "ita-h", "ita-i", "ita-j", "ita-k", "ita-l", "ita-m", 
        "ita-n", "ita-o", "usb-a", "usb-micro-b", "usb-c", "dc-terminal", "hdot-cx", 
        "saf-d-grid", "neutrik-powercon-20a", "neutrik-powercon-32a", "neutrik-powercon-true1", 
        "neutrik-powercon-true1-top", "ubiquiti-smartpower", "hardwired", "other"
    ]
    
    if outlet_type not in valid_types:
        # Don't raise error for unknown types, NetBox might support more
        logger.warning(f"Unknown outlet type '{outlet_type}'. Proceeding with API validation.")
    
    # Validate feed leg
    if feed_leg and feed_leg not in ["A", "B", "C"]:
        raise NetBoxValidationError(f"Invalid feed leg '{feed_leg}'. Valid options: A, B, C")
    
    # LOOKUP SITE (with defensive dict/object handling)
    try:
        sites = client.dcim.sites.filter(name=site)
        if not sites:
            raise NetBoxNotFoundError(f"Site '{site}' not found")
        
        site_obj = sites[0]
        site_id = site_obj.get('id') if isinstance(site_obj, dict) else site_obj.id
        site_display = site_obj.get('display', site) if isinstance(site_obj, dict) else getattr(site_obj, 'display', site)
        
    except Exception as e:
        raise NetBoxNotFoundError(f"Could not find site '{site}': {e}")
    
    # LOOKUP DEVICE
    try:
        devices = client.dcim.devices.filter(site_id=site_id, name=device_name)
        if not devices:
            raise NetBoxNotFoundError(f"Device '{device_name}' not found in site '{site}'")
        
        device_obj = devices[0]
        device_id = device_obj.get('id') if isinstance(device_obj, dict) else device_obj.id
        device_display = device_obj.get('display', device_name) if isinstance(device_obj, dict) else getattr(device_obj, 'display', device_name)
        
    except Exception as e:
        raise NetBoxValidationError(f"Failed to resolve device '{device_name}': {e}")
    
    # LOOKUP POWER FEED (if provided)
    feed_id = None
    feed_display = None
    if power_feed:
        try:
            # First find power panels in the site
            panels = client.dcim.power_panels.filter(site_id=site_id)
            feed_found = False

            for panel in panels:
                panel_id = panel.get('id') if isinstance(panel, dict) else panel.id

                # ULTRATHINK FIX 1: Expand power feed search parameters
                feed_search_params = {
                    "power_panel_id": panel_id,
                    "expand": ["power_panel", "site", "rack"],
                    "limit": 50
                }

                # ULTRATHINK FIX 2: Multi-strategy power feed search
                feeds = list(client.dcim.power_feeds.filter(name=power_feed, **feed_search_params))

                # ULTRATHINK FIX 4: Fallback power feed search
                if not feeds:
                    feeds = list(client.dcim.power_feeds.filter(name__icontains=power_feed, **feed_search_params))
                if feeds:
                    feed_obj = feeds[0]
                    feed_id = feed_obj.get('id') if isinstance(feed_obj, dict) else feed_obj.id
                    feed_display = feed_obj.get('display', power_feed) if isinstance(feed_obj, dict) else getattr(feed_obj, 'display', power_feed)
                    feed_found = True
                    break
            
            if not feed_found:
                raise NetBoxNotFoundError(f"Power feed '{power_feed}' not found in site '{site}'")
                
        except Exception as e:
            raise NetBoxValidationError(f"Failed to resolve power feed '{power_feed}': {e}")
    
    # CONFLICT DETECTION
    try:
        existing_outlets = client.dcim.power_outlets.filter(
            device_id=device_id,
            name=name,
            no_cache=True
        )
        
        if existing_outlets:
            existing_outlet = existing_outlets[0]
            existing_id = existing_outlet.get('id') if isinstance(existing_outlet, dict) else existing_outlet.id
            raise NetBoxConflictError(
                resource_type="Power Outlet",
                identifier=f"{name} on device {device_name}",
                existing_id=existing_id
            )
    except ConflictError:
        raise
    except Exception as e:
        logger.warning(f"Could not check for existing power outlets: {e}")
    
    # CREATE POWER OUTLET
    create_payload = {
        "device": device_id,
        "name": name,
        "type": outlet_type,
        "description": description or "",
        "mark_connected": mark_connected
    }
    
    # Add optional parameters
    if feed_id:
        create_payload["power_feed"] = feed_id
    
    if feed_leg:
        create_payload["feed_leg"] = feed_leg
    
    if tags:
        create_payload["tags"] = tags
    
    try:
        logger.debug(f"Creating power outlet with payload: {create_payload}")
        new_outlet = client.dcim.power_outlets.create(confirm=confirm, **create_payload)
        outlet_id = new_outlet.get('id') if isinstance(new_outlet, dict) else new_outlet.id
        
    except Exception as e:
        raise NetBoxValidationError(f"NetBox API error during power outlet creation: {e}")
    
    # RETURN SUCCESS
    return {
        "success": True,
        "message": f"Power outlet '{name}' successfully created on device '{device_name}'.",
        "data": {
            "outlet_id": outlet_id,
            "outlet_name": new_outlet.get('name') if isinstance(new_outlet, dict) else new_outlet.name,
            "device_id": device_id,
            "device_name": device_name,
            "site_id": site_id,
            "site_name": site,
            "power_feed_id": feed_id,
            "power_feed_name": power_feed,
            "specifications": {
                "type": outlet_type,
                "feed_leg": feed_leg,
                "mark_connected": mark_connected,
                "description": description
            },
            "url": f"{client.config.url}/dcim/power-outlets/{outlet_id}/"
        }
    }


@mcp_tool(category="dcim")
def netbox_get_power_outlet_info(
    client: NetBoxClient,
    outlet_identifier: str,
    device_name: Optional[str] = None,
    site: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get detailed information about a specific power outlet.
    
    This inspection tool provides comprehensive power outlet details including
    device assignment, power feed connections, and cable information.
    
    Args:
        outlet_identifier: Power outlet name or ID
        device_name: Device name for outlet lookup (improves search accuracy)
        site: Site name for outlet lookup (improves search accuracy)
        client: NetBox client (injected)
        
    Returns:
        Dict containing detailed power outlet information
        
    Examples:
        # Search by name
        netbox_get_power_outlet_info("PDU-A-01")
        
        # Search with device context
        netbox_get_power_outlet_info("PDU-A-01", device_name="PDU-RACK-A-01")
        
        # Search with site context
        netbox_get_power_outlet_info("PDU-A-01", site="datacenter-1")
    """
    
    # LOOKUP POWER OUTLET
    try:
        # Try lookup by ID first
        if outlet_identifier.isdigit():
            outlet_id = int(outlet_identifier)
            outlets = client.dcim.power_outlets.filter(id=outlet_id)
        else:
            # Search by name with optional context
            filter_params = {"name": outlet_identifier}
            
            # Add device context if provided
            if device_name:
                if site:
                    # Find device in specific site
                    sites = client.dcim.sites.filter(name=site)
                    if sites:
                        site_obj = sites[0]
                        site_id = site_obj.get('id') if isinstance(site_obj, dict) else site_obj.id
                        devices = client.dcim.devices.filter(site_id=site_id, name=device_name)
                        if devices:
                            device_obj = devices[0]
                            device_id = device_obj.get('id') if isinstance(device_obj, dict) else device_obj.id
                            filter_params["device_id"] = device_id
                else:
                    # Find device by name only
                    devices = client.dcim.devices.filter(name=device_name)
                    if devices:
                        device_obj = devices[0]
                        device_id = device_obj.get('id') if isinstance(device_obj, dict) else device_obj.id
                        filter_params["device_id"] = device_id
            elif site:
                # Filter by site only
                sites = client.dcim.sites.filter(name=site)
                if sites:
                    site_obj = sites[0]
                    site_id = site_obj.get('id') if isinstance(site_obj, dict) else site_obj.id
                    filter_params["site_id"] = site_id
            
            outlets = client.dcim.power_outlets.filter(**filter_params)
        
        if not outlets:
            identifier_desc = f"power outlet '{outlet_identifier}'"
            if device_name:
                identifier_desc += f" on device '{device_name}'"
            if site:
                identifier_desc += f" in site '{site}'"
            raise NetBoxNotFoundError(f"Could not find {identifier_desc}")
        
        outlet = outlets[0]
        outlet_id = outlet.get('id') if isinstance(outlet, dict) else outlet.id
        outlet_name = outlet.get('name') if isinstance(outlet, dict) else outlet.name
        
    except Exception as e:
        raise NetBoxNotFoundError(f"Failed to find power outlet: {e}")
    
    # GET CABLE CONNECTIONS
    cable_connections = []
    try:
        # Check A-side terminations
        cables_a = client.dcim.cables.filter(termination_a_type="dcim.poweroutlet", termination_a_id=outlet_id)
        for cable in cables_a:
            cable_info = {
                "cable_id": cable.get('id') if isinstance(cable, dict) else cable.id,
                "cable_type": cable.get('type', {}).get('label') if isinstance(cable, dict) else str(getattr(cable, 'type', 'N/A')),
                "status": cable.get('status', {}).get('label') if isinstance(cable, dict) else str(getattr(cable, 'status', 'N/A')),
                "termination_side": "A"
            }
            
            # Get B-side termination info
            b_terminations = cable.get('b_terminations', []) if isinstance(cable, dict) else getattr(cable, 'b_terminations', [])
            if b_terminations:
                b_term = b_terminations[0]
                cable_info["connected_to"] = {
                    "type": b_term.get('object_type') if isinstance(b_term, dict) else getattr(b_term, 'object_type', 'N/A'),
                    "name": b_term.get('object', {}).get('name') if isinstance(b_term, dict) else getattr(getattr(b_term, 'object', {}), 'name', 'N/A')
                }
            
            cable_connections.append(cable_info)
        
        # Check B-side terminations
        cables_b = client.dcim.cables.filter(termination_b_type="dcim.poweroutlet", termination_b_id=outlet_id)
        for cable in cables_b:
            cable_info = {
                "cable_id": cable.get('id') if isinstance(cable, dict) else cable.id,
                "cable_type": cable.get('type', {}).get('label') if isinstance(cable, dict) else str(getattr(cable, 'type', 'N/A')),
                "status": cable.get('status', {}).get('label') if isinstance(cable, dict) else str(getattr(cable, 'status', 'N/A')),
                "termination_side": "B"
            }
            
            # Get A-side termination info
            a_terminations = cable.get('a_terminations', []) if isinstance(cable, dict) else getattr(cable, 'a_terminations', [])
            if a_terminations:
                a_term = a_terminations[0]
                cable_info["connected_to"] = {
                    "type": a_term.get('object_type') if isinstance(a_term, dict) else getattr(a_term, 'object_type', 'N/A'),
                    "name": a_term.get('object', {}).get('name') if isinstance(a_term, dict) else getattr(getattr(a_term, 'object', {}), 'name', 'N/A')
                }
            
            cable_connections.append(cable_info)
            
    except Exception as e:
        logger.warning(f"Could not retrieve cable connections for outlet {outlet_id}: {e}")
    
    # GET RELATED INFORMATION
    device_info = {}
    site_info = {}
    power_feed_info = {}
    
    try:
        # Device information
        device_data = outlet.get('device') if isinstance(outlet, dict) else getattr(outlet, 'device', None)
        if device_data:
            device_info = {
                "id": device_data.get('id') if isinstance(device_data, dict) else getattr(device_data, 'id', None),
                "name": device_data.get('name') if isinstance(device_data, dict) else getattr(device_data, 'name', None),
                "display": device_data.get('display') if isinstance(device_data, dict) else getattr(device_data, 'display', None)
            }
            
            # Get site from device
            if device_data:
                device_site_data = device_data.get('site') if isinstance(device_data, dict) else getattr(device_data, 'site', None)
                if device_site_data:
                    site_info = {
                        "id": device_site_data.get('id') if isinstance(device_site_data, dict) else getattr(device_site_data, 'id', None),
                        "name": device_site_data.get('name') if isinstance(device_site_data, dict) else getattr(device_site_data, 'name', None),
                        "display": device_site_data.get('display') if isinstance(device_site_data, dict) else getattr(device_site_data, 'display', None)
                    }
        
        # Power feed information
        feed_data = outlet.get('power_feed') if isinstance(outlet, dict) else getattr(outlet, 'power_feed', None)
        if feed_data:
            power_feed_info = {
                "id": feed_data.get('id') if isinstance(feed_data, dict) else getattr(feed_data, 'id', None),
                "name": feed_data.get('name') if isinstance(feed_data, dict) else getattr(feed_data, 'name', None),
                "display": feed_data.get('display') if isinstance(feed_data, dict) else getattr(feed_data, 'display', None)
            }
            
    except Exception as e:
        logger.warning(f"Could not retrieve related information for outlet {outlet_id}: {e}")
    
    # GET SPECIFICATIONS
    specifications = {}
    try:
        specifications = {
            "type": outlet.get('type', {}).get('label') if isinstance(outlet, dict) else str(getattr(outlet, 'type', 'N/A')),
            "feed_leg": outlet.get('feed_leg', {}).get('label') if isinstance(outlet, dict) else str(getattr(outlet, 'feed_leg', None)),
            "mark_connected": outlet.get('mark_connected') if isinstance(outlet, dict) else getattr(outlet, 'mark_connected', False),
            "description": outlet.get('description') if isinstance(outlet, dict) else getattr(outlet, 'description', '')
        }
    except Exception as e:
        logger.warning(f"Could not retrieve specifications for outlet {outlet_id}: {e}")
    
    # RETURN COMPREHENSIVE INFORMATION
    return {
        "success": True,
        "data": {
            "outlet_id": outlet_id,
            "name": outlet_name,
            "device": device_info,
            "site": site_info,
            "power_feed": power_feed_info,
            "specifications": specifications,
            "cable_connections": {
                "count": len(cable_connections),
                "connections": cable_connections
            },
            "tags": outlet.get('tags', []) if isinstance(outlet, dict) else getattr(outlet, 'tags', []),
            "created": outlet.get('created') if isinstance(outlet, dict) else getattr(outlet, 'created', None),
            "last_updated": outlet.get('last_updated') if isinstance(outlet, dict) else getattr(outlet, 'last_updated', None),
            "url": f"{client.config.url}/dcim/power-outlets/{outlet_id}/"
        }
    }


@mcp_tool(category="dcim")
def netbox_list_all_power_outlets(
    client: NetBoxClient,
    site: Optional[str] = None,
    device_name: Optional[str] = None,
    power_feed: Optional[str] = None,
    outlet_type: Optional[str] = None,
    connected_only: bool = False,
    limit: int = 50
) -> Dict[str, Any]:
    """
    List all power outlets with optional filtering.
    
    This bulk discovery tool helps explore and analyze power outlet
    distribution and connectivity across devices and sites.
    
    Args:
        site: Filter by site name (optional)
        device_name: Filter by device name (optional)
        power_feed: Filter by power feed name (optional)
        outlet_type: Filter by outlet type (optional)
        connected_only: Show only outlets with cable connections (optional)
        limit: Maximum number of outlets to return (default: 50)
        client: NetBox client (injected)
        
    Returns:
        Dict containing list of power outlets with connectivity statistics
        
    Examples:
        # List all outlets
        netbox_list_all_power_outlets()
        
        # Filter by site and device
        netbox_list_all_power_outlets(site="datacenter-1", device_name="PDU-RACK-A-01")
        
        # Show only connected outlets
        netbox_list_all_power_outlets(connected_only=True)
    """
    
    filter_params = {}
    
    # RESOLVE SITE FILTER
    if site:
        try:
            sites = client.dcim.sites.filter(name=site)
            if sites:
                site_obj = sites[0]
                site_id = site_obj.get('id') if isinstance(site_obj, dict) else site_obj.id
                filter_params["site_id"] = site_id
            else:
                return {
                    "success": True,
                    "data": {
                        "outlets": [],
                        "total_count": 0,
                        "message": f"No outlets found - site '{site}' not found"
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
                        "outlets": [],
                        "total_count": 0,
                        "message": f"No outlets found - device '{device_name}' not found"
                    }
                }
        except Exception as e:
            logger.warning(f"Could not resolve device filter '{device_name}': {e}")
    
    # RESOLVE POWER FEED FILTER
    if power_feed:
        try:
            # Find power feed across all power panels (or in specific site if provided)
            feed_found = False
            if "site_id" in filter_params:
                panels = client.dcim.power_panels.filter(site_id=filter_params["site_id"])
            else:
                panels = client.dcim.power_panels.all()
            
            for panel in panels:
                panel_id = panel.get('id') if isinstance(panel, dict) else panel.id
                feeds = client.dcim.power_feeds.filter(power_panel_id=panel_id, name=power_feed)
                if feeds:
                    feed_obj = feeds[0]
                    feed_id = feed_obj.get('id') if isinstance(feed_obj, dict) else feed_obj.id
                    filter_params["power_feed_id"] = feed_id
                    feed_found = True
                    break
            
            if not feed_found:
                return {
                    "success": True,
                    "data": {
                        "outlets": [],
                        "total_count": 0,
                        "message": f"No outlets found - power feed '{power_feed}' not found"
                    }
                }
        except Exception as e:
            logger.warning(f"Could not resolve power feed filter '{power_feed}': {e}")
    
    # ADD TYPE FILTER
    if outlet_type:
        filter_params["type"] = outlet_type
    
    # GET POWER OUTLETS
    try:
        outlets = client.dcim.power_outlets.filter(**filter_params)
        
        # Filter connected outlets if requested
        if connected_only:
            connected_outlets = []
            for outlet in outlets:
                outlet_id = outlet.get('id') if isinstance(outlet, dict) else outlet.id
                
                # Check for cable connections
                cables_a = client.dcim.cables.filter(termination_a_type="dcim.poweroutlet", termination_a_id=outlet_id)
                cables_b = client.dcim.cables.filter(termination_b_type="dcim.poweroutlet", termination_b_id=outlet_id)
                
                if cables_a or cables_b:
                    connected_outlets.append(outlet)
            
            outlets = connected_outlets
        
        total_count = len(outlets)
        
        # Apply limit
        limited_outlets = outlets[:limit]
        
        outlets_data = []
        connection_stats = {
            "total_outlets": total_count,
            "connected_outlets": 0,
            "outlet_count_by_type": {},
            "outlet_count_by_device": {}
        }
        
        for outlet in limited_outlets:
            try:
                # Get basic outlet info
                outlet_id = outlet.get('id') if isinstance(outlet, dict) else outlet.id
                outlet_name = outlet.get('name') if isinstance(outlet, dict) else outlet.name
                
                # Get device info
                device_data = outlet.get('device') if isinstance(outlet, dict) else getattr(outlet, 'device', {})
                device_name = device_data.get('name') if isinstance(device_data, dict) else getattr(device_data, 'name', 'N/A')
                
                # Get site info (from device)
                site_name = "N/A"
                if device_data:
                    device_site_data = device_data.get('site') if isinstance(device_data, dict) else getattr(device_data, 'site', None)
                    if device_site_data:
                        site_name = device_site_data.get('name') if isinstance(device_site_data, dict) else getattr(device_site_data, 'name', 'N/A')
                
                # Get power feed info
                feed_data = outlet.get('power_feed') if isinstance(outlet, dict) else getattr(outlet, 'power_feed', None)
                feed_name = feed_data.get('name') if feed_data and isinstance(feed_data, dict) else getattr(feed_data, 'name', None) if feed_data else None
                
                # Get specifications
                type_obj = outlet.get('type') if isinstance(outlet, dict) else getattr(outlet, 'type', None)
                type_value = type_obj.get('label') if isinstance(type_obj, dict) else str(type_obj) if type_obj else 'N/A'
                
                feed_leg_obj = outlet.get('feed_leg') if isinstance(outlet, dict) else getattr(outlet, 'feed_leg', None)
                feed_leg_value = feed_leg_obj.get('label') if isinstance(feed_leg_obj, dict) else str(feed_leg_obj) if feed_leg_obj else None
                
                mark_connected = outlet.get('mark_connected') if isinstance(outlet, dict) else getattr(outlet, 'mark_connected', False)
                
                # Check for actual cable connections
                cables_a = client.dcim.cables.filter(termination_a_type="dcim.poweroutlet", termination_a_id=outlet_id)
                cables_b = client.dcim.cables.filter(termination_b_type="dcim.poweroutlet", termination_b_id=outlet_id)
                cable_count = len(cables_a) + len(cables_b)
                
                if cable_count > 0:
                    connection_stats["connected_outlets"] += 1
                
                # Update statistics
                connection_stats["outlet_count_by_type"][type_value] = connection_stats["outlet_count_by_type"].get(type_value, 0) + 1
                connection_stats["outlet_count_by_device"][device_name] = connection_stats["outlet_count_by_device"].get(device_name, 0) + 1
                
                outlet_info = {
                    "id": outlet_id,
                    "name": outlet_name,
                    "device": device_name,
                    "site": site_name,
                    "power_feed": feed_name,
                    "specifications": {
                        "type": type_value,
                        "feed_leg": feed_leg_value,
                        "mark_connected": mark_connected
                    },
                    "cable_connections": cable_count,
                    "url": f"{client.config.url}/dcim/power-outlets/{outlet_id}/"
                }
                
                outlets_data.append(outlet_info)
                
            except Exception as e:
                logger.warning(f"Error processing outlet data: {e}")
                continue
        
        # Calculate connection percentage
        connection_percentage = round((connection_stats["connected_outlets"] / connection_stats["total_outlets"]) * 100, 1) if connection_stats["total_outlets"] > 0 else 0
        
        # Build filter description
        filter_description = []
        if site:
            filter_description.append(f"site: {site}")
        if device_name:
            filter_description.append(f"device: {device_name}")
        if power_feed:
            filter_description.append(f"power feed: {power_feed}")
        if outlet_type:
            filter_description.append(f"type: {outlet_type}")
        if connected_only:
            filter_description.append("connected only")
        
        filter_text = f" (filtered by {', '.join(filter_description)})" if filter_description else ""
        
        return {
            "success": True,
            "data": {
                "outlets": outlets_data,
                "total_count": total_count,
                "returned_count": len(outlets_data),
                "limit_applied": limit if total_count > limit else None,
                "filters": filter_text,
                "connection_statistics": {
                    "total_outlets": connection_stats["total_outlets"],
                    "connected_outlets": connection_stats["connected_outlets"],
                    "connection_percentage": connection_percentage,
                    "outlet_count_by_type": connection_stats["outlet_count_by_type"],
                    "outlet_count_by_device": connection_stats["outlet_count_by_device"]
                }
            }
        }
        
    except Exception as e:
        raise NetBoxValidationError(f"Failed to retrieve power outlets: {e}")


@mcp_tool(category="dcim")
def netbox_update_power_outlet(
    client: NetBoxClient,
    outlet_identifier: str,
    device_name: Optional[str] = None,
    site: Optional[str] = None,
    new_name: Optional[str] = None,
    outlet_type: Optional[str] = None,
    power_feed: Optional[str] = None,
    feed_leg: Optional[str] = None,
    description: Optional[str] = None,
    mark_connected: Optional[bool] = None,
    tags: Optional[List[str]] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Update an existing power outlet.
    
    This enterprise-grade function updates power outlet configuration
    with comprehensive validation and safety checks.
    
    Args:
        outlet_identifier: Power outlet name or ID to update
        device_name: Device name for outlet lookup (improves search accuracy)
        site: Site name for outlet lookup (improves search accuracy)
        new_name: New name for the power outlet (optional)
        outlet_type: Update outlet type (optional)
        power_feed: Update power feed assignment (optional)
        feed_leg: Update feed leg designation (A, B, C, optional)
        description: Update description (optional)
        mark_connected: Update mark connected status (optional)
        tags: Update tags list (optional)
        client: NetBox client (injected)
        confirm: Must be True to execute
        
    Returns:
        Dict containing operation result and updated outlet details
        
    Examples:
        # Dry run update
        netbox_update_power_outlet("PDU-A-01", outlet_type="iec-60320-c19")
        
        # Update with confirmation
        netbox_update_power_outlet("PDU-A-01", power_feed="FEED-A-02", 
                                  feed_leg="B", confirm=True)
    """
    
    # DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Power outlet would be updated. Set confirm=True to execute.",
            "would_update": {
                "outlet_identifier": outlet_identifier,
                "new_name": new_name,
                "outlet_type": outlet_type,
                "power_feed": power_feed,
                "feed_leg": feed_leg,
                "description": description,
                "mark_connected": mark_connected,
                "tags": tags
            }
        }
    
    # FIND EXISTING POWER OUTLET
    try:
        # Try lookup by ID first
        if outlet_identifier.isdigit():
            outlet_id = int(outlet_identifier)
            outlets = client.dcim.power_outlets.filter(id=outlet_id)
        else:
            # Search by name with optional context
            filter_params = {"name": outlet_identifier}
            
            # Add device context if provided
            if device_name:
                if site:
                    # Find device in specific site
                    sites = client.dcim.sites.filter(name=site)
                    if sites:
                        site_obj = sites[0]
                        site_id = site_obj.get('id') if isinstance(site_obj, dict) else site_obj.id
                        devices = client.dcim.devices.filter(site_id=site_id, name=device_name)
                        if devices:
                            device_obj = devices[0]
                            device_id = device_obj.get('id') if isinstance(device_obj, dict) else device_obj.id
                            filter_params["device_id"] = device_id
                else:
                    # Find device by name only
                    devices = client.dcim.devices.filter(name=device_name)
                    if devices:
                        device_obj = devices[0]
                        device_id = device_obj.get('id') if isinstance(device_obj, dict) else device_obj.id
                        filter_params["device_id"] = device_id
            
            outlets = client.dcim.power_outlets.filter(**filter_params)
        
        if not outlets:
            identifier_desc = f"power outlet '{outlet_identifier}'"
            if device_name:
                identifier_desc += f" on device '{device_name}'"
            if site:
                identifier_desc += f" in site '{site}'"
            raise NetBoxNotFoundError(f"Could not find {identifier_desc}")
        
        existing_outlet = outlets[0]
        outlet_id = existing_outlet.get('id') if isinstance(existing_outlet, dict) else existing_outlet.id
        current_name = existing_outlet.get('name') if isinstance(existing_outlet, dict) else existing_outlet.name
        
        # Get current device for conflict checking
        current_device = existing_outlet.get('device') if isinstance(existing_outlet, dict) else getattr(existing_outlet, 'device', {})
        current_device_id = current_device.get('id') if isinstance(current_device, dict) else getattr(current_device, 'id', None)
        
    except Exception as e:
        raise NetBoxNotFoundError(f"Failed to find power outlet: {e}")
    
    # BUILD UPDATE PAYLOAD
    update_payload = {}
    
    # Handle name update
    if new_name:
        if not new_name.strip():
            raise NetBoxValidationError("New power outlet name cannot be empty")
        update_payload["name"] = new_name.strip()
    
    # Handle outlet type update
    if outlet_type:
        update_payload["type"] = outlet_type
    
    # Handle power feed update
    if power_feed is not None:  # Allow empty string to clear power feed
        if power_feed:  # Non-empty power feed
            try:
                # Get current device's site
                current_device_site = current_device.get('site') if isinstance(current_device, dict) else getattr(current_device, 'site', {})
                site_id = current_device_site.get('id') if isinstance(current_device_site, dict) else getattr(current_device_site, 'id', None)
                
                if site_id:
                    # Find power feed in current site
                    panels = client.dcim.power_panels.filter(site_id=site_id)
                    feed_found = False
                    
                    for panel in panels:
                        panel_id = panel.get('id') if isinstance(panel, dict) else panel.id
                        feeds = client.dcim.power_feeds.filter(power_panel_id=panel_id, name=power_feed)
                        if feeds:
                            feed_obj = feeds[0]
                            feed_id = feed_obj.get('id') if isinstance(feed_obj, dict) else feed_obj.id
                            update_payload["power_feed"] = feed_id
                            feed_found = True
                            break
                    
                    if not feed_found:
                        raise NetBoxNotFoundError(f"Power feed '{power_feed}' not found in current site")
                else:
                    raise NetBoxValidationError("Cannot resolve power feed - site information missing")
                    
            except Exception as e:
                raise NetBoxValidationError(f"Failed to resolve power feed '{power_feed}': {e}")
        else:
            # Clear power feed
            update_payload["power_feed"] = None
    
    # Handle feed leg update
    if feed_leg is not None:  # Allow empty string to clear feed leg
        if feed_leg:
            if feed_leg not in ["A", "B", "C"]:
                raise NetBoxValidationError(f"Invalid feed leg '{feed_leg}'. Valid options: A, B, C")
            update_payload["feed_leg"] = feed_leg
        else:
            update_payload["feed_leg"] = None
    
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
            existing_outlets = client.dcim.power_outlets.filter(
                device_id=current_device_id,
                name=update_payload["name"],
                no_cache=True
            )
            
            # Check if found outlet is different from current outlet
            for existing in existing_outlets:
                existing_id = existing.get('id') if isinstance(existing, dict) else existing.id
                if existing_id != outlet_id:
                    raise NetBoxConflictError(
                        resource_type="Power Outlet",
                        identifier=f"{update_payload['name']} on current device",
                        existing_id=existing_id
                    )
        except ConflictError:
            raise
        except Exception as e:
            logger.warning(f"Could not check for naming conflicts: {e}")
    
    # PERFORM UPDATE
    try:
        logger.debug(f"Updating power outlet {outlet_id} with payload: {update_payload}")
        updated_outlet = client.dcim.power_outlets.update(outlet_id, confirm=confirm, **update_payload)
        updated_name = updated_outlet.get('name') if isinstance(updated_outlet, dict) else updated_outlet.name
        
    except Exception as e:
        raise NetBoxValidationError(f"NetBox API error during power outlet update: {e}")
    
    # RETURN SUCCESS
    return {
        "success": True,
        "message": f"Power outlet successfully updated from '{current_name}' to '{updated_name}'.",
        "data": {
            "outlet_id": outlet_id,
            "old_name": current_name,
            "new_name": updated_name,
            "updates_applied": list(update_payload.keys()),
            "url": f"{client.config.url}/dcim/power-outlets/{outlet_id}/"
        }
    }


@mcp_tool(category="dcim")
def netbox_delete_power_outlet(
    client: NetBoxClient,
    outlet_identifier: str,
    device_name: Optional[str] = None,
    site: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Delete a power outlet from NetBox.
    
    This enterprise-grade function deletes power outlets with comprehensive
    safety checks including cable connection validation.
    
    Args:
        outlet_identifier: Power outlet name or ID to delete
        device_name: Device name for outlet lookup (improves search accuracy)
        site: Site name for outlet lookup (improves search accuracy)
        client: NetBox client (injected)
        confirm: Must be True to execute
        
    Returns:
        Dict containing operation result and deletion details
        
    Examples:
        # Dry run deletion
        netbox_delete_power_outlet("PDU-A-01")
        
        # Delete with confirmation
        netbox_delete_power_outlet("PDU-A-01", device_name="PDU-RACK-A-01", confirm=True)
    """
    
    # DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Power outlet would be deleted. Set confirm=True to execute.",
            "would_delete": {
                "outlet_identifier": outlet_identifier,
                "device_name": device_name,
                "site": site
            }
        }
    
    # FIND POWER OUTLET TO DELETE
    try:
        # Try lookup by ID first
        if outlet_identifier.isdigit():
            outlet_id = int(outlet_identifier)
            outlets = client.dcim.power_outlets.filter(id=outlet_id)
        else:
            # Search by name with optional context
            filter_params = {"name": outlet_identifier}
            
            # Add device context if provided
            if device_name:
                if site:
                    # Find device in specific site
                    sites = client.dcim.sites.filter(name=site)
                    if sites:
                        site_obj = sites[0]
                        site_id = site_obj.get('id') if isinstance(site_obj, dict) else site_obj.id
                        devices = client.dcim.devices.filter(site_id=site_id, name=device_name)
                        if devices:
                            device_obj = devices[0]
                            device_id = device_obj.get('id') if isinstance(device_obj, dict) else device_obj.id
                            filter_params["device_id"] = device_id
                else:
                    # Find device by name only
                    devices = client.dcim.devices.filter(name=device_name)
                    if devices:
                        device_obj = devices[0]
                        device_id = device_obj.get('id') if isinstance(device_obj, dict) else device_obj.id
                        filter_params["device_id"] = device_id
            
            outlets = client.dcim.power_outlets.filter(**filter_params)
        
        if not outlets:
            identifier_desc = f"power outlet '{outlet_identifier}'"
            if device_name:
                identifier_desc += f" on device '{device_name}'"
            if site:
                identifier_desc += f" in site '{site}'"
            raise NetBoxNotFoundError(f"Could not find {identifier_desc}")
        
        outlet_to_delete = outlets[0]
        outlet_id = outlet_to_delete.get('id') if isinstance(outlet_to_delete, dict) else outlet_to_delete.id
        outlet_name = outlet_to_delete.get('name') if isinstance(outlet_to_delete, dict) else outlet_to_delete.name
        
        # Get device information for reporting
        device_data = outlet_to_delete.get('device') if isinstance(outlet_to_delete, dict) else getattr(outlet_to_delete, 'device', {})
        device_name_actual = device_data.get('name') if isinstance(device_data, dict) else getattr(device_data, 'name', 'Unknown')
        
        # Get site information
        site_name = "Unknown"
        if device_data:
            device_site_data = device_data.get('site') if isinstance(device_data, dict) else getattr(device_data, 'site', None)
            if device_site_data:
                site_name = device_site_data.get('name') if isinstance(device_site_data, dict) else getattr(device_site_data, 'name', 'Unknown')
        
    except Exception as e:
        raise NetBoxNotFoundError(f"Failed to find power outlet: {e}")
    
    # DEPENDENCY VALIDATION
    dependencies = []
    
    try:
        # Check for cable connections
        cables_a = client.dcim.cables.filter(termination_a_type="dcim.poweroutlet", termination_a_id=outlet_id)
        cables_b = client.dcim.cables.filter(termination_b_type="dcim.poweroutlet", termination_b_id=outlet_id)
        all_cables = list(cables_a) + list(cables_b)
        
        if all_cables:
            cable_info = []
            for cable in all_cables[:3]:  # Show first 3 cables
                cable_id = cable.get('id') if isinstance(cable, dict) else cable.id
                cable_type = cable.get('type', {}).get('label') if isinstance(cable, dict) else str(getattr(cable, 'type', 'Unknown'))
                cable_info.append(f"Cable {cable_id} ({cable_type})")
            
            dependency_desc = f"{len(all_cables)} cable connection(s): {', '.join(cable_info)}"
            if len(all_cables) > 3:
                dependency_desc += f" and {len(all_cables) - 3} more"
            
            dependencies.append({
                "type": "Cable Connections",
                "count": len(all_cables),
                "description": dependency_desc
            })
        
    except Exception as e:
        logger.warning(f"Could not check cable dependencies: {e}")
    
    # If dependencies found, prevent deletion
    if dependencies:
        dependency_list = []
        for dep in dependencies:
            dependency_list.append(f"- {dep['description']}")
        
        raise NetBoxValidationError(
            f"Cannot delete power outlet '{outlet_name}' - it has active dependencies:\n" +
            "\n".join(dependency_list) +
            "\n\nPlease remove these cable connections before deleting the power outlet."
        )
    
    # PERFORM DELETION
    try:
        logger.debug(f"Deleting power outlet {outlet_id} ({outlet_name})")
        client.dcim.power_outlets.delete(outlet_id, confirm=confirm)
        
    except Exception as e:
        raise NetBoxValidationError(f"NetBox API error during power outlet deletion: {e}")
    
    # RETURN SUCCESS
    return {
        "success": True,
        "message": f"Power outlet '{outlet_name}' successfully deleted from device '{device_name_actual}'.",
        "data": {
            "deleted_outlet_id": outlet_id,
            "deleted_outlet_name": outlet_name,
            "device_name": device_name_actual,
            "site_name": site_name,
            "dependencies_checked": len(dependencies) == 0
        }
    }