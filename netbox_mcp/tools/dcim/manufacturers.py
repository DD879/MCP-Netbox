#!/usr/bin/env python3
"""
DCIM Manufacturer Management Tools

High-level tools for managing NetBox manufacturers with enterprise-grade functionality.
"""

from typing import Dict, Optional, Any
import logging
from ...registry import mcp_tool
from ...client import NetBoxClient

logger = logging.getLogger(__name__)


@mcp_tool(category="dcim")
def netbox_create_manufacturer(
    client: NetBoxClient,
    name: str,
    slug: str,
    description: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Create a new manufacturer in NetBox DCIM.
    
    Args:
        client: NetBoxClient instance (injected)
        name: Manufacturer name
        slug: URL-friendly identifier
        description: Optional description
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Created manufacturer information or error details
        
    Example:
        netbox_create_manufacturer("Cisco Systems", "cisco", confirm=True)
    """
    try:
        if not name or not slug:
            return {
                "success": False,
                "error": "Manufacturer name and slug are required",
                "error_type": "ValidationError"
            }
        
        logger.info(f"Creating manufacturer: {name} (slug: {slug})")
        
        # Build manufacturer data
        manufacturer_data = {
            "name": name,
            "slug": slug
        }
        
        if description:
            manufacturer_data["description"] = description
        
        # Use dynamic API with safety
        result = client.dcim.manufacturers.create(confirm=confirm, **manufacturer_data)
        
        return {
            "success": True,
            "action": "created",
            "object_type": "manufacturer",
            "manufacturer": result,
            "dry_run": result.get("dry_run", False)
        }
        
    except Exception as e:
        logger.error(f"Failed to create manufacturer {name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@mcp_tool(category="dcim")
def netbox_list_all_manufacturers(
    client: NetBoxClient,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Get summarized list of manufacturers with device type statistics.
    
    This tool provides bulk manufacturer discovery across the NetBox DCIM infrastructure,
    enabling efficient vendor management, device catalog planning, and manufacturer
    oversight. Essential for device procurement and vendor relationship management.
    
    Args:
        client: NetBoxClient instance (injected by dependency system)
        limit: Maximum number of results to return (default: 100)
        
    Returns:
        Dictionary containing:
        - count: Total number of manufacturers found
        - manufacturers: List of summarized manufacturer information
        - summary_stats: Aggregate statistics about the manufacturers
        
    Example:
        netbox_list_all_manufacturers()
        netbox_list_all_manufacturers(limit=50)
    """
    try:
        logger.info(f"Listing manufacturers with limit: {limit}")
        
        # Execute query with limit
        manufacturers = list(client.dcim.manufacturers.all())
        
        # Apply limit after fetching
        if len(manufacturers) > limit:
            manufacturers = manufacturers[:limit]
        
        # Generate summary statistics
        total_device_types = 0
        total_devices = 0
        manufacturers_with_devices = 0
        
        # Create human-readable manufacturer list
        manufacturer_list = []
        for manufacturer in manufacturers:
            # Get device types for this manufacturer with defensive dictionary access
            manufacturer_id = manufacturer.get("id")
            device_types = list(client.dcim.device_types.filter(manufacturer_id=manufacturer_id))
            device_type_count = len(device_types)
            total_device_types += device_type_count
            
            # Get actual devices for this manufacturer (through device types)
            manufacturer_devices = 0
            for device_type in device_types:
                device_type_id = device_type.get("id") if isinstance(device_type, dict) else device_type
                devices_of_type = list(client.dcim.devices.filter(device_type_id=device_type_id))
                manufacturer_devices += len(devices_of_type)
            
            total_devices += manufacturer_devices
            if manufacturer_devices > 0:
                manufacturers_with_devices += 1
            
            manufacturer_info = {
                "name": manufacturer.get("name", "Unknown"),
                "slug": manufacturer.get("slug", ""),
                "description": manufacturer.get("description"),
                "device_type_count": device_type_count,
                "device_count": manufacturer_devices,
                "created": manufacturer.get("created"),
                "last_updated": manufacturer.get("last_updated")
            }
            manufacturer_list.append(manufacturer_info)
        
        # Sort by device count (most active manufacturers first)
        manufacturer_list.sort(key=lambda m: m['device_count'], reverse=True)
        
        result = {
            "count": len(manufacturer_list),
            "manufacturers": manufacturer_list,
            "summary_stats": {
                "total_manufacturers": len(manufacturer_list),
                "total_device_types": total_device_types,
                "total_devices": total_devices,
                "manufacturers_with_devices": manufacturers_with_devices,
                "manufacturers_without_devices": len(manufacturer_list) - manufacturers_with_devices,
                "average_device_types_per_manufacturer": round(total_device_types / len(manufacturer_list), 1) if manufacturer_list else 0,
                "average_devices_per_manufacturer": round(total_devices / len(manufacturer_list), 1) if manufacturer_list else 0,
                "top_manufacturers": [m["name"] for m in manufacturer_list[:5] if m["device_count"] > 0]
            }
        }
        
        logger.info(f"Found {len(manufacturer_list)} manufacturers. Total device types: {total_device_types}, Total devices: {total_devices}")
        return result
        
    except Exception as e:
        logger.error(f"Error listing manufacturers: {e}")
        return {
            "count": 0,
            "manufacturers": [],
            "error": str(e),
            "error_type": type(e).__name__
        }


# TODO: Implement advanced manufacturer management tools:
# - netbox_get_manufacturer_devices
# - netbox_get_manufacturer_statistics
# - netbox_update_manufacturer_info
# - netbox_merge_manufacturers