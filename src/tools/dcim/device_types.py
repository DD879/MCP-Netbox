#!/usr/bin/env python3
"""
DCIM Device Type Management Tools

High-level tools for managing NetBox device types with enterprise-grade functionality.
"""

from typing import Dict, Optional, Any
import logging
from ...registry import mcp_tool
from ...client import NetBoxClient

logger = logging.getLogger(__name__)


@mcp_tool(category="dcim")
def netbox_create_device_type(
    client: NetBoxClient,
    model: str,
    manufacturer: str,
    slug: str,
    u_height: int = 1,
    is_full_depth: bool = True,
    part_number: Optional[str] = None,
    description: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Create a new device type in NetBox DCIM.
    
    Args:
        client: NetBoxClient instance (injected)
        model: Device model name
        manufacturer: Manufacturer name or slug
        slug: URL-friendly identifier
        u_height: Height in rack units (1-100)
        is_full_depth: Whether device takes full rack depth
        part_number: Manufacturer part number
        description: Optional description
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Created device type information or error details
        
    Example:
        netbox_create_device_type("ISR4331", "cisco", "isr4331", u_height=2, confirm=True)
    """
    try:
        if not model or not manufacturer or not slug:
            return {
                "success": False,
                "error": "Model, manufacturer, and slug are required",
                "error_type": "ValidationError"
            }
        
        if not (1 <= u_height <= 100):
            return {
                "success": False,
                "error": "U-height must be between 1 and 100",
                "error_type": "ValidationError"
            }
        
        logger.info(f"Creating device type: {model} ({manufacturer})")
        
        # Resolve manufacturer to ID if slug provided
        manufacturer_id = manufacturer
        if isinstance(manufacturer, str) and not manufacturer.isdigit():
            # Try to find manufacturer by slug or name
            manufacturers = client.dcim.manufacturers.filter(slug=manufacturer)
            if not manufacturers:
                manufacturers = client.dcim.manufacturers.filter(name=manufacturer)
            if manufacturers:
                manufacturer_id = manufacturers[0]["id"]
            else:
                return {
                    "success": False,
                    "error": f"Manufacturer '{manufacturer}' not found",
                    "error_type": "ManufacturerNotFound"
                }
        
        # Build device type data
        device_type_data = {
            "model": model,
            "manufacturer": manufacturer_id,
            "slug": slug,
            "u_height": u_height,
            "is_full_depth": is_full_depth
        }
        
        if part_number:
            device_type_data["part_number"] = part_number
        if description:
            device_type_data["description"] = description
        
        # Use dynamic API with safety
        result = client.dcim.device_types.create(confirm=confirm, **device_type_data)
        
        return {
            "success": True,
            "action": "created",
            "object_type": "device_type",
            "device_type": result,
            "dry_run": result.get("dry_run", False)
        }
        
    except Exception as e:
        logger.error(f"Failed to create device type {model}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@mcp_tool(category="dcim")
def netbox_list_all_device_types(
    client: NetBoxClient,
    limit: int = 100,
    manufacturer_name: Optional[str] = None,
    u_height: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get summarized list of device types with usage statistics.
    
    This tool provides bulk device type discovery across the NetBox DCIM infrastructure,
    enabling efficient device catalog management, procurement planning, and hardware
    standardization. Essential for device lifecycle management and hardware planning.
    
    Args:
        client: NetBoxClient instance (injected by dependency system)
        limit: Maximum number of results to return (default: 100)
        manufacturer_name: Filter by manufacturer name (optional)
        u_height: Filter by rack unit height (optional)
        
    Returns:
        Dictionary containing:
        - count: Total number of device types found
        - device_types: List of summarized device type information
        - filters_applied: Dictionary of filters that were applied
        - summary_stats: Aggregate statistics about the device types
        
    Example:
        netbox_list_all_device_types()
        netbox_list_all_device_types(manufacturer_name="cisco", u_height=1)
        netbox_list_all_device_types(limit=50)
    """
    try:
        logger.info(f"Listing device types with filters - manufacturer: {manufacturer_name}, u_height: {u_height}")
        
        # Build filters dictionary - only include non-None values
        filters = {}
        if manufacturer_name:
            filters['manufacturer'] = manufacturer_name
        if u_height is not None:
            filters['u_height'] = u_height
        
        # Execute filtered query with limit
        device_types = list(client.dcim.device_types.filter(**filters))
        
        # Apply limit after fetching
        if len(device_types) > limit:
            device_types = device_types[:limit]
        
        # Generate summary statistics
        manufacturer_counts = {}
        u_height_counts = {}
        total_devices = 0
        device_types_with_devices = 0
        
        # Create human-readable device type list
        device_type_list = []
        for device_type in device_types:
            # Get manufacturer information with defensive dictionary access
            manufacturer_name = "Unknown"
            manufacturer_obj = device_type.get("manufacturer")
            if manufacturer_obj:
                if isinstance(manufacturer_obj, dict):
                    manufacturer_name = manufacturer_obj.get("name", "Unknown")
                else:
                    # If it's an ID, look up the manufacturer
                    try:
                        manufacturer_detail = client.dcim.manufacturers.get(manufacturer_obj)
                        if isinstance(manufacturer_detail, dict):
                            manufacturer_name = manufacturer_detail.get("name", str(manufacturer_obj))
                        else:
                            manufacturer_name = str(manufacturer_obj)
                    except:
                        manufacturer_name = str(manufacturer_obj)
            
            # Manufacturer breakdown
            manufacturer_counts[manufacturer_name] = manufacturer_counts.get(manufacturer_name, 0) + 1
            
            # U-height breakdown with defensive dictionary access
            u_height = device_type.get("u_height", 1)
            u_height_counts[f"{u_height}U"] = u_height_counts.get(f"{u_height}U", 0) + 1
            
            # Get devices using this device type
            device_type_id = device_type.get("id")
            devices_of_type = list(client.dcim.devices.filter(device_type_id=device_type_id))
            device_count = len(devices_of_type)
            total_devices += device_count
            if device_count > 0:
                device_types_with_devices += 1
            
            device_type_info = {
                "model": device_type.get("model", "Unknown"),
                "manufacturer": manufacturer_name,
                "slug": device_type.get("slug", ""),
                "u_height": u_height,
                "is_full_depth": device_type.get("is_full_depth"),
                "part_number": device_type.get("part_number"),
                "description": device_type.get("description"),
                "device_count": device_count,
                "created": device_type.get("created"),
                "last_updated": device_type.get("last_updated")
            }
            device_type_list.append(device_type_info)
        
        # Sort by device count (most used device types first)
        device_type_list.sort(key=lambda dt: dt['device_count'], reverse=True)
        
        result = {
            "count": len(device_type_list),
            "device_types": device_type_list,
            "filters_applied": {k: v for k, v in filters.items() if v is not None},
            "summary_stats": {
                "total_device_types": len(device_type_list),
                "manufacturer_breakdown": manufacturer_counts,
                "u_height_breakdown": u_height_counts,
                "total_devices_using_types": total_devices,
                "device_types_in_use": device_types_with_devices,
                "device_types_unused": len(device_type_list) - device_types_with_devices,
                "average_devices_per_type": round(total_devices / len(device_type_list), 1) if device_type_list else 0,
                "most_used_types": [dt["model"] for dt in device_type_list[:5] if dt["device_count"] > 0],
                "rack_space_breakdown": {
                    "1U_types": len([dt for dt in device_type_list if dt["u_height"] == 1]),
                    "2U_types": len([dt for dt in device_type_list if dt["u_height"] == 2]),
                    "large_types": len([dt for dt in device_type_list if dt["u_height"] > 2])
                }
            }
        }
        
        logger.info(f"Found {len(device_type_list)} device types matching criteria. Total devices using types: {total_devices}")
        return result
        
    except Exception as e:
        logger.error(f"Error listing device types: {e}")
        return {
            "count": 0,
            "device_types": [],
            "error": str(e),
            "error_type": type(e).__name__,
            "filters_applied": {k: v for k, v in {
                'manufacturer_name': manufacturer_name,
                'u_height': u_height
            }.items() if v is not None}
        }


@mcp_tool(category="dcim")
def netbox_get_device_type_info(
    client: NetBoxClient,
    manufacturer: str,
    model: str
) -> Dict[str, Any]:
    """
    Get detailed information about a specific device type.
    
    This inspection tool provides comprehensive device type details including
    specifications, usage statistics, and component templates. Essential for
    device selection, compatibility verification, and hardware planning.
    
    Args:
        client: NetBoxClient instance (injected)
        manufacturer: Manufacturer name
        model: Device model name
        
    Returns:
        Detailed device type information or error details
        
    Example:
        netbox_get_device_type_info("Cisco", "ISR4331")
    """
    try:
        if not manufacturer or not model:
            return {
                "success": False,
                "error": "Manufacturer and model are required",
                "error_type": "ValidationError"
            }
        
        logger.info(f"Getting device type info for {model} by {manufacturer}")
        
        # Resolve manufacturer to ID
        manufacturers = client.dcim.manufacturers.filter(name=manufacturer)
        if not manufacturers:
            manufacturers = client.dcim.manufacturers.filter(slug=manufacturer)
        if not manufacturers:
            return {
                "success": False,
                "error": f"Manufacturer '{manufacturer}' not found",
                "error_type": "ManufacturerNotFound"
            }
        
        manufacturer_obj = manufacturers[0]
        manufacturer_id = manufacturer_obj.get('id') if isinstance(manufacturer_obj, dict) else manufacturer_obj.id
        manufacturer_name = manufacturer_obj.get('name') if isinstance(manufacturer_obj, dict) else manufacturer_obj.name
        
        # Find device type
        device_types = client.dcim.device_types.filter(manufacturer_id=manufacturer_id, model=model)
        if not device_types:
            return {
                "success": False,
                "error": f"Device type '{model}' by '{manufacturer}' not found",
                "error_type": "DeviceTypeNotFound"
            }
        
        device_type = device_types[0]
        
        # Apply defensive dict/object handling
        device_type_id = device_type.get('id') if isinstance(device_type, dict) else device_type.id
        device_model = device_type.get('model') if isinstance(device_type, dict) else device_type.model
        u_height = device_type.get('u_height') if isinstance(device_type, dict) else device_type.u_height
        is_full_depth = device_type.get('is_full_depth') if isinstance(device_type, dict) else device_type.is_full_depth
        part_number = device_type.get('part_number') if isinstance(device_type, dict) else getattr(device_type, 'part_number', None)
        description = device_type.get('description') if isinstance(device_type, dict) else getattr(device_type, 'description', '')
        slug = device_type.get('slug') if isinstance(device_type, dict) else device_type.slug
        
        # Count devices using this device type
        devices_using_type = list(client.dcim.devices.filter(device_type_id=device_type_id))
        device_count = len(devices_using_type)
        
        # Get component templates count
        interface_templates = list(client.dcim.interface_templates.filter(device_type_id=device_type_id))
        power_port_templates = list(client.dcim.power_port_templates.filter(device_type_id=device_type_id))
        console_port_templates = list(client.dcim.console_port_templates.filter(device_type_id=device_type_id))
        console_server_port_templates = list(client.dcim.console_server_port_templates.filter(device_type_id=device_type_id))
        power_outlet_templates = list(client.dcim.power_outlet_templates.filter(device_type_id=device_type_id))
        front_port_templates = list(client.dcim.front_port_templates.filter(device_type_id=device_type_id))
        rear_port_templates = list(client.dcim.rear_port_templates.filter(device_type_id=device_type_id))
        device_bay_templates = list(client.dcim.device_bay_templates.filter(device_type_id=device_type_id))
        module_bay_templates = list(client.dcim.module_bay_templates.filter(device_type_id=device_type_id))
        
        component_summary = {
            "interface_templates": len(interface_templates),
            "power_port_templates": len(power_port_templates),
            "console_port_templates": len(console_port_templates),
            "console_server_port_templates": len(console_server_port_templates),
            "power_outlet_templates": len(power_outlet_templates),
            "front_port_templates": len(front_port_templates),
            "rear_port_templates": len(rear_port_templates),
            "device_bay_templates": len(device_bay_templates),
            "module_bay_templates": len(module_bay_templates),
            "total_templates": (
                len(interface_templates) + len(power_port_templates) + 
                len(console_port_templates) + len(console_server_port_templates) +
                len(power_outlet_templates) + len(front_port_templates) +
                len(rear_port_templates) + len(device_bay_templates) +
                len(module_bay_templates)
            )
        }
        
        return {
            "success": True,
            "device_type": {
                "id": device_type_id,
                "model": device_model,
                "manufacturer": {
                    "name": manufacturer_name,
                    "id": manufacturer_id
                },
                "slug": slug,
                "u_height": u_height,
                "is_full_depth": is_full_depth,
                "part_number": part_number,
                "description": description,
                "device_count": device_count,
                "component_templates": component_summary
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get device type info for {model} by {manufacturer}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@mcp_tool(category="dcim")
def netbox_update_device_type(
    client: NetBoxClient,
    manufacturer: str,
    model: str,
    new_model: Optional[str] = None,
    new_slug: Optional[str] = None,
    u_height: Optional[int] = None,
    is_full_depth: Optional[bool] = None,
    part_number: Optional[str] = None,
    description: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Update device type properties with enterprise safety validation.
    
    This enterprise-grade function enables device type updates including
    model name, specifications, and metadata. Uses established NetBox MCP
    update patterns with defensive error handling.
    
    Args:
        client: NetBoxClient instance (injected)
        manufacturer: Current manufacturer name
        model: Current device model name
        new_model: Updated model name
        new_slug: Updated URL-friendly identifier
        u_height: Updated height in rack units
        is_full_depth: Updated full depth flag
        part_number: Updated manufacturer part number
        description: Updated description
        confirm: Must be True to execute (enterprise safety)
        
    Returns:
        Success status with updated device type details or error information
        
    Example:
        netbox_update_device_type(
            manufacturer="Cisco",
            model="ISR4331",
            description="Updated 4-port router",
            u_height=2,
            confirm=True
        )
    """
    
    # STEP 1: DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Device Type would be updated. Set confirm=True to execute.",
            "would_update": {
                "manufacturer": manufacturer,
                "model": model,
                "new_model": new_model,
                "new_slug": new_slug,
                "u_height": u_height,
                "is_full_depth": is_full_depth,
                "part_number": part_number,
                "description": description
            }
        }
    
    # STEP 2: PARAMETER VALIDATION
    if not manufacturer or not manufacturer.strip():
        return {
            "success": False,
            "error": "Manufacturer cannot be empty",
            "error_type": "ValidationError"
        }
    
    if not model or not model.strip():
        return {
            "success": False,
            "error": "Model cannot be empty",
            "error_type": "ValidationError"
        }
    
    if u_height is not None and not (1 <= u_height <= 100):
        return {
            "success": False,
            "error": "U-height must be between 1 and 100",
            "error_type": "ValidationError"
        }
    
    if not any([new_model, new_slug, u_height, is_full_depth, part_number, description]):
        return {
            "success": False,
            "error": "At least one field must be provided for update",
            "error_type": "ValidationError"
        }
    
    logger.info(f"Updating device type '{model}' by '{manufacturer}'")
    
    try:
        # STEP 3: LOOKUP DEVICE TYPE (with defensive dict/object handling)
        # Find manufacturer first
        manufacturers = client.dcim.manufacturers.filter(name=manufacturer)
        if not manufacturers:
            manufacturers = client.dcim.manufacturers.filter(slug=manufacturer)
        if not manufacturers:
            return {
                "success": False,
                "error": f"Manufacturer '{manufacturer}' not found",
                "error_type": "ManufacturerNotFound"
            }
        
        manufacturer_obj = manufacturers[0]
        manufacturer_id = manufacturer_obj.get('id') if isinstance(manufacturer_obj, dict) else manufacturer_obj.id
        manufacturer_name = manufacturer_obj.get('name') if isinstance(manufacturer_obj, dict) else manufacturer_obj.name
        
        # Find device type
        device_types = client.dcim.device_types.filter(manufacturer_id=manufacturer_id, model=model)
        if not device_types:
            return {
                "success": False,
                "error": f"Device type '{model}' by '{manufacturer}' not found",
                "error_type": "DeviceTypeNotFound"
            }
        
        device_type = device_types[0]
        device_type_id = device_type.get('id') if isinstance(device_type, dict) else device_type.id
        
        # STEP 4: CONFLICT DETECTION - Check for slug conflicts if new_slug provided
        if new_slug:
            existing_slugs = client.dcim.device_types.filter(slug=new_slug, no_cache=True)
            # Exclude current device type from conflict check
            conflicting_slugs = [dt for dt in existing_slugs if (
                (dt.get('id') if isinstance(dt, dict) else dt.id) != device_type_id
            )]
            
            if conflicting_slugs:
                conflicting_type = conflicting_slugs[0]
                conflicting_id = conflicting_type.get('id') if isinstance(conflicting_type, dict) else conflicting_type.id
                return {
                    "success": False,
                    "error": f"Slug '{new_slug}' already exists for another device type (ID: {conflicting_id})",
                    "error_type": "SlugConflictError"
                }
        
        # STEP 5: BUILD UPDATE PAYLOAD
        update_payload = {}
        if new_model is not None:
            update_payload["model"] = new_model
        if new_slug is not None:
            update_payload["slug"] = new_slug
        if u_height is not None:
            update_payload["u_height"] = u_height
        if is_full_depth is not None:
            update_payload["is_full_depth"] = is_full_depth
        if part_number is not None:
            update_payload["part_number"] = part_number
        if description is not None:
            update_payload["description"] = description
        
        logger.info(f"Updating device type {device_type_id} with payload: {update_payload}")
        
        # STEP 6: UPDATE DEVICE TYPE - Use proven NetBox MCP update pattern
        updated_device_type = client.dcim.device_types.update(device_type_id, confirm=confirm, **update_payload)
        
        # Handle both dict and object responses
        updated_model = updated_device_type.get('model') if isinstance(updated_device_type, dict) else updated_device_type.model
        updated_slug = updated_device_type.get('slug') if isinstance(updated_device_type, dict) else updated_device_type.slug
        updated_u_height = updated_device_type.get('u_height') if isinstance(updated_device_type, dict) else updated_device_type.u_height
        
        logger.info(f"Successfully updated device type '{model}' by '{manufacturer}'")
        
        # STEP 7: RETURN SUCCESS
        return {
            "success": True,
            "message": f"Device Type '{model}' by '{manufacturer}' successfully updated.",
            "data": {
                "device_type_id": device_type_id,
                "manufacturer": {
                    "name": manufacturer_name,
                    "id": manufacturer_id
                },
                "original_model": model,
                "updated_fields": {
                    "model": updated_model,
                    "slug": updated_slug,
                    "u_height": updated_u_height,
                    "part_number": update_payload.get("part_number"),
                    "description": update_payload.get("description"),
                    "is_full_depth": update_payload.get("is_full_depth")
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to update device type '{model}' by '{manufacturer}': {e}")
        return {
            "success": False,
            "error": f"NetBox API error during device type update: {e}",
            "error_type": type(e).__name__
        }


@mcp_tool(category="dcim")
def netbox_delete_device_type(
    client: NetBoxClient,
    manufacturer: str,
    model: str,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Delete a device type with enterprise safety validation.
    
    This enterprise-grade function enables safe device type removal with comprehensive
    validation and dependency checking. Uses established NetBox MCP delete patterns
    with defensive error handling.
    
    SAFETY WARNING: This operation cannot be undone. Ensure no devices are using
    this device type before deletion.
    
    Args:
        client: NetBoxClient instance (injected)
        manufacturer: Manufacturer name
        model: Device model name to delete
        confirm: Must be True to execute (enterprise safety)
        
    Returns:
        Success status with deletion details or error information
        
    Example:
        netbox_delete_device_type(
            manufacturer="Cisco",
            model="ISR4331",
            confirm=True
        )
    """
    
    # STEP 1: DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Device Type would be deleted. Set confirm=True to execute.",
            "would_delete": {
                "manufacturer": manufacturer,
                "model": model
            },
            "warning": "This operation cannot be undone. Ensure no devices are using this device type."
        }
    
    # STEP 2: PARAMETER VALIDATION
    if not manufacturer or not manufacturer.strip():
        return {
            "success": False,
            "error": "Manufacturer cannot be empty",
            "error_type": "ValidationError"
        }
    
    if not model or not model.strip():
        return {
            "success": False,
            "error": "Model cannot be empty",
            "error_type": "ValidationError"
        }
    
    logger.info(f"Deleting device type '{model}' by '{manufacturer}'")
    
    try:
        # STEP 3: LOOKUP DEVICE TYPE (with defensive dict/object handling)
        # Find manufacturer first
        manufacturers = client.dcim.manufacturers.filter(name=manufacturer)
        if not manufacturers:
            manufacturers = client.dcim.manufacturers.filter(slug=manufacturer)
        if not manufacturers:
            return {
                "success": False,
                "error": f"Manufacturer '{manufacturer}' not found",
                "error_type": "ManufacturerNotFound"
            }
        
        manufacturer_obj = manufacturers[0]
        manufacturer_id = manufacturer_obj.get('id') if isinstance(manufacturer_obj, dict) else manufacturer_obj.id
        manufacturer_name = manufacturer_obj.get('name') if isinstance(manufacturer_obj, dict) else manufacturer_obj.name
        
        # Find device type
        device_types = client.dcim.device_types.filter(manufacturer_id=manufacturer_id, model=model)
        if not device_types:
            return {
                "success": False,
                "error": f"Device type '{model}' by '{manufacturer}' not found",
                "error_type": "DeviceTypeNotFound"
            }
        
        device_type = device_types[0]
        device_type_id = device_type.get('id') if isinstance(device_type, dict) else device_type.id
        device_type_model = device_type.get('model') if isinstance(device_type, dict) else device_type.model
        device_type_slug = device_type.get('slug') if isinstance(device_type, dict) else device_type.slug
        
        # STEP 4: DEPENDENCY CHECK - Check for devices using this device type
        devices_using_type = list(client.dcim.devices.filter(device_type_id=device_type_id, no_cache=True))
        if devices_using_type:
            device_names = []
            for device in devices_using_type[:5]:  # Show first 5 devices
                device_name = device.get('name') if isinstance(device, dict) else device.name
                device_names.append(device_name)
            
            return {
                "success": False,
                "error": f"Cannot delete device type '{model}' - {len(devices_using_type)} devices are using this type",
                "error_type": "DependencyError",
                "details": {
                    "devices_using_type": len(devices_using_type),
                    "example_devices": device_names,
                    "action_required": "Remove or change device type for all devices before deletion"
                }
            }
        
        logger.info(f"Deleting device type {device_type_id} ('{device_type_model}') - no dependencies found")
        
        # STEP 5: DELETE DEVICE TYPE - Use proven NetBox MCP delete pattern
        client.dcim.device_types.delete(device_type_id, confirm=confirm)
        
        logger.info(f"Successfully deleted device type '{model}' by '{manufacturer}'")
        
        # STEP 6: RETURN SUCCESS
        return {
            "success": True,
            "message": f"Device Type '{model}' by '{manufacturer}' successfully deleted.",
            "data": {
                "deleted_device_type": {
                    "id": device_type_id,
                    "model": device_type_model,
                    "slug": device_type_slug,
                    "manufacturer": {
                        "name": manufacturer_name,
                        "id": manufacturer_id
                    }
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to delete device type '{model}' by '{manufacturer}': {e}")
        return {
            "success": False,
            "error": f"NetBox API error during device type deletion: {e}",
            "error_type": type(e).__name__
        }