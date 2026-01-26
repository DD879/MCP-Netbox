#!/usr/bin/env python3
"""
DCIM Power Feeds Management Tools

This module provides enterprise-grade tools for managing NetBox power feeds
including creation, updates, deletion, and information retrieval.
"""

from typing import Dict, Any, Optional, List
import logging

from netbox_mcp.registry import mcp_tool
from netbox_mcp.client import NetBoxClient
from netbox_mcp.exceptions import NetBoxValidationError, NetBoxNotFoundError, NetBoxConflictError

logger = logging.getLogger(__name__)


@mcp_tool(category="dcim")
def netbox_create_power_feed(
    client: NetBoxClient,
    name: str,
    power_panel: str,
    site: str,
    status: str = "active",
    feed_type: str = "primary",
    supply: str = "ac",
    phase: str = "single-phase",
    voltage: Optional[int] = None,
    amperage: Optional[int] = None,
    max_utilization: Optional[int] = None,
    rack: Optional[str] = None,
    comments: Optional[str] = None,
    tags: Optional[List[str]] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Create a new power feed in NetBox.
    
    This enterprise-grade function creates power feeds that connect power panels
    to rack PDUs and other power distribution equipment.
    
    Args:
        name: Power feed name/identifier
        power_panel: Power panel name (foreign key resolved)
        site: Site name for validation (foreign key resolved)
        status: Feed status (active, planned, offline, default: active)
        feed_type: Feed type (primary, redundant, default: primary)
        supply: Power supply type (ac, dc, default: ac)
        phase: Phase configuration (single-phase, three-phase, default: single-phase)
        voltage: Voltage rating in volts (optional)
        amperage: Amperage rating in amps (optional)
        max_utilization: Maximum utilization percentage (optional)
        rack: Target rack name (foreign key resolved, optional)
        comments: Additional comments
        tags: List of tags to assign
        client: NetBox client (injected)
        confirm: Must be True to execute
        
    Returns:
        Dict containing operation result and power feed details
        
    Examples:
        # Dry run
        netbox_create_power_feed("FEED-A-01", "PANEL-A-01", "datacenter-1")
        
        # Create feed with specifications
        netbox_create_power_feed("FEED-A-01", "PANEL-A-01", "datacenter-1",
                                voltage=120, amperage=20, rack="RACK-A-01", confirm=True)
    """
    
    # DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Power feed would be created. Set confirm=True to execute.",
            "would_create": {
                "name": name,
                "power_panel": power_panel,
                "site": site,
                "status": status,
                "type": feed_type,
                "supply": supply,
                "phase": phase,
                "voltage": voltage,
                "amperage": amperage,
                "max_utilization": max_utilization,
                "rack": rack,
                "comments": comments,
                "tags": tags
            }
        }
    
    # PARAMETER VALIDATION
    if not name or not name.strip():
        raise NetBoxValidationError("Power feed name cannot be empty")
    
    if not power_panel or not power_panel.strip():
        raise NetBoxValidationError("Power panel is required for power feed creation")
    
    if not site or not site.strip():
        raise NetBoxValidationError("Site is required for power feed creation")
    
    # Validate choice fields
    valid_statuses = ["planned", "active", "offline", "decommissioning"]
    if status not in valid_statuses:
        raise NetBoxValidationError(f"Invalid status '{status}'. Valid options: {', '.join(valid_statuses)}")
    
    valid_types = ["primary", "redundant"]
    if feed_type not in valid_types:
        raise NetBoxValidationError(f"Invalid type '{feed_type}'. Valid options: {', '.join(valid_types)}")
    
    valid_supplies = ["ac", "dc"]
    if supply not in valid_supplies:
        raise NetBoxValidationError(f"Invalid supply '{supply}'. Valid options: {', '.join(valid_supplies)}")
    
    valid_phases = ["single-phase", "three-phase"]
    if phase not in valid_phases:
        raise NetBoxValidationError(f"Invalid phase '{phase}'. Valid options: {', '.join(valid_phases)}")
    
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
    
    # LOOKUP POWER PANEL
    try:
        panels = client.dcim.power_panels.filter(site_id=site_id, name=power_panel)
        if not panels:
            raise NetBoxNotFoundError(f"Power panel '{power_panel}' not found in site '{site}'")
        
        panel_obj = panels[0]
        panel_id = panel_obj.get('id') if isinstance(panel_obj, dict) else panel_obj.id
        panel_display = panel_obj.get('display', power_panel) if isinstance(panel_obj, dict) else getattr(panel_obj, 'display', power_panel)
        
    except Exception as e:
        raise NetBoxValidationError(f"Failed to resolve power panel '{power_panel}': {e}")
    
    # LOOKUP RACK (if provided)
    rack_id = None
    rack_display = None
    if rack:
        try:
            racks = client.dcim.racks.filter(site_id=site_id, name=rack)
            if not racks:
                raise NetBoxNotFoundError(f"Rack '{rack}' not found in site '{site}'")
            
            rack_obj = racks[0]
            rack_id = rack_obj.get('id') if isinstance(rack_obj, dict) else rack_obj.id
            rack_display = rack_obj.get('display', rack) if isinstance(rack_obj, dict) else getattr(rack_obj, 'display', rack)
            
        except Exception as e:
            raise NetBoxValidationError(f"Failed to resolve rack '{rack}': {e}")
    
    # CONFLICT DETECTION
    try:
        existing_feeds = client.dcim.power_feeds.filter(
            power_panel_id=panel_id,
            name=name,
            no_cache=True
        )
        
        if existing_feeds:
            existing_feed = existing_feeds[0]
            existing_id = existing_feed.get('id') if isinstance(existing_feed, dict) else existing_feed.id
            raise NetBoxConflictError(
                resource_type="Power Feed",
                identifier=f"{name} in power panel {power_panel}",
                existing_id=existing_id
            )
    except ConflictError:
        raise
    except Exception as e:
        logger.warning(f"Could not check for existing power feeds: {e}")
    
    # CREATE POWER FEED
    create_payload = {
        "name": name,
        "power_panel": panel_id,
        "status": status,
        "type": feed_type,
        "supply": supply,
        "phase": phase,
        "comments": comments or ""
    }
    
    # Add optional parameters
    if voltage is not None:
        if voltage <= 0:
            raise NetBoxValidationError("Voltage must be positive")
        create_payload["voltage"] = voltage
    
    if amperage is not None:
        if amperage <= 0:
            raise NetBoxValidationError("Amperage must be positive")
        create_payload["amperage"] = amperage
    
    if max_utilization is not None:
        if not (0 <= max_utilization <= 100):
            raise NetBoxValidationError("Max utilization must be between 0 and 100 percent")
        create_payload["max_utilization"] = max_utilization
    
    if rack_id:
        create_payload["rack"] = rack_id
    
    if tags:
        create_payload["tags"] = tags
    
    try:
        logger.debug(f"Creating power feed with payload: {create_payload}")
        new_feed = client.dcim.power_feeds.create(confirm=confirm, **create_payload)
        feed_id = new_feed.get('id') if isinstance(new_feed, dict) else new_feed.id
        
    except Exception as e:
        raise NetBoxValidationError(f"NetBox API error during power feed creation: {e}")
    
    # RETURN SUCCESS
    return {
        "success": True,
        "message": f"Power feed '{name}' successfully created in power panel '{power_panel}'.",
        "data": {
            "feed_id": feed_id,
            "feed_name": new_feed.get('name') if isinstance(new_feed, dict) else new_feed.name,
            "power_panel_id": panel_id,
            "power_panel_name": power_panel,
            "site_id": site_id,
            "site_name": site,
            "rack_id": rack_id,
            "rack_name": rack,
            "specifications": {
                "status": status,
                "type": feed_type,
                "supply": supply,
                "phase": phase,
                "voltage": voltage,
                "amperage": amperage,
                "max_utilization": max_utilization
            },
            "url": f"{client.config.url}/dcim/power-feeds/{feed_id}/"
        }
    }


@mcp_tool(category="dcim")
def netbox_get_power_feed_info(
    client: NetBoxClient,
    feed_identifier: str,
    power_panel: Optional[str] = None,
    site: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get detailed information about a specific power feed.
    
    This inspection tool provides comprehensive power feed details including
    power consumption, connections, and utilization statistics.
    
    Args:
        feed_identifier: Power feed name or ID
        power_panel: Power panel name for feed lookup (improves search accuracy)
        site: Site name for feed lookup (improves search accuracy)
        client: NetBox client (injected)
        
    Returns:
        Dict containing detailed power feed information
        
    Examples:
        # Search by name
        netbox_get_power_feed_info("FEED-A-01")
        
        # Search with panel context
        netbox_get_power_feed_info("FEED-A-01", power_panel="PANEL-A-01")
        
        # Search with site context
        netbox_get_power_feed_info("FEED-A-01", site="datacenter-1")
    """
    
    # LOOKUP POWER FEED
    try:
        # Try lookup by ID first
        if feed_identifier.isdigit():
            feed_id = int(feed_identifier)
            feeds = client.dcim.power_feeds.filter(id=feed_id)
        else:
            # Search by name with optional context
            filter_params = {"name": feed_identifier}
            
            # Add power panel context if provided
            if power_panel:
                if site:
                    # Find panel in specific site
                    sites = client.dcim.sites.filter(name=site)
                    if sites:
                        site_obj = sites[0]
                        site_id = site_obj.get('id') if isinstance(site_obj, dict) else site_obj.id
                        # ULTRATHINK FIX 1: Expand panel search parameters
                        panel_search_params = {
                            "site_id": site_id,
                            "expand": ["site", "rack_group"],
                            "limit": 50
                        }

                        # ULTRATHINK FIX 2: Multi-strategy panel search
                        panels = None
                        if power_panel.isdigit():
                            panels = list(client.dcim.power_panels.filter(id=int(power_panel), **panel_search_params))

                        if not panels:
                            panels = list(client.dcim.power_panels.filter(name=power_panel, **panel_search_params))

                        # ULTRATHINK FIX 4: Fallback panel search
                        if not panels:
                            panels = list(client.dcim.power_panels.filter(name__icontains=power_panel, **panel_search_params))
                        if panels:
                            # ULTRATHINK FIX 3: Defensive panel handling
                            panel_obj = panels[0] if isinstance(panels, list) else panels
                            panel_id = panel_obj.get('id') if isinstance(panel_obj, dict) else getattr(panel_obj, 'id', None)
                            # panel_id may be missing; only apply filter when available
                            if panel_id:
                                filter_params["power_panel_id"] = panel_id
                else:
                    # Find panel by name only
                    panels = client.dcim.power_panels.filter(name=power_panel)
                    if panels:
                        panel_obj = panels[0]
                        panel_id = panel_obj.get('id') if isinstance(panel_obj, dict) else panel_obj.id
                        filter_params["power_panel_id"] = panel_id
            
            feeds = client.dcim.power_feeds.filter(**filter_params)
        
        if not feeds:
            identifier_desc = f"power feed '{feed_identifier}'"
            if power_panel:
                identifier_desc += f" in power panel '{power_panel}'"
            if site:
                identifier_desc += f" in site '{site}'"
            raise NetBoxNotFoundError(f"Could not find {identifier_desc}")
        
        feed = feeds[0]
        feed_id = feed.get('id') if isinstance(feed, dict) else feed.id
        feed_name = feed.get('name') if isinstance(feed, dict) else feed.name
        
    except Exception as e:
        raise NetBoxNotFoundError(f"Failed to find power feed: {e}")
    
    # GET POWER OUTLETS
    power_outlets = []
    outlet_count = 0
    try:
        outlets = client.dcim.power_outlets.filter(power_feed_id=feed_id)
        outlet_count = len(outlets)
        
        for outlet in outlets[:10]:  # Limit to 10 outlets for performance
            outlet_info = {
                "id": outlet.get('id') if isinstance(outlet, dict) else outlet.id,
                "name": outlet.get('name') if isinstance(outlet, dict) else outlet.name,
                "type": outlet.get('type', {}).get('label') if isinstance(outlet, dict) else str(getattr(outlet, 'type', 'N/A')),
                "device": outlet.get('device', {}).get('name') if isinstance(outlet, dict) else getattr(getattr(outlet, 'device', {}), 'name', 'N/A')
            }
            power_outlets.append(outlet_info)
            
    except Exception as e:
        logger.warning(f"Could not retrieve power outlets for feed {feed_id}: {e}")
    
    # GET CABLE CONNECTIONS
    connected_devices = []
    try:
        # Get cables connected to this power feed
        cables = client.dcim.cables.filter(termination_a_type="dcim.powerfeed", termination_a_id=feed_id)
        for cable in cables[:5]:  # Limit to 5 connections
            cable_info = {
                "cable_id": cable.get('id') if isinstance(cable, dict) else cable.id,
                "cable_type": cable.get('type', {}).get('label') if isinstance(cable, dict) else str(getattr(cable, 'type', 'N/A')),
                "status": cable.get('status', {}).get('label') if isinstance(cable, dict) else str(getattr(cable, 'status', 'N/A'))
            }
            connected_devices.append(cable_info)
            
        # Also check reverse connections (B-side terminations)
        cables_b = client.dcim.cables.filter(termination_b_type="dcim.powerfeed", termination_b_id=feed_id)
        for cable in cables_b[:5]:
            if len(connected_devices) >= 5:
                break
            cable_info = {
                "cable_id": cable.get('id') if isinstance(cable, dict) else cable.id,
                "cable_type": cable.get('type', {}).get('label') if isinstance(cable, dict) else str(getattr(cable, 'type', 'N/A')),
                "status": cable.get('status', {}).get('label') if isinstance(cable, dict) else str(getattr(cable, 'status', 'N/A'))
            }
            connected_devices.append(cable_info)
            
    except Exception as e:
        logger.warning(f"Could not retrieve cable connections for feed {feed_id}: {e}")
    
    # GET RELATED INFORMATION
    power_panel_info = {}
    site_info = {}
    rack_info = {}
    
    try:
        # Power panel information
        panel_data = feed.get('power_panel') if isinstance(feed, dict) else getattr(feed, 'power_panel', None)
        if panel_data:
            power_panel_info = {
                "id": panel_data.get('id') if isinstance(panel_data, dict) else getattr(panel_data, 'id', None),
                "name": panel_data.get('name') if isinstance(panel_data, dict) else getattr(panel_data, 'name', None),
                "display": panel_data.get('display') if isinstance(panel_data, dict) else getattr(panel_data, 'display', None)
            }
            
            # Get site from power panel
            if panel_data:
                panel_site_data = panel_data.get('site') if isinstance(panel_data, dict) else getattr(panel_data, 'site', None)
                if panel_site_data:
                    site_info = {
                        "id": panel_site_data.get('id') if isinstance(panel_site_data, dict) else getattr(panel_site_data, 'id', None),
                        "name": panel_site_data.get('name') if isinstance(panel_site_data, dict) else getattr(panel_site_data, 'name', None),
                        "display": panel_site_data.get('display') if isinstance(panel_site_data, dict) else getattr(panel_site_data, 'display', None)
                    }
        
        # Rack information
        rack_data = feed.get('rack') if isinstance(feed, dict) else getattr(feed, 'rack', None)
        if rack_data:
            rack_info = {
                "id": rack_data.get('id') if isinstance(rack_data, dict) else getattr(rack_data, 'id', None),
                "name": rack_data.get('name') if isinstance(rack_data, dict) else getattr(rack_data, 'name', None),
                "display": rack_data.get('display') if isinstance(rack_data, dict) else getattr(rack_data, 'display', None)
            }
            
    except Exception as e:
        logger.warning(f"Could not retrieve related information for feed {feed_id}: {e}")
    
    # GET SPECIFICATIONS
    specifications = {}
    try:
        specifications = {
            "status": feed.get('status', {}).get('label') if isinstance(feed, dict) else str(getattr(feed, 'status', 'N/A')),
            "type": feed.get('type', {}).get('label') if isinstance(feed, dict) else str(getattr(feed, 'type', 'N/A')),
            "supply": feed.get('supply', {}).get('label') if isinstance(feed, dict) else str(getattr(feed, 'supply', 'N/A')),
            "phase": feed.get('phase', {}).get('label') if isinstance(feed, dict) else str(getattr(feed, 'phase', 'N/A')),
            "voltage": feed.get('voltage') if isinstance(feed, dict) else getattr(feed, 'voltage', None),
            "amperage": feed.get('amperage') if isinstance(feed, dict) else getattr(feed, 'amperage', None),
            "max_utilization": feed.get('max_utilization') if isinstance(feed, dict) else getattr(feed, 'max_utilization', None)
        }
    except Exception as e:
        logger.warning(f"Could not retrieve specifications for feed {feed_id}: {e}")
    
    # CALCULATE UTILIZATION METRICS
    utilization_metrics = {}
    try:
        if specifications.get('voltage') and specifications.get('amperage'):
            total_capacity_watts = specifications['voltage'] * specifications['amperage']
            utilization_metrics["total_capacity_watts"] = total_capacity_watts
            utilization_metrics["total_capacity_kw"] = round(total_capacity_watts / 1000, 2)
            
            if specifications.get('max_utilization'):
                safe_capacity_watts = total_capacity_watts * (specifications['max_utilization'] / 100)
                utilization_metrics["safe_capacity_watts"] = round(safe_capacity_watts, 2)
                utilization_metrics["safe_capacity_kw"] = round(safe_capacity_watts / 1000, 2)
    except Exception as e:
        logger.warning(f"Could not calculate utilization metrics: {e}")
    
    # RETURN COMPREHENSIVE INFORMATION
    return {
        "success": True,
        "data": {
            "feed_id": feed_id,
            "name": feed_name,
            "power_panel": power_panel_info,
            "site": site_info,
            "rack": rack_info,
            "specifications": specifications,
            "utilization_metrics": utilization_metrics,
            "power_outlets": {
                "count": outlet_count,
                "outlets": power_outlets,
                "showing": f"{len(power_outlets)} of {outlet_count}" if outlet_count > 10 else f"All {outlet_count}"
            },
            "connections": {
                "count": len(connected_devices),
                "devices": connected_devices
            },
            "comments": feed.get('comments') if isinstance(feed, dict) else getattr(feed, 'comments', ''),
            "tags": feed.get('tags', []) if isinstance(feed, dict) else getattr(feed, 'tags', []),
            "created": feed.get('created') if isinstance(feed, dict) else getattr(feed, 'created', None),
            "last_updated": feed.get('last_updated') if isinstance(feed, dict) else getattr(feed, 'last_updated', None),
            "url": f"{client.config.url}/dcim/power-feeds/{feed_id}/"
        }
    }


@mcp_tool(category="dcim")
def netbox_list_all_power_feeds(
    client: NetBoxClient,
    site: Optional[str] = None,
    power_panel: Optional[str] = None,
    rack: Optional[str] = None,
    status: Optional[str] = None,
    feed_type: Optional[str] = None,
    limit: int = 50
) -> Dict[str, Any]:
    """
    List all power feeds with optional filtering.
    
    This bulk discovery tool helps explore and analyze power distribution
    infrastructure and capacity planning.
    
    Args:
        site: Filter by site name (optional)
        power_panel: Filter by power panel name (optional)
        rack: Filter by rack name (optional)
        status: Filter by status (planned, active, offline, decommissioning, optional)
        feed_type: Filter by type (primary, redundant, optional)
        limit: Maximum number of feeds to return (default: 50)
        client: NetBox client (injected)
        
    Returns:
        Dict containing list of power feeds with capacity statistics
        
    Examples:
        # List all feeds
        netbox_list_all_power_feeds()
        
        # Filter by site and status
        netbox_list_all_power_feeds(site="datacenter-1", status="active")
        
        # Filter by power panel
        netbox_list_all_power_feeds(power_panel="PANEL-A-01")
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
                        "feeds": [],
                        "total_count": 0,
                        "message": f"No feeds found - site '{site}' not found"
                    }
                }
        except Exception as e:
            logger.warning(f"Could not resolve site filter '{site}': {e}")
    
    # RESOLVE POWER PANEL FILTER
    if power_panel:
        try:
            panel_filter = {"name": power_panel}
            if "site_id" in filter_params:
                panel_filter["site_id"] = filter_params["site_id"]
                
            panels = client.dcim.power_panels.filter(**panel_filter)
            if panels:
                panel_obj = panels[0]
                panel_id = panel_obj.get('id') if isinstance(panel_obj, dict) else panel_obj.id
                filter_params["power_panel_id"] = panel_id
            else:
                return {
                    "success": True,
                    "data": {
                        "feeds": [],
                        "total_count": 0,
                        "message": f"No feeds found - power panel '{power_panel}' not found"
                    }
                }
        except Exception as e:
            logger.warning(f"Could not resolve power panel filter '{power_panel}': {e}")
    
    # RESOLVE RACK FILTER
    if rack and "site_id" in filter_params:
        try:
            # ULTRATHINK FIX 1: Expand rack search parameters
            rack_search_params = {
                "site_id": filter_params["site_id"],
                "expand": ["site", "location", "tenant", "role"],
                "limit": 50
            }

            # ULTRATHINK FIX 2: Multi-strategy rack search
            racks = None
            if rack.isdigit():
                racks = list(client.dcim.racks.filter(id=int(rack), **rack_search_params))

            if not racks:
                racks = list(client.dcim.racks.filter(name=rack, **rack_search_params))

            # ULTRATHINK FIX 4: Fallback rack search
            if not racks:
                racks = list(client.dcim.racks.filter(name__icontains=rack, **rack_search_params))
            if racks:
                # ULTRATHINK FIX 3: Defensive rack handling
                rack_obj = racks[0] if isinstance(racks, list) else racks
                rack_id = rack_obj.get('id') if isinstance(rack_obj, dict) else getattr(rack_obj, 'id', None)
                if rack_id:
                    filter_params["rack_id"] = rack_id
            else:
                return {
                    "success": True,
                    "data": {
                        "feeds": [],
                        "total_count": 0,
                        "message": f"No feeds found - rack '{rack}' not found"
                    }
                }
        except Exception as e:
            logger.warning(f"Could not resolve rack filter '{rack}': {e}")
    
    # ADD STATUS AND TYPE FILTERS
    if status:
        filter_params["status"] = status
    
    if feed_type:
        filter_params["type"] = feed_type
    
    # GET POWER FEEDS
    try:
        feeds = client.dcim.power_feeds.filter(**filter_params)
        total_count = len(feeds)
        
        # Apply limit
        limited_feeds = feeds[:limit]
        
        feeds_data = []
        capacity_stats = {
            "total_voltage": 0,
            "total_amperage": 0,
            "total_capacity_kw": 0,
            "feed_count_by_status": {},
            "feed_count_by_type": {}
        }
        
        for feed in limited_feeds:
            try:
                # Get basic feed info
                feed_id = feed.get('id') if isinstance(feed, dict) else feed.id
                feed_name = feed.get('name') if isinstance(feed, dict) else feed.name
                
                # Get power panel info
                panel_data = feed.get('power_panel') if isinstance(feed, dict) else getattr(feed, 'power_panel', {})
                panel_name = panel_data.get('name') if isinstance(panel_data, dict) else getattr(panel_data, 'name', 'N/A')
                
                # Get site info (from power panel)
                site_name = "N/A"
                if panel_data:
                    panel_site_data = panel_data.get('site') if isinstance(panel_data, dict) else getattr(panel_data, 'site', None)
                    if panel_site_data:
                        site_name = panel_site_data.get('name') if isinstance(panel_site_data, dict) else getattr(panel_site_data, 'name', 'N/A')
                
                # Get rack info
                rack_data = feed.get('rack') if isinstance(feed, dict) else getattr(feed, 'rack', None)
                rack_name = rack_data.get('name') if rack_data and isinstance(rack_data, dict) else getattr(rack_data, 'name', None) if rack_data else None
                
                # Get specifications
                status_obj = feed.get('status') if isinstance(feed, dict) else getattr(feed, 'status', None)
                status_value = status_obj.get('label') if isinstance(status_obj, dict) else str(status_obj) if status_obj else 'N/A'
                
                type_obj = feed.get('type') if isinstance(feed, dict) else getattr(feed, 'type', None)
                type_value = type_obj.get('label') if isinstance(type_obj, dict) else str(type_obj) if type_obj else 'N/A'
                
                supply_obj = feed.get('supply') if isinstance(feed, dict) else getattr(feed, 'supply', None)
                supply_value = supply_obj.get('label') if isinstance(supply_obj, dict) else str(supply_obj) if supply_obj else 'N/A'
                
                phase_obj = feed.get('phase') if isinstance(feed, dict) else getattr(feed, 'phase', None)
                phase_value = phase_obj.get('label') if isinstance(phase_obj, dict) else str(phase_obj) if phase_obj else 'N/A'
                
                voltage = feed.get('voltage') if isinstance(feed, dict) else getattr(feed, 'voltage', None)
                amperage = feed.get('amperage') if isinstance(feed, dict) else getattr(feed, 'amperage', None)
                max_utilization = feed.get('max_utilization') if isinstance(feed, dict) else getattr(feed, 'max_utilization', None)
                
                # Calculate capacity
                capacity_kw = None
                if voltage and amperage:
                    capacity_watts = voltage * amperage
                    capacity_kw = round(capacity_watts / 1000, 2)
                    capacity_stats["total_capacity_kw"] += capacity_kw
                
                if voltage:
                    capacity_stats["total_voltage"] += voltage
                if amperage:
                    capacity_stats["total_amperage"] += amperage
                
                # Count by status and type
                capacity_stats["feed_count_by_status"][status_value] = capacity_stats["feed_count_by_status"].get(status_value, 0) + 1
                capacity_stats["feed_count_by_type"][type_value] = capacity_stats["feed_count_by_type"].get(type_value, 0) + 1
                
                # Count power outlets
                outlet_count = 0
                try:
                    outlets = client.dcim.power_outlets.filter(power_feed_id=feed_id)
                    outlet_count = len(outlets)
                except Exception:
                    pass
                
                feed_info = {
                    "id": feed_id,
                    "name": feed_name,
                    "power_panel": panel_name,
                    "site": site_name,
                    "rack": rack_name,
                    "status": status_value,
                    "type": type_value,
                    "supply": supply_value,
                    "phase": phase_value,
                    "specifications": {
                        "voltage": voltage,
                        "amperage": amperage,
                        "capacity_kw": capacity_kw,
                        "max_utilization": max_utilization
                    },
                    "power_outlets": outlet_count,
                    "url": f"{client.config.url}/dcim/power-feeds/{feed_id}/"
                }
                
                feeds_data.append(feed_info)
                
            except Exception as e:
                logger.warning(f"Error processing feed data: {e}")
                continue
        
        # Calculate averages
        if feeds_data:
            capacity_stats["average_voltage"] = round(capacity_stats["total_voltage"] / len(feeds_data), 1) if capacity_stats["total_voltage"] > 0 else 0
            capacity_stats["average_amperage"] = round(capacity_stats["total_amperage"] / len(feeds_data), 1) if capacity_stats["total_amperage"] > 0 else 0
            capacity_stats["average_capacity_kw"] = round(capacity_stats["total_capacity_kw"] / len(feeds_data), 2) if capacity_stats["total_capacity_kw"] > 0 else 0
        
        # Build filter description
        filter_description = []
        if site:
            filter_description.append(f"site: {site}")
        if power_panel:
            filter_description.append(f"power panel: {power_panel}")
        if rack:
            filter_description.append(f"rack: {rack}")
        if status:
            filter_description.append(f"status: {status}")
        if feed_type:
            filter_description.append(f"type: {feed_type}")
        
        filter_text = f" (filtered by {', '.join(filter_description)})" if filter_description else ""
        
        return {
            "success": True,
            "data": {
                "feeds": feeds_data,
                "total_count": total_count,
                "returned_count": len(feeds_data),
                "limit_applied": limit if total_count > limit else None,
                "filters": filter_text,
                "capacity_statistics": {
                    "total_capacity_kw": round(capacity_stats["total_capacity_kw"], 2),
                    "average_voltage": capacity_stats.get("average_voltage", 0),
                    "average_amperage": capacity_stats.get("average_amperage", 0),
                    "average_capacity_kw": capacity_stats.get("average_capacity_kw", 0),
                    "feed_count_by_status": capacity_stats["feed_count_by_status"],
                    "feed_count_by_type": capacity_stats["feed_count_by_type"]
                }
            }
        }
        
    except Exception as e:
        raise NetBoxValidationError(f"Failed to retrieve power feeds: {e}")


@mcp_tool(category="dcim")
def netbox_update_power_feed(
    client: NetBoxClient,
    feed_identifier: str,
    power_panel: Optional[str] = None,
    site: Optional[str] = None,
    new_name: Optional[str] = None,
    status: Optional[str] = None,
    feed_type: Optional[str] = None,
    supply: Optional[str] = None,
    phase: Optional[str] = None,
    voltage: Optional[int] = None,
    amperage: Optional[int] = None,
    max_utilization: Optional[int] = None,
    rack: Optional[str] = None,
    comments: Optional[str] = None,
    tags: Optional[List[str]] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Update an existing power feed.
    
    This enterprise-grade function updates power feed configuration
    with comprehensive validation and safety checks.
    
    Args:
        feed_identifier: Power feed name or ID to update
        power_panel: Power panel name for feed lookup (improves search accuracy)
        site: Site name for feed lookup (improves search accuracy)
        new_name: New name for the power feed (optional)
        status: Update status (planned, active, offline, decommissioning, optional)
        feed_type: Update type (primary, redundant, optional)
        supply: Update supply type (ac, dc, optional)
        phase: Update phase (single-phase, three-phase, optional)
        voltage: Update voltage rating in volts (optional)
        amperage: Update amperage rating in amps (optional)
        max_utilization: Update maximum utilization percentage (optional)
        rack: Update rack assignment (optional)
        comments: Update comments (optional)
        tags: Update tags list (optional)
        client: NetBox client (injected)
        confirm: Must be True to execute
        
    Returns:
        Dict containing operation result and updated feed details
        
    Examples:
        # Dry run update
        netbox_update_power_feed("FEED-A-01", voltage=240, amperage=30)
        
        # Update with confirmation
        netbox_update_power_feed("FEED-A-01", status="active", 
                                voltage=240, amperage=30, confirm=True)
    """
    
    # DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Power feed would be updated. Set confirm=True to execute.",
            "would_update": {
                "feed_identifier": feed_identifier,
                "new_name": new_name,
                "status": status,
                "type": feed_type,
                "supply": supply,
                "phase": phase,
                "voltage": voltage,
                "amperage": amperage,
                "max_utilization": max_utilization,
                "rack": rack,
                "comments": comments,
                "tags": tags
            }
        }
    
    # FIND EXISTING POWER FEED
    try:
        # Try lookup by ID first
        if feed_identifier.isdigit():
            feed_id = int(feed_identifier)
            feeds = client.dcim.power_feeds.filter(id=feed_id)
        else:
            # Search by name with optional context
            filter_params = {"name": feed_identifier}
            
            # Add power panel context if provided
            if power_panel:
                if site:
                    # Find panel in specific site
                    sites = client.dcim.sites.filter(name=site)
                    if sites:
                        site_obj = sites[0]
                        site_id = site_obj.get('id') if isinstance(site_obj, dict) else site_obj.id
                        # ULTRATHINK FIX 1: Expand panel search parameters
                        panel_search_params = {
                            "site_id": site_id,
                            "expand": ["site", "rack_group"],
                            "limit": 50
                        }

                        # ULTRATHINK FIX 2: Multi-strategy panel search
                        panels = None
                        if power_panel.isdigit():
                            panels = list(client.dcim.power_panels.filter(id=int(power_panel), **panel_search_params))

                        if not panels:
                            panels = list(client.dcim.power_panels.filter(name=power_panel, **panel_search_params))

                        # ULTRATHINK FIX 4: Fallback panel search
                        if not panels:
                            panels = list(client.dcim.power_panels.filter(name__icontains=power_panel, **panel_search_params))
                        if panels:
                            # ULTRATHINK FIX 3: Defensive panel handling
                            panel_obj = panels[0] if isinstance(panels, list) else panels
                            panel_id = panel_obj.get('id') if isinstance(panel_obj, dict) else getattr(panel_obj, 'id', None)
                            # panel_id may be missing; only apply filter when available
                            if panel_id:
                                filter_params["power_panel_id"] = panel_id
                else:
                    # Find panel by name only
                    panels = client.dcim.power_panels.filter(name=power_panel)
                    if panels:
                        panel_obj = panels[0]
                        panel_id = panel_obj.get('id') if isinstance(panel_obj, dict) else panel_obj.id
                        filter_params["power_panel_id"] = panel_id
            
            feeds = client.dcim.power_feeds.filter(**filter_params)
        
        if not feeds:
            identifier_desc = f"power feed '{feed_identifier}'"
            if power_panel:
                identifier_desc += f" in power panel '{power_panel}'"
            if site:
                identifier_desc += f" in site '{site}'"
            raise NetBoxNotFoundError(f"Could not find {identifier_desc}")
        
        existing_feed = feeds[0]
        feed_id = existing_feed.get('id') if isinstance(existing_feed, dict) else existing_feed.id
        current_name = existing_feed.get('name') if isinstance(existing_feed, dict) else existing_feed.name
        
    except Exception as e:
        raise NetBoxNotFoundError(f"Failed to find power feed: {e}")
    
    # BUILD UPDATE PAYLOAD
    update_payload = {}
    
    # Handle name update
    if new_name:
        if not new_name.strip():
            raise NetBoxValidationError("New power feed name cannot be empty")
        update_payload["name"] = new_name.strip()
    
    # Handle choice field updates with validation
    if status:
        valid_statuses = ["planned", "active", "offline", "decommissioning"]
        if status not in valid_statuses:
            raise NetBoxValidationError(f"Invalid status '{status}'. Valid options: {', '.join(valid_statuses)}")
        update_payload["status"] = status
    
    if feed_type:
        valid_types = ["primary", "redundant"]
        if feed_type not in valid_types:
            raise NetBoxValidationError(f"Invalid type '{feed_type}'. Valid options: {', '.join(valid_types)}")
        update_payload["type"] = feed_type
    
    if supply:
        valid_supplies = ["ac", "dc"]
        if supply not in valid_supplies:
            raise NetBoxValidationError(f"Invalid supply '{supply}'. Valid options: {', '.join(valid_supplies)}")
        update_payload["supply"] = supply
    
    if phase:
        valid_phases = ["single-phase", "three-phase"]
        if phase not in valid_phases:
            raise NetBoxValidationError(f"Invalid phase '{phase}'. Valid options: {', '.join(valid_phases)}")
        update_payload["phase"] = phase
    
    # Handle numeric updates with validation
    if voltage is not None:
        if voltage <= 0:
            raise NetBoxValidationError("Voltage must be positive")
        update_payload["voltage"] = voltage
    
    if amperage is not None:
        if amperage <= 0:
            raise NetBoxValidationError("Amperage must be positive")
        update_payload["amperage"] = amperage
    
    if max_utilization is not None:
        if not (0 <= max_utilization <= 100):
            raise NetBoxValidationError("Max utilization must be between 0 and 100 percent")
        update_payload["max_utilization"] = max_utilization
    
    # Handle rack update
    if rack is not None:  # Allow empty string to clear rack
        if rack:  # Non-empty rack
            try:
                # Get current power panel to determine site
                current_panel = existing_feed.get('power_panel') if isinstance(existing_feed, dict) else getattr(existing_feed, 'power_panel', {})
                panel_site = current_panel.get('site') if isinstance(current_panel, dict) else getattr(current_panel, 'site', {})
                site_id = panel_site.get('id') if isinstance(panel_site, dict) else getattr(panel_site, 'id', None)
                
                if site_id:
                    racks = client.dcim.racks.filter(site_id=site_id, name=rack)
                    if not racks:
                        raise NetBoxNotFoundError(f"Rack '{rack}' not found in current site")
                    
                    rack_obj = racks[0]
                    rack_id = rack_obj.get('id') if isinstance(rack_obj, dict) else rack_obj.id
                    update_payload["rack"] = rack_id
                else:
                    raise NetBoxValidationError("Cannot resolve rack - site information missing")
                    
            except Exception as e:
                raise NetBoxValidationError(f"Failed to resolve rack '{rack}': {e}")
        else:
            # Clear rack
            update_payload["rack"] = None
    
    # Handle other updates
    if comments is not None:
        update_payload["comments"] = comments
    
    if tags is not None:
        update_payload["tags"] = tags
    
    # Check if any updates provided
    if not update_payload:
        raise NetBoxValidationError("No update parameters provided")
    
    # CONFLICT DETECTION (if name is being changed)
    if "name" in update_payload:
        try:
            current_panel = existing_feed.get('power_panel') if isinstance(existing_feed, dict) else getattr(existing_feed, 'power_panel', {})
            panel_id = current_panel.get('id') if isinstance(current_panel, dict) else getattr(current_panel, 'id', None)
            
            if panel_id:
                existing_feeds = client.dcim.power_feeds.filter(
                    power_panel_id=panel_id,
                    name=update_payload["name"],
                    no_cache=True
                )
                
                # Check if found feed is different from current feed
                for existing in existing_feeds:
                    existing_id = existing.get('id') if isinstance(existing, dict) else existing.id
                    if existing_id != feed_id:
                        raise NetBoxConflictError(
                            resource_type="Power Feed",
                            identifier=f"{update_payload['name']} in current power panel",
                            existing_id=existing_id
                        )
        except ConflictError:
            raise
        except Exception as e:
            logger.warning(f"Could not check for naming conflicts: {e}")
    
    # PERFORM UPDATE
    try:
        logger.debug(f"Updating power feed {feed_id} with payload: {update_payload}")
        updated_feed = client.dcim.power_feeds.update(feed_id, confirm=confirm, **update_payload)
        updated_name = updated_feed.get('name') if isinstance(updated_feed, dict) else updated_feed.name
        
    except Exception as e:
        raise NetBoxValidationError(f"NetBox API error during power feed update: {e}")
    
    # RETURN SUCCESS
    return {
        "success": True,
        "message": f"Power feed successfully updated from '{current_name}' to '{updated_name}'.",
        "data": {
            "feed_id": feed_id,
            "old_name": current_name,
            "new_name": updated_name,
            "updates_applied": list(update_payload.keys()),
            "url": f"{client.config.url}/dcim/power-feeds/{feed_id}/"
        }
    }


@mcp_tool(category="dcim")
def netbox_delete_power_feed(
    client: NetBoxClient,
    feed_identifier: str,
    power_panel: Optional[str] = None,
    site: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Delete a power feed from NetBox.
    
    This enterprise-grade function deletes power feeds with comprehensive
    safety checks including dependency validation.
    
    Args:
        feed_identifier: Power feed name or ID to delete
        power_panel: Power panel name for feed lookup (improves search accuracy)
        site: Site name for feed lookup (improves search accuracy)
        client: NetBox client (injected)
        confirm: Must be True to execute
        
    Returns:
        Dict containing operation result and deletion details
        
    Examples:
        # Dry run deletion
        netbox_delete_power_feed("FEED-A-01")
        
        # Delete with confirmation
        netbox_delete_power_feed("FEED-A-01", power_panel="PANEL-A-01", confirm=True)
    """
    
    # DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Power feed would be deleted. Set confirm=True to execute.",
            "would_delete": {
                "feed_identifier": feed_identifier,
                "power_panel": power_panel,
                "site": site
            }
        }
    
    # FIND POWER FEED TO DELETE
    try:
        # Try lookup by ID first
        if feed_identifier.isdigit():
            feed_id = int(feed_identifier)
            feeds = client.dcim.power_feeds.filter(id=feed_id)
        else:
            # Search by name with optional context
            filter_params = {"name": feed_identifier}
            
            # Add power panel context if provided
            if power_panel:
                if site:
                    # Find panel in specific site
                    sites = client.dcim.sites.filter(name=site)
                    if sites:
                        site_obj = sites[0]
                        site_id = site_obj.get('id') if isinstance(site_obj, dict) else site_obj.id
                        # ULTRATHINK FIX 1: Expand panel search parameters
                        panel_search_params = {
                            "site_id": site_id,
                            "expand": ["site", "rack_group"],
                            "limit": 50
                        }

                        # ULTRATHINK FIX 2: Multi-strategy panel search
                        panels = None
                        if power_panel.isdigit():
                            panels = list(client.dcim.power_panels.filter(id=int(power_panel), **panel_search_params))

                        if not panels:
                            panels = list(client.dcim.power_panels.filter(name=power_panel, **panel_search_params))

                        # ULTRATHINK FIX 4: Fallback panel search
                        if not panels:
                            panels = list(client.dcim.power_panels.filter(name__icontains=power_panel, **panel_search_params))
                        if panels:
                            # ULTRATHINK FIX 3: Defensive panel handling
                            panel_obj = panels[0] if isinstance(panels, list) else panels
                            panel_id = panel_obj.get('id') if isinstance(panel_obj, dict) else getattr(panel_obj, 'id', None)
                            # panel_id may be missing; only apply filter when available
                            if panel_id:
                                filter_params["power_panel_id"] = panel_id
                else:
                    # Find panel by name only
                    panels = client.dcim.power_panels.filter(name=power_panel)
                    if panels:
                        panel_obj = panels[0]
                        panel_id = panel_obj.get('id') if isinstance(panel_obj, dict) else panel_obj.id
                        filter_params["power_panel_id"] = panel_id
            
            feeds = client.dcim.power_feeds.filter(**filter_params)
        
        if not feeds:
            identifier_desc = f"power feed '{feed_identifier}'"
            if power_panel:
                identifier_desc += f" in power panel '{power_panel}'"
            if site:
                identifier_desc += f" in site '{site}'"
            raise NetBoxNotFoundError(f"Could not find {identifier_desc}")
        
        feed_to_delete = feeds[0]
        feed_id = feed_to_delete.get('id') if isinstance(feed_to_delete, dict) else feed_to_delete.id
        feed_name = feed_to_delete.get('name') if isinstance(feed_to_delete, dict) else feed_to_delete.name
        
        # Get power panel and site information for reporting
        panel_data = feed_to_delete.get('power_panel') if isinstance(feed_to_delete, dict) else getattr(feed_to_delete, 'power_panel', {})
        panel_name = panel_data.get('name') if isinstance(panel_data, dict) else getattr(panel_data, 'name', 'Unknown')
        
        site_name = "Unknown"
        if panel_data:
            panel_site_data = panel_data.get('site') if isinstance(panel_data, dict) else getattr(panel_data, 'site', None)
            if panel_site_data:
                site_name = panel_site_data.get('name') if isinstance(panel_site_data, dict) else getattr(panel_site_data, 'name', 'Unknown')
        
    except Exception as e:
        raise NetBoxNotFoundError(f"Failed to find power feed: {e}")
    
    # DEPENDENCY VALIDATION
    dependencies = []
    
    try:
        # Check for power outlets
        power_outlets = client.dcim.power_outlets.filter(power_feed_id=feed_id)
        if power_outlets:
            outlet_names = []
            for outlet in power_outlets[:5]:  # Show first 5 outlets
                outlet_name = outlet.get('name') if isinstance(outlet, dict) else outlet.name
                device_data = outlet.get('device') if isinstance(outlet, dict) else getattr(outlet, 'device', {})
                device_name = device_data.get('name') if isinstance(device_data, dict) else getattr(device_data, 'name', 'Unknown')
                outlet_names.append(f"{outlet_name} ({device_name})")
            
            dependency_desc = f"{len(power_outlets)} power outlet(s): {', '.join(outlet_names)}"
            if len(power_outlets) > 5:
                dependency_desc += f" and {len(power_outlets) - 5} more"
            
            dependencies.append({
                "type": "Power Outlets",
                "count": len(power_outlets),
                "description": dependency_desc
            })
        
    except Exception as e:
        logger.warning(f"Could not check power outlet dependencies: {e}")
    
    try:
        # Check for cable connections
        cables_a = client.dcim.cables.filter(termination_a_type="dcim.powerfeed", termination_a_id=feed_id)
        cables_b = client.dcim.cables.filter(termination_b_type="dcim.powerfeed", termination_b_id=feed_id)
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
            f"Cannot delete power feed '{feed_name}' - it has active dependencies:\n" +
            "\n".join(dependency_list) +
            "\n\nPlease remove or reassign these dependencies before deleting the power feed."
        )
    
    # PERFORM DELETION
    try:
        logger.debug(f"Deleting power feed {feed_id} ({feed_name})")
        client.dcim.power_feeds.delete(feed_id, confirm=confirm)
        
    except Exception as e:
        raise NetBoxValidationError(f"NetBox API error during power feed deletion: {e}")
    
    # RETURN SUCCESS
    return {
        "success": True,
        "message": f"Power feed '{feed_name}' successfully deleted from power panel '{panel_name}'.",
        "data": {
            "deleted_feed_id": feed_id,
            "deleted_feed_name": feed_name,
            "power_panel_name": panel_name,
            "site_name": site_name,
            "dependencies_checked": len(dependencies) == 0
        }
    }