#!/usr/bin/env python3
"""
DCIM Power Panels Management Tools

This module provides enterprise-grade tools for managing NetBox power panels
including creation, updates, deletion, and information retrieval.
"""

from typing import Dict, Any, Optional, List
import logging

from netbox_mcp.registry import mcp_tool
from netbox_mcp.client import NetBoxClient
from netbox_mcp.exceptions import NetBoxValidationError, NetBoxNotFoundError, NetBoxConflictError

logger = logging.getLogger(__name__)


@mcp_tool(category="dcim")
def netbox_create_power_panel(
    client: NetBoxClient,
    name: str,
    site: str,
    location: Optional[str] = None,
    rack_group: Optional[str] = None,
    comments: Optional[str] = None,
    tags: Optional[List[str]] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Create a new power panel in NetBox.
    
    This enterprise-grade function creates power panels for electrical distribution
    within data centers and facilities.
    
    Args:
        name: Power panel name/identifier
        site: Site where power panel is located (foreign key resolved)
        location: Specific location within site (foreign key resolved, optional)
        rack_group: Rack group association (foreign key resolved, optional)
        comments: Additional comments
        tags: List of tags to assign
        client: NetBox client (injected)
        confirm: Must be True to execute
        
    Returns:
        Dict containing operation result and power panel details
        
    Examples:
        # Dry run
        netbox_create_power_panel("PANEL-A-01", "datacenter-1")
        
        # Create panel with location
        netbox_create_power_panel("PANEL-A-01", "datacenter-1", 
                                 location="Electrical Room A", confirm=True)
    """
    
    # DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Power panel would be created. Set confirm=True to execute.",
            "would_create": {
                "name": name,
                "site": site,
                "location": location,
                "rack_group": rack_group,
                "comments": comments,
                "tags": tags
            }
        }
    
    # PARAMETER VALIDATION
    if not name or not name.strip():
        raise NetBoxValidationError("Power panel name cannot be empty")
    
    if not site or not site.strip():
        raise NetBoxValidationError("Site is required for power panel creation")
    
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
    
    # LOOKUP LOCATION (if provided)
    location_id = None
    location_display = None
    if location:
        try:
            locations = client.dcim.locations.filter(site_id=site_id, name=location)
            if not locations:
                raise NetBoxNotFoundError(f"Location '{location}' not found in site '{site}'")
            
            location_obj = locations[0]
            location_id = location_obj.get('id') if isinstance(location_obj, dict) else location_obj.id
            location_display = location_obj.get('display', location) if isinstance(location_obj, dict) else getattr(location_obj, 'display', location)
            
        except Exception as e:
            raise NetBoxValidationError(f"Failed to resolve location '{location}': {e}")
    
    # LOOKUP RACK GROUP (if provided)
    rack_group_id = None
    rack_group_display = None
    if rack_group:
        try:
            rack_groups = client.dcim.rack_groups.filter(site_id=site_id, name=rack_group)
            if not rack_groups:
                raise NetBoxNotFoundError(f"Rack group '{rack_group}' not found in site '{site}'")
            
            rack_group_obj = rack_groups[0]
            rack_group_id = rack_group_obj.get('id') if isinstance(rack_group_obj, dict) else rack_group_obj.id
            rack_group_display = rack_group_obj.get('display', rack_group) if isinstance(rack_group_obj, dict) else getattr(rack_group_obj, 'display', rack_group)
            
        except Exception as e:
            raise NetBoxValidationError(f"Failed to resolve rack group '{rack_group}': {e}")
    
    # CONFLICT DETECTION
    try:
        existing_panels = client.dcim.power_panels.filter(
            site_id=site_id,
            name=name,
            no_cache=True
        )
        
        if existing_panels:
            existing_panel = existing_panels[0]
            existing_id = existing_panel.get('id') if isinstance(existing_panel, dict) else existing_panel.id
            raise NetBoxConflictError(
                resource_type="Power Panel",
                identifier=f"{name} in site {site}",
                existing_id=existing_id
            )
    except ConflictError:
        raise
    except Exception as e:
        logger.warning(f"Could not check for existing power panels: {e}")
    
    # CREATE POWER PANEL
    create_payload = {
        "name": name,
        "site": site_id,
        "comments": comments or ""
    }
    
    # Add optional foreign keys
    if location_id:
        create_payload["location"] = location_id
    if rack_group_id:
        create_payload["rack_group"] = rack_group_id
    if tags:
        create_payload["tags"] = tags
    
    try:
        logger.debug(f"Creating power panel with payload: {create_payload}")
        new_panel = client.dcim.power_panels.create(confirm=confirm, **create_payload)
        panel_id = new_panel.get('id') if isinstance(new_panel, dict) else new_panel.id
        
    except Exception as e:
        raise NetBoxValidationError(f"NetBox API error during power panel creation: {e}")
    
    # RETURN SUCCESS
    return {
        "success": True,
        "message": f"Power panel '{name}' successfully created in site '{site}'.",
        "data": {
            "panel_id": panel_id,
            "panel_name": new_panel.get('name') if isinstance(new_panel, dict) else new_panel.name,
            "site_id": site_id,
            "site_name": site,
            "location_id": location_id,
            "location_name": location,
            "rack_group_id": rack_group_id,
            "rack_group_name": rack_group,
            "url": f"{client.config.url}/dcim/power-panels/{panel_id}/"
        }
    }


@mcp_tool(category="dcim")
def netbox_get_power_panel_info(
    client: NetBoxClient,
    panel_identifier: str,
    site: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get detailed information about a specific power panel.
    
    This inspection tool provides comprehensive power panel details including
    power feeds, usage statistics, and connected equipment.
    
    Args:
        panel_identifier: Power panel name or ID
        site: Site name for panel lookup (improves search accuracy)
        client: NetBox client (injected)
        
    Returns:
        Dict containing detailed power panel information
        
    Examples:
        # Search by name
        netbox_get_power_panel_info("PANEL-A-01")
        
        # Search with site context
        netbox_get_power_panel_info("PANEL-A-01", site="datacenter-1")
    """
    
    # LOOKUP POWER PANEL
    try:
        # Try lookup by ID first
        if panel_identifier.isdigit():
            panel_id = int(panel_identifier)
            # ULTRATHINK FIX 1: Add expand parameters for power panel ID lookups\n            power_panel_search_params = {\n                \"expand\": [\"site\", \"location\", \"rack_group\"],\n                \"limit\": 50\n            }\n            panels = list(client.dcim.power_panels.filter(id=panel_id, **power_panel_search_params))
        else:
            # Search by name with optional site context
            filter_params = {"name": panel_identifier}
            if site:
                # ULTRATHINK FIX 1: Expand search parameters with comprehensive relationship data\n        site_search_params = {\n            \"expand\": [\"region\", \"tenant\"],\n            \"limit\": 50\n        }\n\n        # ULTRATHINK FIX 2: ID resolution with fallback patterns\n        sites = None\n        if site.isdigit():\n            sites = list(client.dcim.sites.filter(id=int(site), **site_search_params))\n\n        if not sites:\n            sites = list(client.dcim.sites.filter(name=site, **site_search_params))\n\n        # ULTRATHINK FIX 4: Slug-based fallback mechanisms\n        if not sites:\n            sites = list(client.dcim.sites.filter(slug=site, **site_search_params))
                if sites:
                    site_obj = sites[0]
                    site_id = site_obj.get('id') if isinstance(site_obj, dict) else site_obj.id
                    filter_params["site_id"] = site_id
            
            # ULTRATHINK FIX 1: Add expand parameters to dynamic power panel filter\n            if 'expand' not in filter_params:\n                filter_params['expand'] = [\"site\", \"location\", \"rack_group\"]\n            if 'limit' not in filter_params:\n                filter_params['limit'] = 50\n            panels = list(client.dcim.power_panels.filter(**filter_params))
        
        if not panels:
            identifier_desc = f"power panel '{panel_identifier}'"
            if site:
                identifier_desc += f" in site '{site}'"
            raise NetBoxNotFoundError(f"Could not find {identifier_desc}")
        
        panel = panels[0]
        panel_id = panel.get('id') if isinstance(panel, dict) else panel.id
        panel_name = panel.get('name') if isinstance(panel, dict) else panel.name
        
    except Exception as e:
        raise NetBoxNotFoundError(f"Failed to find power panel: {e}")
    
    # GET POWER FEEDS
    power_feeds = []
    feed_count = 0
    try:
        # ULTRATHINK FIX 1: Add expand parameters for power feed lookups\n        power_feed_search_params = {\n            \"expand\": [\"power_panel\", \"rack\", \"site\"],\n            \"limit\": 100\n        }\n        feeds = list(client.dcim.power_feeds.filter(power_panel_id=panel_id, **power_feed_search_params))
        feed_count = len(feeds)
        
        for feed in feeds[:10]:  # Limit to 10 feeds for performance
            feed_info = {
                "id": feed.get('id') if isinstance(feed, dict) else feed.id,
                "name": feed.get('name') if isinstance(feed, dict) else feed.name,
                "status": feed.get('status', {}).get('label') if isinstance(feed, dict) else str(getattr(feed, 'status', 'N/A')),
                "type": feed.get('type', {}).get('label') if isinstance(feed, dict) else str(getattr(feed, 'type', 'N/A')),
                "supply": feed.get('supply', {}).get('label') if isinstance(feed, dict) else str(getattr(feed, 'supply', 'N/A'))
            }
            power_feeds.append(feed_info)
            
    except Exception as e:
        logger.warning(f"Could not retrieve power feeds for panel {panel_id}: {e}")
    
    # GET RELATED INFORMATION
    site_info = {}
    location_info = {}
    rack_group_info = {}
    
    try:
        # Site information
        site_data = panel.get('site') if isinstance(panel, dict) else getattr(panel, 'site', None)
        if site_data:
            site_info = {
                "id": site_data.get('id') if isinstance(site_data, dict) else getattr(site_data, 'id', None),
                "name": site_data.get('name') if isinstance(site_data, dict) else getattr(site_data, 'name', None),
                "display": site_data.get('display') if isinstance(site_data, dict) else getattr(site_data, 'display', None)
            }
        
        # Location information
        location_data = panel.get('location') if isinstance(panel, dict) else getattr(panel, 'location', None)
        if location_data:
            location_info = {
                "id": location_data.get('id') if isinstance(location_data, dict) else getattr(location_data, 'id', None),
                "name": location_data.get('name') if isinstance(location_data, dict) else getattr(location_data, 'name', None),
                "display": location_data.get('display') if isinstance(location_data, dict) else getattr(location_data, 'display', None)
            }
        
        # Rack group information
        rack_group_data = panel.get('rack_group') if isinstance(panel, dict) else getattr(panel, 'rack_group', None)
        if rack_group_data:
            rack_group_info = {
                "id": rack_group_data.get('id') if isinstance(rack_group_data, dict) else getattr(rack_group_data, 'id', None),
                "name": rack_group_data.get('name') if isinstance(rack_group_data, dict) else getattr(rack_group_data, 'name', None),
                "display": rack_group_data.get('display') if isinstance(rack_group_data, dict) else getattr(rack_group_data, 'display', None)
            }
            
    except Exception as e:
        logger.warning(f"Could not retrieve related information for panel {panel_id}: {e}")
    
    # RETURN COMPREHENSIVE INFORMATION
    return {
        "success": True,
        "data": {
            "panel_id": panel_id,
            "name": panel_name,
            "site": site_info,
            "location": location_info,
            "rack_group": rack_group_info,
            "comments": panel.get('comments') if isinstance(panel, dict) else getattr(panel, 'comments', ''),
            "tags": panel.get('tags', []) if isinstance(panel, dict) else getattr(panel, 'tags', []),
            "power_feeds": {
                "count": feed_count,
                "feeds": power_feeds,
                "showing": f"{len(power_feeds)} of {feed_count}" if feed_count > 10 else f"All {feed_count}"
            },
            "created": panel.get('created') if isinstance(panel, dict) else getattr(panel, 'created', None),
            "last_updated": panel.get('last_updated') if isinstance(panel, dict) else getattr(panel, 'last_updated', None),
            "url": f"{client.config.url}/dcim/power-panels/{panel_id}/"
        }
    }


@mcp_tool(category="dcim")
def netbox_list_all_power_panels(
    client: NetBoxClient,
    site: Optional[str] = None,
    location: Optional[str] = None,
    rack_group: Optional[str] = None,
    limit: int = 50
) -> Dict[str, Any]:
    """
    List all power panels with optional filtering.
    
    This bulk discovery tool helps explore and analyze power distribution
    infrastructure across sites and locations.
    
    Args:
        site: Filter by site name (optional)
        location: Filter by location name (optional)
        rack_group: Filter by rack group name (optional)
        limit: Maximum number of panels to return (default: 50)
        client: NetBox client (injected)
        
    Returns:
        Dict containing list of power panels with summary statistics
        
    Examples:
        # List all panels
        netbox_list_all_power_panels()
        
        # Filter by site
        netbox_list_all_power_panels(site="datacenter-1")
        
        # Filter by location
        netbox_list_all_power_panels(site="datacenter-1", location="Electrical Room A")
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
                        "panels": [],
                        "total_count": 0,
                        "message": f"No panels found - site '{site}' not found"
                    }
                }
        except Exception as e:
            logger.warning(f"Could not resolve site filter '{site}': {e}")
    
    # RESOLVE LOCATION FILTER
    if location and "site_id" in filter_params:
        try:
            locations = client.dcim.locations.filter(site_id=filter_params["site_id"], name=location)
            if locations:
                location_obj = locations[0]
                location_id = location_obj.get('id') if isinstance(location_obj, dict) else location_obj.id
                filter_params["location_id"] = location_id
            else:
                return {
                    "success": True,
                    "data": {
                        "panels": [],
                        "total_count": 0,
                        "message": f"No panels found - location '{location}' not found in site '{site}'"
                    }
                }
        except Exception as e:
            logger.warning(f"Could not resolve location filter '{location}': {e}")
    
    # RESOLVE RACK GROUP FILTER
    if rack_group and "site_id" in filter_params:
        try:
            rack_groups = client.dcim.rack_groups.filter(site_id=filter_params["site_id"], name=rack_group)
            if rack_groups:
                rack_group_obj = rack_groups[0]
                rack_group_id = rack_group_obj.get('id') if isinstance(rack_group_obj, dict) else rack_group_obj.id
                filter_params["rack_group_id"] = rack_group_id
            else:
                return {
                    "success": True,
                    "data": {
                        "panels": [],
                        "total_count": 0,
                        "message": f"No panels found - rack group '{rack_group}' not found in site '{site}'"
                    }
                }
        except Exception as e:
            logger.warning(f"Could not resolve rack group filter '{rack_group}': {e}")
    
    # GET POWER PANELS
    try:
        # ULTRATHINK FIX 1: Add expand parameters to power panel filter\n        if 'expand' not in filter_params:\n            filter_params['expand'] = [\"site\", \"location\", \"rack_group\"]\n        if 'limit' not in filter_params:\n            filter_params['limit'] = 100\n        panels = list(client.dcim.power_panels.filter(**filter_params))
        total_count = len(panels)
        
        # Apply limit
        limited_panels = panels[:limit]
        
        panels_data = []
        feed_stats = {"total_feeds": 0, "active_feeds": 0}
        
        for panel in limited_panels:
            try:
                # Get basic panel info
                panel_id = panel.get('id') if isinstance(panel, dict) else panel.id
                panel_name = panel.get('name') if isinstance(panel, dict) else panel.name
                
                # Get site info
                site_data = panel.get('site') if isinstance(panel, dict) else getattr(panel, 'site', {})
                site_name = site_data.get('name') if isinstance(site_data, dict) else getattr(site_data, 'name', 'N/A')
                
                # Get location info
                location_data = panel.get('location') if isinstance(panel, dict) else getattr(panel, 'location', None)
                location_name = location_data.get('name') if location_data and isinstance(location_data, dict) else getattr(location_data, 'name', None) if location_data else None
                
                # Get rack group info
                rack_group_data = panel.get('rack_group') if isinstance(panel, dict) else getattr(panel, 'rack_group', None)
                rack_group_name = rack_group_data.get('name') if rack_group_data and isinstance(rack_group_data, dict) else getattr(rack_group_data, 'name', None) if rack_group_data else None
                
                # Count power feeds
                # ULTRATHINK FIX 1: Add expand parameters for power feed lookups\n        power_feed_search_params = {\n            \"expand\": [\"power_panel\", \"rack\", \"site\"],\n            \"limit\": 100\n        }\n        feeds = list(client.dcim.power_feeds.filter(power_panel_id=panel_id, **power_feed_search_params))
                feed_count = len(feeds)
                feed_stats["total_feeds"] += feed_count
                
                # Count active feeds
                active_count = 0
                for feed in feeds:
                    status_obj = feed.get('status') if isinstance(feed, dict) else getattr(feed, 'status', None)
                    if status_obj:
                        status_value = status_obj.get('value') if isinstance(status_obj, dict) else str(status_obj)
                        if status_value == 'active':
                            active_count += 1
                feed_stats["active_feeds"] += active_count
                
                panel_info = {
                    "id": panel_id,
                    "name": panel_name,
                    "site": site_name,
                    "location": location_name,
                    "rack_group": rack_group_name,
                    "power_feeds": {
                        "total": feed_count,
                        "active": active_count
                    },
                    "url": f"{client.config.url}/dcim/power-panels/{panel_id}/"
                }
                
                panels_data.append(panel_info)
                
            except Exception as e:
                logger.warning(f"Error processing panel data: {e}")
                continue
        
        # Build filter description
        filter_description = []
        if site:
            filter_description.append(f"site: {site}")
        if location:
            filter_description.append(f"location: {location}")
        if rack_group:
            filter_description.append(f"rack group: {rack_group}")
        
        filter_text = f" (filtered by {', '.join(filter_description)})" if filter_description else ""
        
        return {
            "success": True,
            "data": {
                "panels": panels_data,
                "total_count": total_count,
                "returned_count": len(panels_data),
                "limit_applied": limit if total_count > limit else None,
                "filters": filter_text,
                "statistics": {
                    "total_power_feeds": feed_stats["total_feeds"],
                    "active_power_feeds": feed_stats["active_feeds"],
                    "average_feeds_per_panel": round(feed_stats["total_feeds"] / len(panels_data), 1) if panels_data else 0
                }
            }
        }
        
    except Exception as e:
        raise NetBoxValidationError(f"Failed to retrieve power panels: {e}")


@mcp_tool(category="dcim")
def netbox_update_power_panel(
    client: NetBoxClient,
    panel_identifier: str,
    site: Optional[str] = None,
    new_name: Optional[str] = None,
    new_site: Optional[str] = None,
    location: Optional[str] = None,
    rack_group: Optional[str] = None,
    comments: Optional[str] = None,
    tags: Optional[List[str]] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Update an existing power panel.
    
    This enterprise-grade function updates power panel configuration
    with comprehensive validation and safety checks.
    
    Args:
        panel_identifier: Power panel name or ID to update
        site: Current site for panel lookup (improves search accuracy)
        new_name: New name for the power panel (optional)
        new_site: Move panel to different site (optional)
        location: Update location assignment (optional)
        rack_group: Update rack group assignment (optional)
        comments: Update comments (optional)
        tags: Update tags list (optional)
        client: NetBox client (injected)
        confirm: Must be True to execute
        
    Returns:
        Dict containing operation result and updated panel details
        
    Examples:
        # Dry run update
        netbox_update_power_panel("PANEL-A-01", new_name="PANEL-A-001")
        
        # Update with confirmation
        netbox_update_power_panel("PANEL-A-01", new_name="PANEL-A-001", 
                                 location="Electrical Room B", confirm=True)
    """
    
    # DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Power panel would be updated. Set confirm=True to execute.",
            "would_update": {
                "panel_identifier": panel_identifier,
                "new_name": new_name,
                "new_site": new_site,
                "location": location,
                "rack_group": rack_group,
                "comments": comments,
                "tags": tags
            }
        }
    
    # FIND EXISTING POWER PANEL
    try:
        # Try lookup by ID first
        if panel_identifier.isdigit():
            panel_id = int(panel_identifier)
            # ULTRATHINK FIX 1: Add expand parameters for power panel ID lookups\n            power_panel_search_params = {\n                \"expand\": [\"site\", \"location\", \"rack_group\"],\n                \"limit\": 50\n            }\n            panels = list(client.dcim.power_panels.filter(id=panel_id, **power_panel_search_params))
        else:
            # Search by name with optional site context
            filter_params = {"name": panel_identifier}
            if site:
                # ULTRATHINK FIX 1: Expand search parameters with comprehensive relationship data\n        site_search_params = {\n            \"expand\": [\"region\", \"tenant\"],\n            \"limit\": 50\n        }\n\n        # ULTRATHINK FIX 2: ID resolution with fallback patterns\n        sites = None\n        if site.isdigit():\n            sites = list(client.dcim.sites.filter(id=int(site), **site_search_params))\n\n        if not sites:\n            sites = list(client.dcim.sites.filter(name=site, **site_search_params))\n\n        # ULTRATHINK FIX 4: Slug-based fallback mechanisms\n        if not sites:\n            sites = list(client.dcim.sites.filter(slug=site, **site_search_params))
                if sites:
                    site_obj = sites[0]
                    site_id = site_obj.get('id') if isinstance(site_obj, dict) else site_obj.id
                    filter_params["site_id"] = site_id
            
            # ULTRATHINK FIX 1: Add expand parameters to dynamic power panel filter\n            if 'expand' not in filter_params:\n                filter_params['expand'] = [\"site\", \"location\", \"rack_group\"]\n            if 'limit' not in filter_params:\n                filter_params['limit'] = 50\n            panels = list(client.dcim.power_panels.filter(**filter_params))
        
        if not panels:
            identifier_desc = f"power panel '{panel_identifier}'"
            if site:
                identifier_desc += f" in site '{site}'"
            raise NetBoxNotFoundError(f"Could not find {identifier_desc}")
        
        existing_panel = panels[0]
        panel_id = existing_panel.get('id') if isinstance(existing_panel, dict) else existing_panel.id
        current_name = existing_panel.get('name') if isinstance(existing_panel, dict) else existing_panel.name
        
    except Exception as e:
        raise NetBoxNotFoundError(f"Failed to find power panel: {e}")
    
    # BUILD UPDATE PAYLOAD
    update_payload = {}
    
    # Handle name update
    if new_name:
        if not new_name.strip():
            raise NetBoxValidationError("New power panel name cannot be empty")
        update_payload["name"] = new_name.strip()
    
    # Handle site change
    if new_site:
        try:
            sites = client.dcim.sites.filter(name=new_site)
            if not sites:
                raise NetBoxNotFoundError(f"New site '{new_site}' not found")
            
            new_site_obj = sites[0]
            new_site_id = new_site_obj.get('id') if isinstance(new_site_obj, dict) else new_site_obj.id
            update_payload["site"] = new_site_id
            
        except Exception as e:
            raise NetBoxValidationError(f"Failed to resolve new site '{new_site}': {e}")
    
    # Handle location update
    if location is not None:  # Allow empty string to clear location
        if location:  # Non-empty location
            try:
                # Use new site if specified, otherwise current site
                target_site_id = update_payload.get("site")
                if not target_site_id:
                    current_site = existing_panel.get('site') if isinstance(existing_panel, dict) else getattr(existing_panel, 'site', {})
                    target_site_id = current_site.get('id') if isinstance(current_site, dict) else getattr(current_site, 'id', None)
                
                if target_site_id:
                    locations = client.dcim.locations.filter(site_id=target_site_id, name=location)
                    if not locations:
                        site_name = new_site if new_site else (site if site else "unknown")
                        raise NetBoxNotFoundError(f"Location '{location}' not found in site '{site_name}'")
                    
                    location_obj = locations[0]
                    location_id = location_obj.get('id') if isinstance(location_obj, dict) else location_obj.id
                    update_payload["location"] = location_id
                else:
                    raise NetBoxValidationError("Cannot resolve location - site information missing")
                    
            except Exception as e:
                raise NetBoxValidationError(f"Failed to resolve location '{location}': {e}")
        else:
            # Clear location
            update_payload["location"] = None
    
    # Handle rack group update
    if rack_group is not None:  # Allow empty string to clear rack group
        if rack_group:  # Non-empty rack group
            try:
                # Use new site if specified, otherwise current site
                target_site_id = update_payload.get("site")
                if not target_site_id:
                    current_site = existing_panel.get('site') if isinstance(existing_panel, dict) else getattr(existing_panel, 'site', {})
                    target_site_id = current_site.get('id') if isinstance(current_site, dict) else getattr(current_site, 'id', None)
                
                if target_site_id:
                    rack_groups = client.dcim.rack_groups.filter(site_id=target_site_id, name=rack_group)
                    if not rack_groups:
                        site_name = new_site if new_site else (site if site else "unknown")
                        raise NetBoxNotFoundError(f"Rack group '{rack_group}' not found in site '{site_name}'")
                    
                    rack_group_obj = rack_groups[0]
                    rack_group_id = rack_group_obj.get('id') if isinstance(rack_group_obj, dict) else rack_group_obj.id
                    update_payload["rack_group"] = rack_group_id
                else:
                    raise NetBoxValidationError("Cannot resolve rack group - site information missing")
                    
            except Exception as e:
                raise NetBoxValidationError(f"Failed to resolve rack group '{rack_group}': {e}")
        else:
            # Clear rack group
            update_payload["rack_group"] = None
    
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
            target_site_id = update_payload.get("site")
            if not target_site_id:
                current_site = existing_panel.get('site') if isinstance(existing_panel, dict) else getattr(existing_panel, 'site', {})
                target_site_id = current_site.get('id') if isinstance(current_site, dict) else getattr(current_site, 'id', None)
            
            if target_site_id:
                existing_panels = client.dcim.power_panels.filter(
                    site_id=target_site_id,
                    name=update_payload["name"],
                    no_cache=True
                )
                
                # Check if found panel is different from current panel
                for existing in existing_panels:
                    existing_id = existing.get('id') if isinstance(existing, dict) else existing.id
                    if existing_id != panel_id:
                        raise NetBoxConflictError(
                            resource_type="Power Panel",
                            identifier=f"{update_payload['name']} in target site",
                            existing_id=existing_id
                        )
        except ConflictError:
            raise
        except Exception as e:
            logger.warning(f"Could not check for naming conflicts: {e}")
    
    # PERFORM UPDATE
    try:
        logger.debug(f"Updating power panel {panel_id} with payload: {update_payload}")
        updated_panel = client.dcim.power_panels.update(panel_id, confirm=confirm, **update_payload)
        updated_name = updated_panel.get('name') if isinstance(updated_panel, dict) else updated_panel.name
        
    except Exception as e:
        raise NetBoxValidationError(f"NetBox API error during power panel update: {e}")
    
    # RETURN SUCCESS
    return {
        "success": True,
        "message": f"Power panel successfully updated from '{current_name}' to '{updated_name}'.",
        "data": {
            "panel_id": panel_id,
            "old_name": current_name,
            "new_name": updated_name,
            "updates_applied": list(update_payload.keys()),
            "url": f"{client.config.url}/dcim/power-panels/{panel_id}/"
        }
    }


@mcp_tool(category="dcim")
def netbox_delete_power_panel(
    client: NetBoxClient,
    panel_identifier: str,
    site: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Delete a power panel from NetBox.
    
    This enterprise-grade function deletes power panels with comprehensive
    safety checks including dependency validation.
    
    Args:
        panel_identifier: Power panel name or ID to delete
        site: Site for panel lookup (improves search accuracy)
        client: NetBox client (injected)
        confirm: Must be True to execute
        
    Returns:
        Dict containing operation result and deletion details
        
    Examples:
        # Dry run deletion
        netbox_delete_power_panel("PANEL-A-01")
        
        # Delete with confirmation
        netbox_delete_power_panel("PANEL-A-01", site="datacenter-1", confirm=True)
    """
    
    # DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Power panel would be deleted. Set confirm=True to execute.",
            "would_delete": {
                "panel_identifier": panel_identifier,
                "site": site
            }
        }
    
    # FIND POWER PANEL TO DELETE
    try:
        # Try lookup by ID first
        if panel_identifier.isdigit():
            panel_id = int(panel_identifier)
            # ULTRATHINK FIX 1: Add expand parameters for power panel ID lookups\n            power_panel_search_params = {\n                \"expand\": [\"site\", \"location\", \"rack_group\"],\n                \"limit\": 50\n            }\n            panels = list(client.dcim.power_panels.filter(id=panel_id, **power_panel_search_params))
        else:
            # Search by name with optional site context
            filter_params = {"name": panel_identifier}
            if site:
                # ULTRATHINK FIX 1: Expand search parameters with comprehensive relationship data\n        site_search_params = {\n            \"expand\": [\"region\", \"tenant\"],\n            \"limit\": 50\n        }\n\n        # ULTRATHINK FIX 2: ID resolution with fallback patterns\n        sites = None\n        if site.isdigit():\n            sites = list(client.dcim.sites.filter(id=int(site), **site_search_params))\n\n        if not sites:\n            sites = list(client.dcim.sites.filter(name=site, **site_search_params))\n\n        # ULTRATHINK FIX 4: Slug-based fallback mechanisms\n        if not sites:\n            sites = list(client.dcim.sites.filter(slug=site, **site_search_params))
                if sites:
                    site_obj = sites[0]
                    site_id = site_obj.get('id') if isinstance(site_obj, dict) else site_obj.id
                    filter_params["site_id"] = site_id
            
            # ULTRATHINK FIX 1: Add expand parameters to dynamic power panel filter\n            if 'expand' not in filter_params:\n                filter_params['expand'] = [\"site\", \"location\", \"rack_group\"]\n            if 'limit' not in filter_params:\n                filter_params['limit'] = 50\n            panels = list(client.dcim.power_panels.filter(**filter_params))
        
        if not panels:
            identifier_desc = f"power panel '{panel_identifier}'"
            if site:
                identifier_desc += f" in site '{site}'"
            raise NetBoxNotFoundError(f"Could not find {identifier_desc}")
        
        panel_to_delete = panels[0]
        panel_id = panel_to_delete.get('id') if isinstance(panel_to_delete, dict) else panel_to_delete.id
        panel_name = panel_to_delete.get('name') if isinstance(panel_to_delete, dict) else panel_to_delete.name
        
        # Get site information for reporting
        site_data = panel_to_delete.get('site') if isinstance(panel_to_delete, dict) else getattr(panel_to_delete, 'site', {})
        site_name = site_data.get('name') if isinstance(site_data, dict) else getattr(site_data, 'name', 'Unknown')
        
    except Exception as e:
        raise NetBoxNotFoundError(f"Failed to find power panel: {e}")
    
    # DEPENDENCY VALIDATION
    dependencies = []
    
    try:
        # Check for power feeds
        power_feeds = client.dcim.power_feeds.filter(power_panel_id=panel_id)
        if power_feeds:
            feed_names = []
            for feed in power_feeds[:5]:  # Show first 5 feeds
                feed_name = feed.get('name') if isinstance(feed, dict) else feed.name
                feed_names.append(feed_name)
            
            dependency_desc = f"{len(power_feeds)} power feed(s): {', '.join(feed_names)}"
            if len(power_feeds) > 5:
                dependency_desc += f" and {len(power_feeds) - 5} more"
            
            dependencies.append({
                "type": "Power Feeds",
                "count": len(power_feeds),
                "description": dependency_desc
            })
        
    except Exception as e:
        logger.warning(f"Could not check power feed dependencies: {e}")
    
    # If dependencies found, prevent deletion
    if dependencies:
        dependency_list = []
        for dep in dependencies:
            dependency_list.append(f"- {dep['description']}")
        
        raise NetBoxValidationError(
            f"Cannot delete power panel '{panel_name}' - it has active dependencies:\n" +
            "\n".join(dependency_list) +
            "\n\nPlease remove or reassign these dependencies before deleting the power panel."
        )
    
    # PERFORM DELETION
    try:
        logger.debug(f"Deleting power panel {panel_id} ({panel_name})")
        client.dcim.power_panels.delete(panel_id, confirm=confirm)
        
    except Exception as e:
        raise NetBoxValidationError(f"NetBox API error during power panel deletion: {e}")
    
    # RETURN SUCCESS
    return {
        "success": True,
        "message": f"Power panel '{panel_name}' successfully deleted from site '{site_name}'.",
        "data": {
            "deleted_panel_id": panel_id,
            "deleted_panel_name": panel_name,
            "site_name": site_name,
            "dependencies_checked": len(dependencies) == 0
        }
    }