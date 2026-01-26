#!/usr/bin/env python3
"""
DCIM Site Management Tools

High-level tools for managing NetBox sites, locations, regions,
and site infrastructure with enterprise-grade functionality.
"""

from typing import Dict, Optional, Any
import logging
from ...registry import mcp_tool
from ...client import NetBoxClient

logger = logging.getLogger(__name__)


@mcp_tool(category="dcim")
def netbox_create_site(
    client: NetBoxClient,
    name: str,
    slug: str,
    status: str = "active",
    region: Optional[str] = None,
    description: Optional[str] = None,
    physical_address: Optional[str] = None,
    shipping_address: Optional[str] = None,
    contact_name: Optional[str] = None,
    contact_phone: Optional[str] = None,
    contact_email: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Create a new site in NetBox DCIM.
    
    Args:
        client: NetBoxClient instance (injected)
        name: Site name
        slug: URL-friendly identifier
        status: Site status (active, planned, staged, decommissioning, retired)
        region: Optional region name
        description: Optional description
        physical_address: Physical location address
        shipping_address: Shipping address if different
        contact_name: Primary contact name
        contact_phone: Contact phone number
        contact_email: Contact email address
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Created site information or error details
        
    Example:
        netbox_create_site("Amsterdam DC", "amsterdam-dc", status="active", confirm=True)
    """
    try:
        if not name or not slug:
            return {
                "success": False,
                "error": "Site name and slug are required",
                "error_type": "ValidationError"
            }
        
        logger.info(f"Creating site: {name} (slug: {slug})")
        
        # Build site data
        site_data = {
            "name": name,
            "slug": slug,
            "status": status
        }
        
        if region:
            site_data["region"] = region
        if description:
            site_data["description"] = description
        if physical_address:
            site_data["physical_address"] = physical_address
        if shipping_address:
            site_data["shipping_address"] = shipping_address
        if contact_name:
            site_data["contact_name"] = contact_name
        if contact_phone:
            site_data["contact_phone"] = contact_phone
        if contact_email:
            site_data["contact_email"] = contact_email
        
        # Use dynamic API with safety
        result = client.dcim.sites.create(confirm=confirm, **site_data)
        
        return {
            "success": True,
            "action": "created",
            "object_type": "site",
            "site": result,
            "dry_run": result.get("dry_run", False)
        }
        
    except Exception as e:
        logger.error(f"Failed to create site {name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@mcp_tool(category="dcim")
def netbox_get_site_info(
    client: NetBoxClient,
    site_name: str
) -> Dict[str, Any]:
    """
    Get detailed information about ONE specific site by name.

    This tool is exclusively intended for retrieving details of a single,
    already known site. Use 'netbox_list_all_sites' for open, exploratory questions.

    Args:
        client: NetBoxClient instance (injected)
        site_name: The exact name of the site to be retrieved
        
    Returns:
        Site information including racks, devices, and statistics
        
    Example:
        netbox_get_site_info("Amsterdam DC")
    """
    try:
        logger.info(f"Getting site information: {site_name}")
        
        # Find the site
        # ULTRATHINK FIX 1: Expand search parameters with comprehensive relationship data\n        site_search_params = {\n            \"expand\": [\"region\", \"tenant\"],\n            \"limit\": 50\n        }\n\n        # ULTRATHINK FIX 2: ID resolution with fallback patterns\n        sites = None\n        if site_name.isdigit():\n            sites = list(client.dcim.sites.filter(id=int(site_name), **site_search_params))\n\n        if not sites:\n            sites = list(client.dcim.sites.filter(name=site_name, **site_search_params))\n\n        # ULTRATHINK FIX 4: Slug-based fallback mechanisms\n        if not sites:\n            sites = list(client.dcim.sites.filter(slug=site_name, **site_search_params))
        
        if not sites:
            return {
                "success": False,
                "error": f"Site '{site_name}' not found",
                "error_type": "SiteNotFound"
            }
        
        site = sites[0]
        site_id = site["id"]
        
        # Get related objects
        racks = client.dcim.racks.filter(site_id=site_id)
        devices = client.dcim.devices.filter(site_id=site_id)
        
        return {
            "success": True,
            "site": site,
            "statistics": {
                "rack_count": len(racks),
                "device_count": len(devices),
                "total_rack_units": sum(rack.get("u_height", 0) for rack in racks)
            },
            "racks": racks,
            "devices": devices[:10]  # Limit to first 10 devices
        }
        
    except Exception as e:
        logger.error(f"Failed to get site info for {site_name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@mcp_tool(category="dcim")
def netbox_list_all_sites(
    client: NetBoxClient,
    limit: int = 100,
    region_name: Optional[str] = None,
    status: Optional[str] = None,
    tenant_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get a summarized list of all sites in NetBox.

    This function is the correct choice for open, exploratory questions like
    "what sites are there?" or "show all active locations". Use 
    'netbox_get_site_info' for detailed information about one specific site.
    
    Args:
        client: NetBoxClient instance (injected by dependency system)
        limit: Maximum number of results to return (default: 100)
        region_name: Filter by region name (optional)
        status: Filter by site status (active, planned, retired, etc.)
        tenant_name: Filter by tenant name (optional)
        
    Returns:
        Dictionary containing:
        - count: Total number of sites found
        - sites: List of summarized site information
        - filters_applied: Dictionary of filters that were applied
        - summary_stats: Aggregate statistics about the sites
        
    Example:
        netbox_list_all_sites(status="active", region_name="europe")
        netbox_list_all_sites(tenant_name="customer-a", limit=20)
    """
    try:
        logger.info(f"Listing sites with filters - region: {region_name}, status: {status}, tenant: {tenant_name}")
        
        # Build filters dictionary - only include non-None values
        filters = {}
        if region_name:
            filters['region'] = region_name
        if status:
            filters['status'] = status
        if tenant_name:
            filters['tenant'] = tenant_name
        
        # Execute filtered query with limit
        sites = list(client.dcim.sites.filter(**filters))
        
        # Apply limit after fetching
        if len(sites) > limit:
            sites = sites[:limit]
        
        # Generate summary statistics
        status_counts = {}
        region_counts = {}
        tenant_counts = {}
        
        # Collect device and rack statistics for each site
        total_devices = 0
        total_racks = 0
        
        for site in sites:
            # Status breakdown with defensive checks for dictionary access
            status_obj = site.get("status", {})
            if isinstance(status_obj, dict):
                status = status_obj.get("label", "N/A")
            else:
                status = str(status_obj) if status_obj else "N/A"
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Region breakdown with defensive checks for dictionary access
            region_obj = site.get("region")
            if region_obj:
                if isinstance(region_obj, dict):
                    region_name = region_obj.get("name", str(region_obj))
                else:
                    region_name = str(region_obj)
                region_counts[region_name] = region_counts.get(region_name, 0) + 1
            
            # Tenant breakdown with defensive checks for dictionary access
            tenant_obj = site.get("tenant")
            if tenant_obj:
                if isinstance(tenant_obj, dict):
                    tenant_name = tenant_obj.get("name", str(tenant_obj))
                else:
                    tenant_name = str(tenant_obj)
                tenant_counts[tenant_name] = tenant_counts.get(tenant_name, 0) + 1
            
            # Get basic counts for this site (efficient queries)
            site_id = site.get("id")
            site_devices = list(client.dcim.devices.filter(site_id=site_id))
            site_racks = list(client.dcim.racks.filter(site_id=site_id))
            
            total_devices += len(site_devices)
            total_racks += len(site_racks)
        
        # Create human-readable site list
        site_list = []
        for site in sites:
            # Get counts for this specific site
            site_id = site.get("id")
            site_devices = list(client.dcim.devices.filter(site_id=site_id))
            site_racks = list(client.dcim.racks.filter(site_id=site_id))
            
            # DEFENSIVE CHECK: Handle dictionary access for all site attributes
            status_obj = site.get("status", {})
            if isinstance(status_obj, dict):
                status = status_obj.get("label", "N/A")
            else:
                status = str(status_obj) if status_obj else "N/A"
            
            region_obj = site.get("region")
            region_name = None
            if region_obj:
                if isinstance(region_obj, dict):
                    region_name = region_obj.get("name")
                else:
                    region_name = str(region_obj)
            
            tenant_obj = site.get("tenant")
            if tenant_obj:
                if isinstance(tenant_obj, dict):
                    tenant_name = tenant_obj.get("name", "N/A")
                else:
                    tenant_name = str(tenant_obj)
            else:
                tenant_name = "N/A"
            
            site_info = {
                "name": site.get("name", "Unknown"),
                "slug": site.get("slug", ""),
                "status": status,
                "region": region_name,
                "tenant": tenant_name,
                # DEFENSIVE CHECK: Ensure description is never None
                "description": site.get("description", ""),
                "physical_address": site.get("physical_address"),
                "device_count": len(site_devices),
                "rack_count": len(site_racks),
                "total_rack_units": sum(rack.get("u_height", 0) for rack in site_racks if rack.get("u_height")),
                "contact_name": site.get("contact_name"),
                "contact_email": site.get("contact_email")
            }
            site_list.append(site_info)
        
        result = {
            "count": len(site_list),
            "sites": site_list,
            "filters_applied": {k: v for k, v in filters.items() if v is not None},
            "summary_stats": {
                "total_sites": len(site_list),
                "status_breakdown": status_counts,
                "region_breakdown": region_counts,
                "tenant_breakdown": tenant_counts,
                "total_devices_across_sites": total_devices,
                "total_racks_across_sites": total_racks,
                "sites_with_contact": len([s for s in site_list if s['contact_name']]),
                "sites_with_address": len([s for s in site_list if s['physical_address']])
            }
        }
        
        logger.info(f"Found {len(site_list)} sites matching criteria. Status breakdown: {status_counts}")
        return result
        
    except Exception as e:
        logger.error(f"Error listing sites: {e}")
        return {
            "count": 0,
            "sites": [],
            "error": str(e),
            "error_type": type(e).__name__,
            "filters_applied": {k: v for k, v in {
                'region_name': region_name,
                'status': status,
                'tenant_name': tenant_name
            }.items() if v is not None}
        }


# TODO: Implement advanced site management tools:
# - netbox_plan_site_capacity
# - netbox_manage_multi_site_infrastructure  
# - netbox_report_site_utilization
# - netbox_analyze_site_geography
# - netbox_manage_site_interconnections