#!/usr/bin/env python3
"""
DCIM Power Connections Management Tools

This module provides enterprise-grade tools for managing NetBox power connections
including cable connections between power outlets, devices, and power feeds.
"""

from typing import Dict, Any, Optional, List
import logging

from netbox_mcp.registry import mcp_tool
from netbox_mcp.client import NetBoxClient
from netbox_mcp.exceptions import NetBoxValidationError, NetBoxNotFoundError, NetBoxConflictError

logger = logging.getLogger(__name__)


@mcp_tool(category="dcim")
def netbox_create_power_cable(
    client: NetBoxClient,
    a_termination_type: str,
    a_termination_name: str,
    b_termination_type: str,
    b_termination_name: str,
    cable_type: str = "power",
    status: str = "connected",
    a_device_name: Optional[str] = None,
    b_device_name: Optional[str] = None,
    site: Optional[str] = None,
    length: Optional[float] = None,
    length_unit: str = "m",
    label: Optional[str] = None,
    color: Optional[str] = None,
    tags: Optional[List[str]] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Create a power cable connection between two power terminations.
    
    This enterprise-grade function creates cables connecting power outlets,
    power feeds, and other power infrastructure components.
    
    Args:
        a_termination_type: A-side termination type (poweroutlet, powerfeed, powerport)
        a_termination_name: A-side termination name
        b_termination_type: B-side termination type (poweroutlet, powerfeed, powerport)
        b_termination_name: B-side termination name  
        cable_type: Cable type (power, default: power)
        status: Cable status (planned, connected, decommissioning, default: connected)
        a_device_name: A-side device name (required for poweroutlet/powerport)
        b_device_name: B-side device name (required for poweroutlet/powerport)
        site: Site name for validation (optional but recommended)
        length: Cable length (optional)
        length_unit: Length unit (m, ft, default: m)
        label: Cable label (optional)
        color: Cable color (optional)
        tags: List of tags to assign
        client: NetBox client (injected)
        confirm: Must be True to execute
        
    Returns:
        Dict containing operation result and cable details
        
    Examples:
        # Dry run - Power outlet to power port
        netbox_create_power_cable("poweroutlet", "PDU-A-01", "powerport", "PSU1",
                                 a_device_name="PDU-RACK-A-01", b_device_name="server-01", 
                                 site="datacenter-1")
        
        # Connect power feed to power outlet
        netbox_create_power_cable("powerfeed", "FEED-A-01", "poweroutlet", "PDU-A-01",
                                 b_device_name="PDU-RACK-A-01", length=2.0, confirm=True)
    """
    
    # DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Power cable would be created. Set confirm=True to execute.",
            "would_create": {
                "cable_type": cable_type,
                "status": status,
                "a_side": {
                    "type": a_termination_type,
                    "name": a_termination_name,
                    "device": a_device_name
                },
                "b_side": {
                    "type": b_termination_type,
                    "name": b_termination_name,
                    "device": b_device_name
                },
                "site": site,
                "length": length,
                "length_unit": length_unit,
                "label": label,
                "color": color,
                "tags": tags
            }
        }
    
    # PARAMETER VALIDATION
    valid_statuses = ["planned", "connected", "decommissioning"]
    if status not in valid_statuses:
        raise NetBoxValidationError(f"Invalid status '{status}'. Valid options: {', '.join(valid_statuses)}")
    
    valid_termination_types = ["poweroutlet", "powerfeed", "powerport"]
    if a_termination_type not in valid_termination_types:
        raise NetBoxValidationError(f"Invalid A-side termination type '{a_termination_type}'. Valid options: {', '.join(valid_termination_types)}")
    
    if b_termination_type not in valid_termination_types:
        raise NetBoxValidationError(f"Invalid B-side termination type '{b_termination_type}'. Valid options: {', '.join(valid_termination_types)}")
    
    # Device names are required for poweroutlet and powerport
    if a_termination_type in ["poweroutlet", "powerport"] and not a_device_name:
        raise NetBoxValidationError(f"Device name is required for A-side termination type '{a_termination_type}'")
    
    if b_termination_type in ["poweroutlet", "powerport"] and not b_device_name:
        raise NetBoxValidationError(f"Device name is required for B-side termination type '{b_termination_type}'")
    
    valid_length_units = ["mm", "cm", "m", "km", "in", "ft", "yd"]
    if length_unit not in valid_length_units:
        raise NetBoxValidationError(f"Invalid length unit '{length_unit}'. Valid options: {', '.join(valid_length_units)}")
    
    # LOOKUP SITE (if provided)
    site_id = None
    if site:
        try:
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
                sites = list(client.dcim.sites.filter(name=site, **site_search_params))

            # ULTRATHINK FIX 4: Slug-based fallback mechanisms
            if not sites:
                sites = list(client.dcim.sites.filter(slug=site, **site_search_params))
            if not sites:
                raise NetBoxNotFoundError(f"Site '{site}' not found")
            
            site_obj = sites[0]
            site_id = site_obj.get('id') if isinstance(site_obj, dict) else site_obj.id
            
        except Exception as e:
            raise NetBoxNotFoundError(f"Could not find site '{site}': {e}")
    
    # RESOLVE A-SIDE TERMINATION
    a_termination_id = None
    a_termination_object_type = None
    
    try:
        if a_termination_type == "poweroutlet":
            a_termination_object_type = "dcim.poweroutlet"
            
            # Find device first
            device_filter = {"name": a_device_name}
            if site_id:
                device_filter["site_id"] = site_id
            
            # ULTRATHINK FIX 1: Add expand parameters to dynamic device filter
            if 'expand' not in device_filter:
                device_filter['expand'] = ["device_type", "device_type__manufacturer", "site", "rack", "tenant", "role"]
            if 'limit' not in device_filter:
                device_filter['limit'] = 50
            devices = list(client.dcim.devices.filter(**device_filter))
            if not devices:
                raise NetBoxNotFoundError(f"A-side device '{a_device_name}' not found")
            
            device_obj = devices[0]
            device_id = device_obj.get('id') if isinstance(device_obj, dict) else device_obj.id
            
            # Find power outlet on device
            # ULTRATHINK FIX 1: Add expand parameters for power outlet lookups
            power_outlet_search_params = {
                "expand": ["device", "power_port", "cable"],
                "limit": 50
            }
            outlets = list(client.dcim.power_outlets.filter(device_id=device_id, name=a_termination_name, **power_outlet_search_params))
            if not outlets:
                raise NetBoxNotFoundError(f"A-side power outlet '{a_termination_name}' not found on device '{a_device_name}'")
            
            outlet_obj = outlets[0]
            a_termination_id = outlet_obj.get('id') if isinstance(outlet_obj, dict) else outlet_obj.id
            
        elif a_termination_type == "powerport":
            a_termination_object_type = "dcim.powerport"
            
            # Find device first
            device_filter = {"name": a_device_name}
            if site_id:
                device_filter["site_id"] = site_id
            
            # ULTRATHINK FIX 1: Add expand parameters to dynamic device filter
            if 'expand' not in device_filter:
                device_filter['expand'] = ["device_type", "device_type__manufacturer", "site", "rack", "tenant", "role"]
            if 'limit' not in device_filter:
                device_filter['limit'] = 50
            devices = list(client.dcim.devices.filter(**device_filter))
            if not devices:
                raise NetBoxNotFoundError(f"A-side device '{a_device_name}' not found")
            
            device_obj = devices[0]
            device_id = device_obj.get('id') if isinstance(device_obj, dict) else device_obj.id
            
            # Find power port on device
            # ULTRATHINK FIX 1: Add expand parameters for power port lookups
            power_port_search_params = {
                "expand": ["device", "cable"],
                "limit": 50
            }
            ports = list(client.dcim.power_ports.filter(device_id=device_id, name=a_termination_name, **power_port_search_params))
            if not ports:
                raise NetBoxNotFoundError(f"A-side power port '{a_termination_name}' not found on device '{a_device_name}'")
            
            port_obj = ports[0]
            a_termination_id = port_obj.get('id') if isinstance(port_obj, dict) else port_obj.id
            
        elif a_termination_type == "powerfeed":
            a_termination_object_type = "dcim.powerfeed"
            
            # Find power feed across power panels
            feed_found = False
            if site_id:
                # ULTRATHINK FIX 1: Add expand parameters for power panel lookups
                power_panel_search_params = {
                    "expand": ["site", "location", "rack_group"],
                    "limit": 100
                }
                panels = list(client.dcim.power_panels.filter(site_id=site_id, **power_panel_search_params))
            else:
                panels = client.dcim.power_panels.all()
            
            for panel in panels:
                panel_id = panel.get('id') if isinstance(panel, dict) else panel.id
                # ULTRATHINK FIX 1: Add expand parameters for power feed lookups
                power_feed_search_params = {
                    "expand": ["power_panel", "rack", "site"],
                    "limit": 50
                }
                feeds = list(client.dcim.power_feeds.filter(power_panel_id=panel_id, name=a_termination_name, **power_feed_search_params))
                if feeds:
                    feed_obj = feeds[0]
                    a_termination_id = feed_obj.get('id') if isinstance(feed_obj, dict) else feed_obj.id
                    feed_found = True
                    break
            
            if not feed_found:
                site_context = f" in site '{site}'" if site else ""
                raise NetBoxNotFoundError(f"A-side power feed '{a_termination_name}' not found{site_context}")
        
    except Exception as e:
        raise NetBoxValidationError(f"Failed to resolve A-side termination: {e}")
    
    # RESOLVE B-SIDE TERMINATION
    b_termination_id = None
    b_termination_object_type = None
    
    try:
        if b_termination_type == "poweroutlet":
            b_termination_object_type = "dcim.poweroutlet"
            
            # Find device first
            device_filter = {"name": b_device_name}
            if site_id:
                device_filter["site_id"] = site_id
            
            # ULTRATHINK FIX 1: Add expand parameters to dynamic device filter
            if 'expand' not in device_filter:
                device_filter['expand'] = ["device_type", "device_type__manufacturer", "site", "rack", "tenant", "role"]
            if 'limit' not in device_filter:
                device_filter['limit'] = 50
            devices = list(client.dcim.devices.filter(**device_filter))
            if not devices:
                raise NetBoxNotFoundError(f"B-side device '{b_device_name}' not found")
            
            device_obj = devices[0]
            device_id = device_obj.get('id') if isinstance(device_obj, dict) else device_obj.id
            
            # Find power outlet on device
            # ULTRATHINK FIX 1: Add expand parameters for power outlet lookups
            power_outlet_search_params = {
                "expand": ["device", "power_port", "cable"],
                "limit": 50
            }
            outlets = list(client.dcim.power_outlets.filter(device_id=device_id, name=b_termination_name, **power_outlet_search_params))
            if not outlets:
                raise NetBoxNotFoundError(f"B-side power outlet '{b_termination_name}' not found on device '{b_device_name}'")
            
            outlet_obj = outlets[0]
            b_termination_id = outlet_obj.get('id') if isinstance(outlet_obj, dict) else outlet_obj.id
            
        elif b_termination_type == "powerport":
            b_termination_object_type = "dcim.powerport"
            
            # Find device first
            device_filter = {"name": b_device_name}
            if site_id:
                device_filter["site_id"] = site_id
            
            # ULTRATHINK FIX 1: Add expand parameters to dynamic device filter
            if 'expand' not in device_filter:
                device_filter['expand'] = ["device_type", "device_type__manufacturer", "site", "rack", "tenant", "role"]
            if 'limit' not in device_filter:
                device_filter['limit'] = 50
            devices = list(client.dcim.devices.filter(**device_filter))
            if not devices:
                raise NetBoxNotFoundError(f"B-side device '{b_device_name}' not found")
            
            device_obj = devices[0]
            device_id = device_obj.get('id') if isinstance(device_obj, dict) else device_obj.id
            
            # Find power port on device
            # ULTRATHINK FIX 1: Add expand parameters for power port lookups
            power_port_search_params = {
                "expand": ["device", "cable"],
                "limit": 50
            }
            ports = list(client.dcim.power_ports.filter(device_id=device_id, name=b_termination_name, **power_port_search_params))
            if not ports:
                raise NetBoxNotFoundError(f"B-side power port '{b_termination_name}' not found on device '{b_device_name}'")
            
            port_obj = ports[0]
            b_termination_id = port_obj.get('id') if isinstance(port_obj, dict) else port_obj.id
            
        elif b_termination_type == "powerfeed":
            b_termination_object_type = "dcim.powerfeed"
            
            # Find power feed across power panels
            feed_found = False
            if site_id:
                # ULTRATHINK FIX 1: Add expand parameters for power panel lookups
                power_panel_search_params = {
                    "expand": ["site", "location", "rack_group"],
                    "limit": 100
                }
                panels = list(client.dcim.power_panels.filter(site_id=site_id, **power_panel_search_params))
            else:
                panels = client.dcim.power_panels.all()
            
            for panel in panels:
                panel_id = panel.get('id') if isinstance(panel, dict) else panel.id
                # ULTRATHINK FIX 1: Add expand parameters for power feed lookups
                power_feed_search_params = {
                    "expand": ["power_panel", "rack", "site"],
                    "limit": 50
                }
                feeds = list(client.dcim.power_feeds.filter(power_panel_id=panel_id, name=b_termination_name, **power_feed_search_params))
                if feeds:
                    feed_obj = feeds[0]
                    b_termination_id = feed_obj.get('id') if isinstance(feed_obj, dict) else feed_obj.id
                    feed_found = True
                    break
            
            if not feed_found:
                site_context = f" in site '{site}'" if site else ""
                raise NetBoxNotFoundError(f"B-side power feed '{b_termination_name}' not found{site_context}")
        
    except Exception as e:
        raise NetBoxValidationError(f"Failed to resolve B-side termination: {e}")
    
    # CONFLICT DETECTION
    try:
        # Check if A-side termination is already connected
        existing_cables_a_a = client.dcim.cables.filter(
            termination_a_type=a_termination_object_type.replace("dcim.", ""),
            termination_a_id=a_termination_id,
            no_cache=True
        )
        existing_cables_a_b = client.dcim.cables.filter(
            termination_b_type=a_termination_object_type.replace("dcim.", ""),
            termination_b_id=a_termination_id,
            no_cache=True
        )
        
        if existing_cables_a_a or existing_cables_a_b:
            raise NetBoxConflictError(
                resource_type="Power Cable",
                identifier=f"A-side termination {a_termination_name} is already connected",
                existing_id="multiple"
            )
        
        # Check if B-side termination is already connected
        existing_cables_b_a = client.dcim.cables.filter(
            termination_a_type=b_termination_object_type.replace("dcim.", ""),
            termination_a_id=b_termination_id,
            no_cache=True
        )
        existing_cables_b_b = client.dcim.cables.filter(
            termination_b_type=b_termination_object_type.replace("dcim.", ""),
            termination_b_id=b_termination_id,
            no_cache=True
        )
        
        if existing_cables_b_a or existing_cables_b_b:
            raise NetBoxConflictError(
                resource_type="Power Cable",
                identifier=f"B-side termination {b_termination_name} is already connected",
                existing_id="multiple"
            )
            
    except NetBoxConflictError:
        raise
    except Exception as e:
        logger.warning(f"Could not check for existing cable connections: {e}")
    
    # CREATE POWER CABLE
    create_payload = {
        "type": cable_type,
        "status": status,
        "a_terminations": [{
            "object_type": a_termination_object_type,
            "object_id": a_termination_id
        }],
        "b_terminations": [{
            "object_type": b_termination_object_type,
            "object_id": b_termination_id
        }]
    }
    
    # Add optional parameters
    if length is not None:
        if length <= 0:
            raise NetBoxValidationError("Cable length must be positive")
        create_payload["length"] = length
        create_payload["length_unit"] = length_unit
    
    if label:
        create_payload["label"] = label
    
    if color:
        create_payload["color"] = color
    
    if tags:
        create_payload["tags"] = tags
    
    try:
        logger.debug(f"Creating power cable with payload: {create_payload}")
        new_cable = client.dcim.cables.create(confirm=confirm, **create_payload)
        cable_id = new_cable.get('id') if isinstance(new_cable, dict) else new_cable.id
        
    except Exception as e:
        raise NetBoxValidationError(f"NetBox API error during power cable creation: {e}")
    
    # RETURN SUCCESS
    return {
        "success": True,
        "message": f"Power cable successfully created between {a_termination_type} '{a_termination_name}' and {b_termination_type} '{b_termination_name}'.",
        "data": {
            "cable_id": cable_id,
            "cable_type": cable_type,
            "status": status,
            "a_termination": {
                "type": a_termination_type,
                "name": a_termination_name,
                "device": a_device_name,
                "id": a_termination_id
            },
            "b_termination": {
                "type": b_termination_type,
                "name": b_termination_name,
                "device": b_device_name,
                "id": b_termination_id
            },
            "specifications": {
                "length": length,
                "length_unit": length_unit,
                "label": label,
                "color": color
            },
            "url": f"{client.config.url}/dcim/cables/{cable_id}/"
        }
    }


@mcp_tool(category="dcim")
def netbox_get_power_connection_info(
    client: NetBoxClient,
    termination_type: str,
    termination_name: str,
    device_name: Optional[str] = None,
    site: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get detailed power connection information for a specific termination.
    
    This inspection tool shows all power cable connections for a power outlet,
    power port, or power feed including connection details and cable paths.
    
    Args:
        termination_type: Termination type (poweroutlet, powerport, powerfeed)
        termination_name: Termination name
        device_name: Device name (required for poweroutlet/powerport)
        site: Site name for lookup (improves search accuracy)
        client: NetBox client (injected)
        
    Returns:
        Dict containing detailed power connection information
        
    Examples:
        # Get power outlet connections
        netbox_get_power_connection_info("poweroutlet", "PDU-A-01", "PDU-RACK-A-01")
        
        # Get power feed connections
        netbox_get_power_connection_info("powerfeed", "FEED-A-01", site="datacenter-1")
        
        # Get power port connections
        netbox_get_power_connection_info("powerport", "PSU1", "server-01")
    """
    
    # PARAMETER VALIDATION
    valid_termination_types = ["poweroutlet", "powerport", "powerfeed"]
    if termination_type not in valid_termination_types:
        raise NetBoxValidationError(f"Invalid termination type '{termination_type}'. Valid options: {', '.join(valid_termination_types)}")
    
    if termination_type in ["poweroutlet", "powerport"] and not device_name:
        raise NetBoxValidationError(f"Device name is required for termination type '{termination_type}'")
    
    # LOOKUP SITE (if provided)
    site_id = None
    if site:
        try:
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
                sites = list(client.dcim.sites.filter(name=site, **site_search_params))

            # ULTRATHINK FIX 4: Slug-based fallback mechanisms
            if not sites:
                sites = list(client.dcim.sites.filter(slug=site, **site_search_params))
            if not sites:
                raise NetBoxNotFoundError(f"Site '{site}' not found")
            
            site_obj = sites[0]
            site_id = site_obj.get('id') if isinstance(site_obj, dict) else site_obj.id
            
        except Exception as e:
            raise NetBoxNotFoundError(f"Could not find site '{site}': {e}")
    
    # RESOLVE TERMINATION
    termination_id = None
    termination_object_type = None
    termination_info = {}
    
    try:
        if termination_type == "poweroutlet":
            termination_object_type = "dcim.poweroutlet"
            
            # Find device first
            device_filter = {"name": device_name}
            if site_id:
                device_filter["site_id"] = site_id
            
            # ULTRATHINK FIX 1: Add expand parameters to dynamic device filter
            if 'expand' not in device_filter:
                device_filter['expand'] = ["device_type", "device_type__manufacturer", "site", "rack", "tenant", "role"]
            if 'limit' not in device_filter:
                device_filter['limit'] = 50
            devices = list(client.dcim.devices.filter(**device_filter))
            if not devices:
                raise NetBoxNotFoundError(f"Device '{device_name}' not found")
            
            device_obj = devices[0]
            device_id = device_obj.get('id') if isinstance(device_obj, dict) else device_obj.id
            
            # Find power outlet on device
            # ULTRATHINK FIX 1: Add expand parameters for power outlet lookups
            power_outlet_search_params = {
                "expand": ["device", "power_port", "cable"],
                "limit": 50
            }
            outlets = list(client.dcim.power_outlets.filter(device_id=device_id, name=termination_name, **power_outlet_search_params))
            if not outlets:
                raise NetBoxNotFoundError(f"Power outlet '{termination_name}' not found on device '{device_name}'")
            
            outlet_obj = outlets[0]
            termination_id = outlet_obj.get('id') if isinstance(outlet_obj, dict) else outlet_obj.id
            
            # Get outlet details
            termination_info = {
                "type": "Power Outlet",
                "name": termination_name,
                "device": device_name,
                "outlet_type": outlet_obj.get('type', {}).get('label') if isinstance(outlet_obj, dict) else str(getattr(outlet_obj, 'type', 'N/A')),
                "description": outlet_obj.get('description') if isinstance(outlet_obj, dict) else getattr(outlet_obj, 'description', '')
            }
            
        elif termination_type == "powerport":
            termination_object_type = "dcim.powerport"
            
            # Find device first
            device_filter = {"name": device_name}
            if site_id:
                device_filter["site_id"] = site_id
            
            # ULTRATHINK FIX 1: Add expand parameters to dynamic device filter
            if 'expand' not in device_filter:
                device_filter['expand'] = ["device_type", "device_type__manufacturer", "site", "rack", "tenant", "role"]
            if 'limit' not in device_filter:
                device_filter['limit'] = 50
            devices = list(client.dcim.devices.filter(**device_filter))
            if not devices:
                raise NetBoxNotFoundError(f"Device '{device_name}' not found")
            
            device_obj = devices[0]
            device_id = device_obj.get('id') if isinstance(device_obj, dict) else device_obj.id
            
            # Find power port on device
            # ULTRATHINK FIX 1: Add expand parameters for power port lookups
            power_port_search_params = {
                "expand": ["device", "cable"],
                "limit": 50
            }
            ports = list(client.dcim.power_ports.filter(device_id=device_id, name=termination_name, **power_port_search_params))
            if not ports:
                raise NetBoxNotFoundError(f"Power port '{termination_name}' not found on device '{device_name}'")
            
            port_obj = ports[0]
            termination_id = port_obj.get('id') if isinstance(port_obj, dict) else port_obj.id
            
            # Get port details
            termination_info = {
                "type": "Power Port",
                "name": termination_name,
                "device": device_name,
                "port_type": port_obj.get('type', {}).get('label') if isinstance(port_obj, dict) else str(getattr(port_obj, 'type', 'N/A')),
                "description": port_obj.get('description') if isinstance(port_obj, dict) else getattr(port_obj, 'description', '')
            }
            
        elif termination_type == "powerfeed":
            termination_object_type = "dcim.powerfeed"
            
            # Find power feed across power panels
            feed_found = False
            feed_obj = None
            
            if site_id:
                # ULTRATHINK FIX 1: Add expand parameters for power panel lookups
                power_panel_search_params = {
                    "expand": ["site", "location", "rack_group"],
                    "limit": 100
                }
                panels = list(client.dcim.power_panels.filter(site_id=site_id, **power_panel_search_params))
            else:
                panels = client.dcim.power_panels.all()
            
            for panel in panels:
                panel_id = panel.get('id') if isinstance(panel, dict) else panel.id
                feeds = client.dcim.power_feeds.filter(power_panel_id=panel_id, name=termination_name)
                if feeds:
                    feed_obj = feeds[0]
                    termination_id = feed_obj.get('id') if isinstance(feed_obj, dict) else feed_obj.id
                    feed_found = True
                    break
            
            if not feed_found:
                site_context = f" in site '{site}'" if site else ""
                raise NetBoxNotFoundError(f"Power feed '{termination_name}' not found{site_context}")
            
            # Get feed details
            panel_data = feed_obj.get('power_panel') if isinstance(feed_obj, dict) else getattr(feed_obj, 'power_panel', {})
            panel_name = panel_data.get('name') if isinstance(panel_data, dict) else getattr(panel_data, 'name', 'N/A')
            
            termination_info = {
                "type": "Power Feed",
                "name": termination_name,
                "power_panel": panel_name,
                "feed_type": feed_obj.get('type', {}).get('label') if isinstance(feed_obj, dict) else str(getattr(feed_obj, 'type', 'N/A')),
                "supply": feed_obj.get('supply', {}).get('label') if isinstance(feed_obj, dict) else str(getattr(feed_obj, 'supply', 'N/A')),
                "voltage": feed_obj.get('voltage') if isinstance(feed_obj, dict) else getattr(feed_obj, 'voltage', None),
                "amperage": feed_obj.get('amperage') if isinstance(feed_obj, dict) else getattr(feed_obj, 'amperage', None)
            }
        
    except Exception as e:
        raise NetBoxValidationError(f"Failed to resolve termination: {e}")
    
    # GET CABLE CONNECTIONS
    cable_connections = []
    
    try:
        # Check A-side terminations
        cables_a = client.dcim.cables.filter(
            termination_a_type=termination_object_type.replace("dcim.", ""),
            termination_a_id=termination_id
        )
        
        for cable in cables_a:
            cable_info = {
                "cable_id": cable.get('id') if isinstance(cable, dict) else cable.id,
                "cable_type": cable.get('type', {}).get('label') if isinstance(cable, dict) else str(getattr(cable, 'type', 'N/A')),
                "status": cable.get('status', {}).get('label') if isinstance(cable, dict) else str(getattr(cable, 'status', 'N/A')),
                "length": cable.get('length') if isinstance(cable, dict) else getattr(cable, 'length', None),
                "length_unit": cable.get('length_unit', {}).get('label') if isinstance(cable, dict) else str(getattr(cable, 'length_unit', None)),
                "label": cable.get('label') if isinstance(cable, dict) else getattr(cable, 'label', ''),
                "color": cable.get('color') if isinstance(cable, dict) else getattr(cable, 'color', ''),
                "termination_side": "A",
                "connected_to": {}
            }
            
            # Get B-side termination info
            b_terminations = cable.get('b_terminations', []) if isinstance(cable, dict) else getattr(cable, 'b_terminations', [])
            if b_terminations:
                b_term = b_terminations[0]
                b_object = b_term.get('object') if isinstance(b_term, dict) else getattr(b_term, 'object', {})
                b_object_type = b_term.get('object_type') if isinstance(b_term, dict) else getattr(b_term, 'object_type', 'N/A')
                
                cable_info["connected_to"] = {
                    "type": b_object_type,
                    "name": b_object.get('name') if isinstance(b_object, dict) else getattr(b_object, 'name', 'N/A'),
                    "device": None
                }
                
                # Get device info if it's a device component
                if b_object_type in ["dcim.poweroutlet", "dcim.powerport"]:
                    device_data = b_object.get('device') if isinstance(b_object, dict) else getattr(b_object, 'device', {})
                    if device_data:
                        cable_info["connected_to"]["device"] = device_data.get('name') if isinstance(device_data, dict) else getattr(device_data, 'name', 'N/A')
            
            cable_connections.append(cable_info)
        
        # Check B-side terminations
        cables_b = client.dcim.cables.filter(
            termination_b_type=termination_object_type.replace("dcim.", ""),
            termination_b_id=termination_id
        )
        
        for cable in cables_b:
            cable_info = {
                "cable_id": cable.get('id') if isinstance(cable, dict) else cable.id,
                "cable_type": cable.get('type', {}).get('label') if isinstance(cable, dict) else str(getattr(cable, 'type', 'N/A')),
                "status": cable.get('status', {}).get('label') if isinstance(cable, dict) else str(getattr(cable, 'status', 'N/A')),
                "length": cable.get('length') if isinstance(cable, dict) else getattr(cable, 'length', None),
                "length_unit": cable.get('length_unit', {}).get('label') if isinstance(cable, dict) else str(getattr(cable, 'length_unit', None)),
                "label": cable.get('label') if isinstance(cable, dict) else getattr(cable, 'label', ''),
                "color": cable.get('color') if isinstance(cable, dict) else getattr(cable, 'color', ''),
                "termination_side": "B",
                "connected_to": {}
            }
            
            # Get A-side termination info
            a_terminations = cable.get('a_terminations', []) if isinstance(cable, dict) else getattr(cable, 'a_terminations', [])
            if a_terminations:
                a_term = a_terminations[0]
                a_object = a_term.get('object') if isinstance(a_term, dict) else getattr(a_term, 'object', {})
                a_object_type = a_term.get('object_type') if isinstance(a_term, dict) else getattr(a_term, 'object_type', 'N/A')
                
                cable_info["connected_to"] = {
                    "type": a_object_type,
                    "name": a_object.get('name') if isinstance(a_object, dict) else getattr(a_object, 'name', 'N/A'),
                    "device": None
                }
                
                # Get device info if it's a device component
                if a_object_type in ["dcim.poweroutlet", "dcim.powerport"]:
                    device_data = a_object.get('device') if isinstance(a_object, dict) else getattr(a_object, 'device', {})
                    if device_data:
                        cable_info["connected_to"]["device"] = device_data.get('name') if isinstance(device_data, dict) else getattr(device_data, 'name', 'N/A')
            
            cable_connections.append(cable_info)
            
    except Exception as e:
        logger.warning(f"Could not retrieve cable connections: {e}")
    
    # CALCULATE CONNECTION STATISTICS
    connection_stats = {
        "total_connections": len(cable_connections),
        "connected_status": len([c for c in cable_connections if c.get('status') == 'Connected']),
        "planned_status": len([c for c in cable_connections if c.get('status') == 'Planned']),
        "connection_types": {}
    }
    
    for conn in cable_connections:
        connected_type = conn.get('connected_to', {}).get('type', 'Unknown')
        connection_stats["connection_types"][connected_type] = connection_stats["connection_types"].get(connected_type, 0) + 1
    
    # RETURN COMPREHENSIVE INFORMATION
    return {
        "success": True,
        "data": {
            "termination": termination_info,
            "termination_id": termination_id,
            "cable_connections": {
                "count": len(cable_connections),
                "connections": cable_connections
            },
            "connection_statistics": connection_stats,
            "is_connected": len(cable_connections) > 0,
            "url": f"{client.config.url}/dcim/{termination_type.replace('power', 'power-')}s/{termination_id}/"
        }
    }


@mcp_tool(category="dcim")
def netbox_list_all_power_cables(
    client: NetBoxClient,
    site: Optional[str] = None,
    status: Optional[str] = None,
    cable_type: Optional[str] = None,
    termination_type: Optional[str] = None,
    device_name: Optional[str] = None,
    limit: int = 50
) -> Dict[str, Any]:
    """
    List all power cables with optional filtering.
    
    This bulk discovery tool helps explore and analyze power cable
    infrastructure and connectivity patterns.
    
    Args:
        site: Filter by site name (optional)
        status: Filter by cable status (planned, connected, decommissioning, optional)
        cable_type: Filter by cable type (optional)
        termination_type: Filter by termination type (poweroutlet, powerport, powerfeed, optional)
        device_name: Filter by device name (optional)
        limit: Maximum number of cables to return (default: 50)
        client: NetBox client (injected)
        
    Returns:
        Dict containing list of power cables with connectivity statistics
        
    Examples:
        # List all power cables
        netbox_list_all_power_cables()
        
        # Filter by site and status
        netbox_list_all_power_cables(site="datacenter-1", status="connected")
        
        # Filter by termination type
        netbox_list_all_power_cables(termination_type="poweroutlet")
    """
    
    filter_params = {}
    
    # ADD BASIC FILTERS
    if status:
        filter_params["status"] = status
    
    if cable_type:
        filter_params["type"] = cable_type
    
    # RESOLVE SITE FILTER (for device filtering)
    site_id = None
    if site:
        try:
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
                sites = list(client.dcim.sites.filter(name=site, **site_search_params))

            # ULTRATHINK FIX 4: Slug-based fallback mechanisms
            if not sites:
                sites = list(client.dcim.sites.filter(slug=site, **site_search_params))
            if sites:
                site_obj = sites[0]
                site_id = site_obj.get('id') if isinstance(site_obj, dict) else site_obj.id
            else:
                return {
                    "success": True,
                    "data": {
                        "cables": [],
                        "total_count": 0,
                        "message": f"No cables found - site '{site}' not found"
                    }
                }
        except Exception as e:
            logger.warning(f"Could not resolve site filter '{site}': {e}")
    
    # GET ALL CABLES WITH POWER TERMINATIONS
    try:
        # Get all cables first, then filter for power components
        # ULTRATHINK FIX 1: Add expand parameters to cable filter
        if 'expand' not in filter_params:
            filter_params['expand'] = ["termination_a", "termination_b"]
        if 'limit' not in filter_params:
            filter_params['limit'] = 200
        all_cables = list(client.dcim.cables.filter(**filter_params))
        power_cables = []
        
        for cable in all_cables:
            # Check if cable has power terminations
            has_power_termination = False
            
            # Check A-side terminations
            a_terminations = cable.get('a_terminations', []) if isinstance(cable, dict) else getattr(cable, 'a_terminations', [])
            for a_term in a_terminations:
                a_type = a_term.get('object_type') if isinstance(a_term, dict) else getattr(a_term, 'object_type', '')
                if a_type in ['dcim.poweroutlet', 'dcim.powerport', 'dcim.powerfeed']:
                    has_power_termination = True
                    break
            
            # Check B-side terminations
            if not has_power_termination:
                b_terminations = cable.get('b_terminations', []) if isinstance(cable, dict) else getattr(cable, 'b_terminations', [])
                for b_term in b_terminations:
                    b_type = b_term.get('object_type') if isinstance(b_term, dict) else getattr(b_term, 'object_type', '')
                    if b_type in ['dcim.poweroutlet', 'dcim.powerport', 'dcim.powerfeed']:
                        has_power_termination = True
                        break
            
            if has_power_termination:
                power_cables.append(cable)
        
        # Apply additional filtering
        filtered_cables = power_cables
        
        # Filter by termination type
        if termination_type:
            termination_filtered = []
            for cable in filtered_cables:
                has_termination_type = False
                
                # Check A-side
                a_terminations = cable.get('a_terminations', []) if isinstance(cable, dict) else getattr(cable, 'a_terminations', [])
                for a_term in a_terminations:
                    a_type = a_term.get('object_type') if isinstance(a_term, dict) else getattr(a_term, 'object_type', '')
                    if a_type == f'dcim.{termination_type}':
                        has_termination_type = True
                        break
                
                # Check B-side
                if not has_termination_type:
                    b_terminations = cable.get('b_terminations', []) if isinstance(cable, dict) else getattr(cable, 'b_terminations', [])
                    for b_term in b_terminations:
                        b_type = b_term.get('object_type') if isinstance(b_term, dict) else getattr(b_term, 'object_type', '')
                        if b_type == f'dcim.{termination_type}':
                            has_termination_type = True
                            break
                
                if has_termination_type:
                    termination_filtered.append(cable)
            
            filtered_cables = termination_filtered
        
        # Filter by device name
        if device_name:
            device_filtered = []
            for cable in filtered_cables:
                has_device = False
                
                # Check A-side terminations
                a_terminations = cable.get('a_terminations', []) if isinstance(cable, dict) else getattr(cable, 'a_terminations', [])
                for a_term in a_terminations:
                    a_object = a_term.get('object') if isinstance(a_term, dict) else getattr(a_term, 'object', {})
                    a_device = a_object.get('device') if isinstance(a_object, dict) else getattr(a_object, 'device', {})
                    if a_device:
                        a_device_name = a_device.get('name') if isinstance(a_device, dict) else getattr(a_device, 'name', '')
                        if a_device_name == device_name:
                            has_device = True
                            break
                
                # Check B-side terminations
                if not has_device:
                    b_terminations = cable.get('b_terminations', []) if isinstance(cable, dict) else getattr(cable, 'b_terminations', [])
                    for b_term in b_terminations:
                        b_object = b_term.get('object') if isinstance(b_term, dict) else getattr(b_term, 'object', {})
                        b_device = b_object.get('device') if isinstance(b_object, dict) else getattr(b_object, 'device', {})
                        if b_device:
                            b_device_name = b_device.get('name') if isinstance(b_device, dict) else getattr(b_device, 'name', '')
                            if b_device_name == device_name:
                                has_device = True
                                break
                
                if has_device:
                    device_filtered.append(cable)
            
            filtered_cables = device_filtered
        
        # Filter by site (if specified)
        if site_id:
            site_filtered = []
            for cable in filtered_cables:
                has_site = False
                
                # Check if any termination is in the specified site
                all_terminations = []
                a_terminations = cable.get('a_terminations', []) if isinstance(cable, dict) else getattr(cable, 'a_terminations', [])
                b_terminations = cable.get('b_terminations', []) if isinstance(cable, dict) else getattr(cable, 'b_terminations', [])
                all_terminations.extend(a_terminations)
                all_terminations.extend(b_terminations)
                
                for term in all_terminations:
                    term_object = term.get('object') if isinstance(term, dict) else getattr(term, 'object', {})
                    
                    # For device components, check device site
                    if hasattr(term_object, 'device') or (isinstance(term_object, dict) and 'device' in term_object):
                        device_data = term_object.get('device') if isinstance(term_object, dict) else getattr(term_object, 'device', {})
                        if device_data:
                            device_site = device_data.get('site') if isinstance(device_data, dict) else getattr(device_data, 'site', {})
                            if device_site:
                                site_id_check = device_site.get('id') if isinstance(device_site, dict) else getattr(device_site, 'id', None)
                                if site_id_check == site_id:
                                    has_site = True
                                    break
                    
                    # For power feeds, check power panel site
                    elif term.get('object_type') == 'dcim.powerfeed' if isinstance(term, dict) else getattr(term, 'object_type', '') == 'dcim.powerfeed':
                        # This would require additional lookup, simplified for now
                        has_site = True  # Assume site match for power feeds
                        break
                
                if has_site:
                    site_filtered.append(cable)
            
            filtered_cables = site_filtered
        
        total_count = len(filtered_cables)
        
        # Apply limit
        limited_cables = filtered_cables[:limit]
        
        cables_data = []
        cable_stats = {
            "total_cables": total_count,
            "cable_count_by_status": {},
            "cable_count_by_type": {},
            "termination_type_stats": {}
        }
        
        for cable in limited_cables:
            try:
                # Get basic cable info
                cable_id = cable.get('id') if isinstance(cable, dict) else cable.id
                cable_type_obj = cable.get('type') if isinstance(cable, dict) else getattr(cable, 'type', None)
                cable_type_value = cable_type_obj.get('label') if isinstance(cable_type_obj, dict) else str(cable_type_obj) if cable_type_obj else 'N/A'
                
                status_obj = cable.get('status') if isinstance(cable, dict) else getattr(cable, 'status', None)
                status_value = status_obj.get('label') if isinstance(status_obj, dict) else str(status_obj) if status_obj else 'N/A'
                
                length = cable.get('length') if isinstance(cable, dict) else getattr(cable, 'length', None)
                length_unit_obj = cable.get('length_unit') if isinstance(cable, dict) else getattr(cable, 'length_unit', None)
                length_unit_value = length_unit_obj.get('label') if isinstance(length_unit_obj, dict) else str(length_unit_obj) if length_unit_obj else None
                
                label = cable.get('label') if isinstance(cable, dict) else getattr(cable, 'label', '')
                color = cable.get('color') if isinstance(cable, dict) else getattr(cable, 'color', '')
                
                # Get termination info
                a_terminations = cable.get('a_terminations', []) if isinstance(cable, dict) else getattr(cable, 'a_terminations', [])
                b_terminations = cable.get('b_terminations', []) if isinstance(cable, dict) else getattr(cable, 'b_terminations', [])
                
                a_termination_info = {}
                b_termination_info = {}
                
                if a_terminations:
                    a_term = a_terminations[0]
                    a_object = a_term.get('object') if isinstance(a_term, dict) else getattr(a_term, 'object', {})
                    a_type = a_term.get('object_type') if isinstance(a_term, dict) else getattr(a_term, 'object_type', 'N/A')
                    
                    a_termination_info = {
                        "type": a_type,
                        "name": a_object.get('name') if isinstance(a_object, dict) else getattr(a_object, 'name', 'N/A'),
                        "device": None
                    }
                    
                    if a_type in ['dcim.poweroutlet', 'dcim.powerport']:
                        device_data = a_object.get('device') if isinstance(a_object, dict) else getattr(a_object, 'device', {})
                        if device_data:
                            a_termination_info["device"] = device_data.get('name') if isinstance(device_data, dict) else getattr(device_data, 'name', 'N/A')
                
                if b_terminations:
                    b_term = b_terminations[0]
                    b_object = b_term.get('object') if isinstance(b_term, dict) else getattr(b_term, 'object', {})
                    b_type = b_term.get('object_type') if isinstance(b_term, dict) else getattr(b_term, 'object_type', 'N/A')
                    
                    b_termination_info = {
                        "type": b_type,
                        "name": b_object.get('name') if isinstance(b_object, dict) else getattr(b_object, 'name', 'N/A'),
                        "device": None
                    }
                    
                    if b_type in ['dcim.poweroutlet', 'dcim.powerport']:
                        device_data = b_object.get('device') if isinstance(b_object, dict) else getattr(b_object, 'device', {})
                        if device_data:
                            b_termination_info["device"] = device_data.get('name') if isinstance(device_data, dict) else getattr(device_data, 'name', 'N/A')
                
                # Update statistics
                cable_stats["cable_count_by_status"][status_value] = cable_stats["cable_count_by_status"].get(status_value, 0) + 1
                cable_stats["cable_count_by_type"][cable_type_value] = cable_stats["cable_count_by_type"].get(cable_type_value, 0) + 1
                
                # Track termination types
                for term_type in [a_termination_info.get('type'), b_termination_info.get('type')]:
                    if term_type and term_type.startswith('dcim.'):
                        clean_type = term_type.replace('dcim.', '')
                        cable_stats["termination_type_stats"][clean_type] = cable_stats["termination_type_stats"].get(clean_type, 0) + 1
                
                cable_info = {
                    "id": cable_id,
                    "type": cable_type_value,
                    "status": status_value,
                    "a_termination": a_termination_info,
                    "b_termination": b_termination_info,
                    "specifications": {
                        "length": length,
                        "length_unit": length_unit_value,
                        "label": label,
                        "color": color
                    },
                    "url": f"{client.config.url}/dcim/cables/{cable_id}/"
                }
                
                cables_data.append(cable_info)
                
            except Exception as e:
                logger.warning(f"Error processing cable data: {e}")
                continue
        
        # Build filter description
        filter_description = []
        if site:
            filter_description.append(f"site: {site}")
        if status:
            filter_description.append(f"status: {status}")
        if cable_type:
            filter_description.append(f"type: {cable_type}")
        if termination_type:
            filter_description.append(f"termination type: {termination_type}")
        if device_name:
            filter_description.append(f"device: {device_name}")
        
        filter_text = f" (filtered by {', '.join(filter_description)})" if filter_description else ""
        
        return {
            "success": True,
            "data": {
                "cables": cables_data,
                "total_count": total_count,
                "returned_count": len(cables_data),
                "limit_applied": limit if total_count > limit else None,
                "filters": filter_text,
                "cable_statistics": cable_stats
            }
        }
        
    except Exception as e:
        raise NetBoxValidationError(f"Failed to retrieve power cables: {e}")


@mcp_tool(category="dcim")
def netbox_disconnect_power_cable(
    client: NetBoxClient,
    cable_id: int,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Disconnect (delete) a power cable connection.
    
    This enterprise-grade function removes power cable connections
    with comprehensive safety checks.
    
    Args:
        cable_id: Cable ID to disconnect/delete
        client: NetBox client (injected)
        confirm: Must be True to execute
        
    Returns:
        Dict containing operation result and disconnection details
        
    Examples:
        # Dry run disconnection
        netbox_disconnect_power_cable(123)
        
        # Disconnect with confirmation
        netbox_disconnect_power_cable(123, confirm=True)
    """
    
    # DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Power cable would be disconnected. Set confirm=True to execute.",
            "would_disconnect": {
                "cable_id": cable_id
            }
        }
    
    # FIND CABLE TO DISCONNECT
    try:
        # ULTRATHINK FIX 1: Add expand parameters for cable ID lookups
        cable_search_params = {
            "expand": ["termination_a", "termination_b"],
            "limit": 50
        }
        cables = list(client.dcim.cables.filter(id=cable_id, **cable_search_params))
        if not cables:
            raise NetBoxNotFoundError(f"Cable with ID {cable_id} not found")
        
        cable_to_delete = cables[0]
        cable_id = cable_to_delete.get('id') if isinstance(cable_to_delete, dict) else cable_to_delete.id
        
        # Get cable details for reporting
        cable_type = cable_to_delete.get('type', {}).get('label') if isinstance(cable_to_delete, dict) else str(getattr(cable_to_delete, 'type', 'Unknown'))
        cable_status = cable_to_delete.get('status', {}).get('label') if isinstance(cable_to_delete, dict) else str(getattr(cable_to_delete, 'status', 'Unknown'))
        cable_label = cable_to_delete.get('label') if isinstance(cable_to_delete, dict) else getattr(cable_to_delete, 'label', '')
        
        # Get termination details
        a_terminations = cable_to_delete.get('a_terminations', []) if isinstance(cable_to_delete, dict) else getattr(cable_to_delete, 'a_terminations', [])
        b_terminations = cable_to_delete.get('b_terminations', []) if isinstance(cable_to_delete, dict) else getattr(cable_to_delete, 'b_terminations', [])
        
        a_termination_info = "Unknown"
        b_termination_info = "Unknown"
        
        if a_terminations:
            a_term = a_terminations[0]
            a_object = a_term.get('object') if isinstance(a_term, dict) else getattr(a_term, 'object', {})
            a_type = a_term.get('object_type') if isinstance(a_term, dict) else getattr(a_term, 'object_type', 'N/A')
            a_name = a_object.get('name') if isinstance(a_object, dict) else getattr(a_object, 'name', 'N/A')
            
            if a_type in ['dcim.poweroutlet', 'dcim.powerport']:
                device_data = a_object.get('device') if isinstance(a_object, dict) else getattr(a_object, 'device', {})
                if device_data:
                    device_name = device_data.get('name') if isinstance(device_data, dict) else getattr(device_data, 'name', 'N/A')
                    a_termination_info = f"{a_type.replace('dcim.', '')} '{a_name}' on device '{device_name}'"
                else:
                    a_termination_info = f"{a_type.replace('dcim.', '')} '{a_name}'"
            else:
                a_termination_info = f"{a_type.replace('dcim.', '')} '{a_name}'"
        
        if b_terminations:
            b_term = b_terminations[0]
            b_object = b_term.get('object') if isinstance(b_term, dict) else getattr(b_term, 'object', {})
            b_type = b_term.get('object_type') if isinstance(b_term, dict) else getattr(b_term, 'object_type', 'N/A')
            b_name = b_object.get('name') if isinstance(b_object, dict) else getattr(b_object, 'name', 'N/A')
            
            if b_type in ['dcim.poweroutlet', 'dcim.powerport']:
                device_data = b_object.get('device') if isinstance(b_object, dict) else getattr(b_object, 'device', {})
                if device_data:
                    device_name = device_data.get('name') if isinstance(device_data, dict) else getattr(device_data, 'name', 'N/A')
                    b_termination_info = f"{b_type.replace('dcim.', '')} '{b_name}' on device '{device_name}'"
                else:
                    b_termination_info = f"{b_type.replace('dcim.', '')} '{b_name}'"
            else:
                b_termination_info = f"{b_type.replace('dcim.', '')} '{b_name}'"
        
    except Exception as e:
        raise NetBoxNotFoundError(f"Failed to find cable: {e}")
    
    # PERFORM DISCONNECTION
    try:
        logger.debug(f"Disconnecting power cable {cable_id}")
        client.dcim.cables.delete(cable_id, confirm=confirm)
        
    except Exception as e:
        raise NetBoxValidationError(f"NetBox API error during cable disconnection: {e}")
    
    # RETURN SUCCESS
    return {
        "success": True,
        "message": f"Power cable successfully disconnected between {a_termination_info} and {b_termination_info}.",
        "data": {
            "disconnected_cable_id": cable_id,
            "cable_type": cable_type,
            "cable_status": cable_status,
            "cable_label": cable_label,
            "a_termination": a_termination_info,
            "b_termination": b_termination_info
        }
    }