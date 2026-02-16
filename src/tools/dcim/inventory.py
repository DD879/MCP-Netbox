#!/usr/bin/env python3
"""
DCIM Inventory Management Tools

⚠️ **DEPRECATION WARNING**: NetBox v4.3+ has deprecated inventory items in favor of modules.
These tools will become obsolete in future NetBox releases. Consider using module 
management tools instead for new implementations.

Enterprise-grade tools for managing NetBox inventory items and inventory item templates.
These tools enable comprehensive tracking of device components, assets, and hierarchical
inventory management for complete device lifecycle documentation.

Key Features:
- Inventory Item Template Management: Define standard inventory for device types
- Device Inventory Management: Track actual inventory items on devices
- Hierarchical Inventory: Support parent/child relationships for complex assemblies
- Asset Tracking: Serial numbers, asset tags, part numbers, manufacturer information
- Enterprise Safety: Comprehensive validation, conflict detection, and dry-run capabilities

Inventory Components Supported:
- Physical Components: Memory, storage drives, CPUs, expansion cards
- Rack Components: Power supplies, fans, controllers
- Network Components: Transceivers, line cards, modules
- Custom Components: Any trackable asset or component

Migration Path:
- Inventory Item Templates → Module Types
- Inventory Items → Modules with enhanced functionality and user-defined attributes
"""

from typing import Dict, Optional, Any, List
import logging
from ...registry import mcp_tool
from ...client import NetBoxClient
from ...exceptions import (
    NetBoxValidationError as ValidationError,
    NetBoxNotFoundError as NotFoundError,
    NetBoxConflictError as ConflictError
)

logger = logging.getLogger(__name__)


# Validation Functions
def validate_component_type(component_type: str) -> Optional[str]:
    """
    Validate and convert component type to correct NetBox ContentType format.
    
    Args:
        component_type: Input component type (can be simple string or app.model format)
        
    Returns:
        Validated component type in 'app_label.model_name' format, or None for general inventory
        
    Raises:
        ValidationError: If component_type is invalid
    """
    if not component_type:
        return None
    
    # Valid NetBox ContentTypes for inventory items
    valid_content_types = [
        "dcim.interface", "dcim.powerport", "dcim.poweroutlet",
        "dcim.consoleport", "dcim.frontport", "dcim.rearport", 
        "dcim.modulebay", "dcim.devicebay",
        "circuits.circuittermination",
        "ipam.prefix", "ipam.ipaddress", "ipam.vlan"
    ]
    
    # If already in correct format, validate and return
    if '.' in component_type:
        if component_type in valid_content_types:
            return component_type
        else:
            raise ValidationError(
                f"Invalid component_type '{component_type}'. "
                f"Valid ContentTypes: {', '.join(valid_content_types)} or leave empty for general inventory."
            )
    
    # Convert simple strings to ContentType format or None for general inventory
    simple_to_contenttype = {
        # Network components
        "interface": "dcim.interface",
        "network": "dcim.interface", 
        "ethernet": "dcim.interface",
        "nic": "dcim.interface",
        
        # Power components
        "power": "dcim.powerport",
        "powerport": "dcim.powerport",
        "poweroutlet": "dcim.poweroutlet",
        "psu": "dcim.powerport",
        
        # Console components
        "console": "dcim.consoleport",
        "serial": "dcim.consoleport",
        
        # Physical ports
        "frontport": "dcim.frontport",
        "rearport": "dcim.rearport",
        
        # Bays and modules
        "module": "dcim.modulebay",
        "modulebay": "dcim.modulebay",
        "device": "dcim.devicebay",
        "devicebay": "dcim.devicebay",
        
        # General components (return None for general inventory)
        "general": None,
        "generic": None,
        "asset": None,
        "component": None,
        "storage": None,
        "memory": None,
        "cpu": None,
        "ssd": None,
        "hdd": None,
        "ram": None,
        "gpu": None,
        "fan": None,
        "controller": None,
        "transceiver": None,
        "expansion": None,
        "slot": None,
        "bay": None,
        "other": None
    }
    
    converted = simple_to_contenttype.get(component_type.lower())
    if converted is not None or component_type.lower() in simple_to_contenttype:
        return converted
    else:
        # Unknown component type - suggest using None for general inventory
        logger.warning(f"Unknown component type '{component_type}', using as general inventory item (no specific ContentType)")
        return None


def normalize_device_name(device_name: str) -> str:
    """Normalize device name for consistent lookup."""
    return device_name.strip().lower()


def validate_serial_format(serial: str) -> None:
    """Basic validation for serial number format."""
    if serial and (len(serial) < 3 or len(serial) > 50):
        raise ValidationError(f"Serial number '{serial}' must be between 3 and 50 characters")


# ======================================================================
# INVENTORY ITEM TEMPLATE MANAGEMENT
# ======================================================================

@mcp_tool(category="dcim")
def netbox_add_inventory_item_template_to_device_type(
    client: NetBoxClient,
    device_type_model: str,
    name: str,
    component_type: Optional[str] = None,
    component_id: Optional[int] = None,
    description: Optional[str] = None,
    part_id: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Add inventory item template to a device type for standardized inventory definition.
    
    ⚠️ **DEPRECATION WARNING**: NetBox v4.3+ has deprecated inventory items in favor of modules.
    This function will become obsolete in future NetBox releases. Consider using module 
    management tools instead for new implementations.
    
    This enterprise-grade function enables device type standardization by defining
    inventory items that should be present on all devices of a specific type.
    Essential for automated inventory provisioning and compliance checking.
    
    Args:
        client: NetBoxClient instance (injected)
        device_type_model: Device type model name (e.g., "PowerEdge R750")
        name: Inventory item template name (e.g., "Drive Bay 1", "Memory Slot A1")
        component_type: Component category (Memory, Storage, CPU, etc.)
        component_id: Optional component identifier
        description: Detailed description of the inventory item
        part_id: Part number template or specification
        confirm: Must be True to execute (enterprise safety)
        
    Returns:
        Success status with template details or error information
        
    Example:
        netbox_add_inventory_item_template_to_device_type(
            device_type_model="PowerEdge R750",
            name="Drive Bay 1",
            component_type="Storage",
            description="2.5-inch SATA/SAS/NVMe drive bay",
            part_id="DRIVE-BAY-2.5",
            confirm=True
        )
    """
    
    # STEP 1: DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Inventory Item Template would be created. Set confirm=True to execute.",
            "would_create": {
                "device_type_model": device_type_model,
                "template_name": name,
                "component_type": component_type,
                "description": description,
                "part_id": part_id
            }
        }
    
    # STEP 2: PARAMETER VALIDATION
    if not device_type_model or not device_type_model.strip():
        raise ValidationError("Device type model cannot be empty")
    
    if not name or not name.strip():
        raise ValidationError("Inventory item template name cannot be empty")
    
    # Validate and convert component_type to correct NetBox ContentType format
    validated_component_type = None
    if component_type:
        validated_component_type = validate_component_type(component_type)
    
    logger.info(f"Creating Inventory Item Template '{name}' for Device Type '{device_type_model}'")
    
    # STEP 3: ULTRATHINK OPTIMIZATION - Enhanced Device Type lookup with expand parameters
    try:
        # ULTRATHINK FIX 1: Expand Parameters + ULTRATHINK FIX 5: List Handling
        device_types = list(client.dcim.device_types.filter(
            model=device_type_model,
            expand=["manufacturer"]
        ))

        # ULTRATHINK FIX 4: Slug-Based Fallback
        if not device_types:
            slug_candidate = device_type_model.lower().replace(' ', '-').replace('_', '-')
            device_types = list(client.dcim.device_types.filter(
                slug=slug_candidate,
                expand=["manufacturer"]
            ))

        # ULTRATHINK FIX 6: Fallback Filtering - Client-side partial match if needed
        if not device_types:
            all_device_types = list(client.dcim.device_types.filter(expand=["manufacturer"]))
            device_types = [
                dt for dt in all_device_types
                if device_type_model.lower() in dt.get('model', '').lower()
            ]

        if not device_types:
            logger.error(f"Device Type '{device_type_model}' not found")
            raise NotFoundError(f"Device Type '{device_type_model}' not found. Create the device type first.")

        # ULTRATHINK FIX 3: Defensive Dict/Object Handling
        device_type = device_types[0] if device_types else None
        if not device_type:
            raise NotFoundError(f"Device Type '{device_type_model}' not found.")
        # CRITICAL: Apply defensive dict/object handling to ALL NetBox responses
        device_type_id = device_type.get('id') if isinstance(device_type, dict) else device_type.id
        device_type_display = device_type.get('display', device_type_model) if isinstance(device_type, dict) else getattr(device_type, 'display', device_type_model)
        logger.info(f"Found Device Type: {device_type_display} (ID: {device_type_id})")
        
    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Error looking up device type '{device_type_model}': {e}")
        raise ValidationError(f"Failed to resolve device type '{device_type_model}': {e}")
    
    # STEP 4: CONFLICT DETECTION - Check for existing template
    logger.info(f"Checking for existing Inventory Item Template '{name}' on Device Type '{device_type_model}'")
    
    try:
        existing_templates = client.dcim.inventory_item_templates.filter(
            device_type_id=device_type_id,
            name=name,
            no_cache=True  # Force live check for accurate conflict detection
        )
        
        if existing_templates:
            existing_template = existing_templates[0]
            existing_id = existing_template.get('id') if isinstance(existing_template, dict) else existing_template.id
            logger.warning(f"Inventory Item Template conflict detected: '{name}' already exists for Device Type '{device_type_model}' (ID: {existing_id})")
            raise ConflictError(
                resource_type="Inventory Item Template",
                identifier=f"{name} for Device Type {device_type_model}",
                existing_id=existing_id
            )
            
    except ConflictError:
        raise
    except Exception as e:
        logger.warning(f"Could not check for existing inventory item templates: {e}")
    
    # STEP 5: CREATE INVENTORY ITEM TEMPLATE
    create_payload = {
        "device_type": device_type_id,
        "name": name,
        "description": description or ""
    }
    
    # Add optional fields with validated component_type
    if validated_component_type is not None:
        create_payload["component_type"] = validated_component_type
    if component_id is not None:
        create_payload["component_id"] = component_id
    if part_id:
        create_payload["part_id"] = part_id
    
    logger.info(f"Creating Inventory Item Template with payload: {create_payload}")
    
    try:
        new_template = client.dcim.inventory_item_templates.create(confirm=confirm, **create_payload)
        
        # Handle both dict and object responses
        template_id = new_template.get('id') if isinstance(new_template, dict) else new_template.id
        template_name = new_template.get('name') if isinstance(new_template, dict) else new_template.name
        
        logger.info(f"Successfully created Inventory Item Template '{template_name}' (ID: {template_id})")
        
    except Exception as e:
        logger.error(f"NetBox API error during template creation: {e}")
        raise ValidationError(f"NetBox API error during inventory item template creation: {e}")
    
    # STEP 6: RETURN SUCCESS
    return {
        "success": True,
        "message": f"Inventory Item Template '{name}' successfully created for Device Type '{device_type_model}'.",
        "data": {
            "template_id": template_id,
            "template_name": template_name,
            "device_type_model": device_type_model,
            "device_type_id": device_type_id,
            "component_type": create_payload.get("component_type"),
            "part_id": create_payload.get("part_id"),
            "description": create_payload.get("description")
        }
    }


@mcp_tool(category="dcim")
def netbox_list_inventory_item_templates_for_device_type(
    client: NetBoxClient,
    device_type_model: str,
    limit: int = 100
) -> Dict[str, Any]:
    """
    List all inventory item templates for a specific device type.
    
    This tool provides comprehensive visibility into standardized inventory
    definitions for device types, enabling inventory planning and compliance
    verification across device deployments.
    
    Args:
        client: NetBoxClient instance (injected)
        device_type_model: Device type model name
        limit: Maximum number of templates to return (default: 100)
        
    Returns:
        List of inventory item templates with comprehensive details
        
    Example:
        netbox_list_inventory_item_templates_for_device_type(
            device_type_model="PowerEdge R750"
        )
    """
    
    if not device_type_model or not device_type_model.strip():
        raise ValidationError("Device type model cannot be empty")
    
    logger.info(f"Listing Inventory Item Templates for Device Type '{device_type_model}'")
    
    # STEP 1: LOOKUP DEVICE TYPE
    try:
        # ULTRATHINK FIX 1: Expand Parameters + ULTRATHINK FIX 5: List Handling
        device_types = list(client.dcim.device_types.filter(
            model=device_type_model,
            expand=["manufacturer"]
        ))

        # ULTRATHINK FIX 4: Slug-Based Fallback
        if not device_types:
            slug_candidate = device_type_model.lower().replace(' ', '-').replace('_', '-')
            device_types = list(client.dcim.device_types.filter(
                slug=slug_candidate,
                expand=["manufacturer"]
            ))

        # ULTRATHINK FIX 6: Fallback Filtering - Client-side partial match if needed
        if not device_types:
            all_device_types = list(client.dcim.device_types.filter(expand=["manufacturer"]))
            device_types = [
                dt for dt in all_device_types
                if device_type_model.lower() in dt.get('model', '').lower()
            ]

        if not device_types:
            raise NotFoundError(f"Device Type '{device_type_model}' not found")

        # ULTRATHINK FIX 3: Defensive Dict/Object Handling
        device_type = device_types[0] if device_types else None
        if not device_type:
            raise NotFoundError(f"Device Type '{device_type_model}' not found")

        device_data = device_type if isinstance(device_type, dict) else device_type.serialize()
        device_type_id = device_data.get('id')
        device_type_display = device_data.get('display', device_type_model)

    except NotFoundError:
        raise
    except Exception as e:
        raise NotFoundError(f"Could not find device type '{device_type_model}': {e}")
    
    # STEP 2: GET INVENTORY ITEM TEMPLATES
    try:
        templates = client.dcim.inventory_item_templates.filter(
            device_type_id=device_type_id,
            limit=limit
        )
        
        if not templates:
            return {
                "success": True,
                "message": f"No inventory item templates found for Device Type '{device_type_model}'.",
                "data": {
                    "device_type_model": device_type_model,
                    "device_type_id": device_type_id,
                    "template_count": 0,
                    "templates": []
                }
            }
        
        # Process templates with defensive handling
        template_list = []
        for template in templates:
            template_data = {
                "id": template.get('id') if isinstance(template, dict) else template.id,
                "name": template.get('name') if isinstance(template, dict) else template.name,
                "component_type": template.get('component_type') if isinstance(template, dict) else getattr(template, 'component_type', None),
                "component_id": template.get('component_id') if isinstance(template, dict) else getattr(template, 'component_id', None),
                "description": template.get('description') if isinstance(template, dict) else getattr(template, 'description', ''),
                "part_id": template.get('part_id') if isinstance(template, dict) else getattr(template, 'part_id', None)
            }
            template_list.append(template_data)
        
        # Sort by name for consistent output
        template_list.sort(key=lambda x: x['name'])
        
        return {
            "success": True,
            "message": f"Found {len(template_list)} inventory item template(s) for Device Type '{device_type_model}'.",
            "data": {
                "device_type_model": device_type_model,
                "device_type_display": device_type_display,
                "device_type_id": device_type_id,
                "template_count": len(template_list),
                "templates": template_list
            }
        }
        
    except Exception as e:
        logger.error(f"Error retrieving inventory item templates: {e}")
        raise ValidationError(f"Error retrieving inventory item templates for device type '{device_type_model}': {e}")


# ======================================================================
# DEVICE INVENTORY MANAGEMENT
# ======================================================================

@mcp_tool(category="dcim")
def netbox_add_inventory_item_to_device(
    client: NetBoxClient,
    device_name: str,
    name: str,
    component_type: Optional[str] = None,
    component_id: Optional[int] = None,
    description: Optional[str] = None,
    part_id: Optional[str] = None,
    serial: Optional[str] = None,
    asset_tag: Optional[str] = None,
    manufacturer: Optional[str] = None,
    parent_item: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Add inventory item to a specific device for asset tracking and documentation.
    
    ⚠️ **DEPRECATION WARNING**: NetBox v4.3+ has deprecated inventory items in favor of modules.
    This function will become obsolete in future NetBox releases. Consider using module 
    management tools instead for new implementations.
    
    This enterprise-grade function enables comprehensive device asset tracking
    by documenting actual inventory items installed on devices. Supports
    hierarchical inventory with parent/child relationships for complex assemblies.
    
    Args:
        client: NetBoxClient instance (injected)
        device_name: Target device name
        name: Inventory item name (e.g., "Drive Bay 1", "Memory Slot A1")
        component_type: Component category (Memory, Storage, CPU, etc.)
        component_id: Optional component identifier
        description: Detailed description
        part_id: Actual part number
        serial: Serial number for asset tracking
        asset_tag: Asset tag for inventory management
        manufacturer: Manufacturer name
        parent_item: Parent inventory item name (for hierarchical inventory)
        confirm: Must be True to execute (enterprise safety)
        
    Returns:
        Success status with inventory item details or error information
        
    Example:
        netbox_add_inventory_item_to_device(
            device_name="srv-web-01",
            name="Drive Bay 1",
            component_type="SSD",
            part_id="400-BDUN",
            serial="SSD8F3D92A1",
            manufacturer="Dell",
            description="960GB SATA 6Gbps 2.5-inch Hot-Plug SSD",
            confirm=True
        )
    """
    
    # STEP 1: DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Inventory Item would be created. Set confirm=True to execute.",
            "would_create": {
                "device_name": device_name,
                "item_name": name,
                "component_type": component_type,
                "part_id": part_id,
                "serial": serial,
                "asset_tag": asset_tag,
                "manufacturer": manufacturer,
                "parent_item": parent_item
            }
        }
    
    # STEP 2: PARAMETER VALIDATION
    if not device_name or not device_name.strip():
        raise ValidationError("Device name cannot be empty")
    
    if not name or not name.strip():
        raise ValidationError("Inventory item name cannot be empty")
    
    # Validate and convert component_type to correct NetBox ContentType format
    validated_component_type = None
    if component_type:
        validated_component_type = validate_component_type(component_type)
    
    if serial:
        validate_serial_format(serial)
    
    device_name_normalized = normalize_device_name(device_name)
    logger.info(f"Adding Inventory Item '{name}' to Device '{device_name}'")
    
    # STEP 3: ULTRATHINK OPTIMIZATION - Enhanced Device lookup with expand parameters
    try:
        # ULTRATHINK FIX 1: Expand Parameters + ULTRATHINK FIX 5: List Handling
        devices = list(client.dcim.devices.filter(
            name=device_name,
            expand=["device_type", "site", "rack", "tenant", "role"]
        ))

        # ULTRATHINK FIX 6: Fallback Filtering - Client-side case-insensitive search
        if not devices:
            all_devices = list(client.dcim.devices.filter(expand=["device_type", "site", "rack", "tenant", "role"]))
            devices = [d for d in all_devices if normalize_device_name(
                d.get('name') if isinstance(d, dict) else d.name
            ) == device_name_normalized]
        
        if not devices:
            logger.error(f"Device '{device_name}' not found")
            raise NotFoundError(f"Device '{device_name}' not found. Verify the device exists in NetBox.")
        
        device = devices[0]
        device_id = device.get('id') if isinstance(device, dict) else device.id
        device_display = device.get('display', device_name) if isinstance(device, dict) else getattr(device, 'display', device_name)
        logger.info(f"Found Device: {device_display} (ID: {device_id})")
        
    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Error looking up device '{device_name}': {e}")
        raise ValidationError(f"Failed to resolve device '{device_name}': {e}")
    
    # STEP 4: LOOKUP PARENT ITEM (if specified)
    parent_item_id = None
    if parent_item:
        try:
            parent_items = client.dcim.inventory_items.filter(
                device_id=device_id,
                name=parent_item
            )
            
            if not parent_items:
                raise NotFoundError(f"Parent inventory item '{parent_item}' not found on device '{device_name}'")
            
            parent_item_obj = parent_items[0]
            parent_item_id = parent_item_obj.get('id') if isinstance(parent_item_obj, dict) else parent_item_obj.id
            logger.info(f"Found parent inventory item '{parent_item}' (ID: {parent_item_id})")
            
        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error resolving parent item '{parent_item}': {e}")
            raise ValidationError(f"Failed to resolve parent inventory item '{parent_item}': {e}")
    
    # STEP 5: LOOKUP MANUFACTURER (if specified)
    manufacturer_id = None
    if manufacturer:
        try:
            # ULTRATHINK FIX 1: Expand Parameters + ULTRATHINK FIX 5: List Handling
            manufacturers = list(client.dcim.manufacturers.filter(name=manufacturer))

            # ULTRATHINK FIX 4: Slug-Based Fallback
            if not manufacturers:
                slug_candidate = manufacturer.lower().replace(' ', '-').replace('_', '-')
                manufacturers = list(client.dcim.manufacturers.filter(slug=slug_candidate))

            # ULTRATHINK FIX 6: Fallback Filtering - Client-side partial match
            if not manufacturers:
                all_manufacturers = list(client.dcim.manufacturers.all())
                manufacturers = [
                    m for m in all_manufacturers
                    if manufacturer.lower() in m.get('name', '').lower()
                ]

            if manufacturers:
                # ULTRATHINK FIX 3: Defensive Dict/Object Handling
                manufacturer_obj = manufacturers[0] if manufacturers else None
                if manufacturer_obj:
                    manufacturer_data = manufacturer_obj if isinstance(manufacturer_obj, dict) else manufacturer_obj.serialize()
                    manufacturer_id = manufacturer_data.get('id')
                logger.info(f"Found manufacturer '{manufacturer}' (ID: {manufacturer_id})")
            else:
                logger.warning(f"Manufacturer '{manufacturer}' not found, will create inventory item without manufacturer reference")
                
        except Exception as e:
            logger.warning(f"Error resolving manufacturer '{manufacturer}': {e}")
    
    # STEP 6: CONFLICT DETECTION - Check for existing inventory item
    logger.info(f"Checking for existing Inventory Item '{name}' on Device '{device_name}'")
    
    try:
        existing_items = client.dcim.inventory_items.filter(
            device_id=device_id,
            name=name,
            no_cache=True  # Force live check for accurate conflict detection
        )
        
        if existing_items:
            existing_item = existing_items[0]
            existing_id = existing_item.get('id') if isinstance(existing_item, dict) else existing_item.id
            logger.warning(f"Inventory Item conflict detected: '{name}' already exists on Device '{device_name}' (ID: {existing_id})")
            raise ConflictError(
                resource_type="Inventory Item",
                identifier=f"{name} on Device {device_name}",
                existing_id=existing_id
            )
            
    except ConflictError:
        raise
    except Exception as e:
        logger.warning(f"Could not check for existing inventory items: {e}")
    
    # STEP 7: CREATE INVENTORY ITEM
    create_payload = {
        "device": device_id,
        "name": name,
        "description": description or ""
    }
    
    # Add optional fields with validated component_type
    if validated_component_type is not None:
        create_payload["component_type"] = validated_component_type
    if component_id is not None:
        create_payload["component_id"] = component_id
    if part_id:
        create_payload["part_id"] = part_id
    if serial:
        create_payload["serial"] = serial
    if asset_tag:
        create_payload["asset_tag"] = asset_tag
    if manufacturer_id:
        create_payload["manufacturer"] = manufacturer_id
    if parent_item_id:
        create_payload["parent"] = parent_item_id
    
    logger.info(f"Creating Inventory Item with payload: {create_payload}")
    
    try:
        new_item = client.dcim.inventory_items.create(confirm=confirm, **create_payload)
        
        # Handle both dict and object responses
        item_id = new_item.get('id') if isinstance(new_item, dict) else new_item.id
        item_name = new_item.get('name') if isinstance(new_item, dict) else new_item.name
        
        logger.info(f"Successfully created Inventory Item '{item_name}' (ID: {item_id})")
        
    except Exception as e:
        logger.error(f"NetBox API error during inventory item creation: {e}")
        raise ValidationError(f"NetBox API error during inventory item creation: {e}")
    
    # STEP 8: RETURN SUCCESS
    return {
        "success": True,
        "message": f"Inventory Item '{name}' successfully added to Device '{device_name}'.",
        "data": {
            "item_id": item_id,
            "item_name": item_name,
            "device_name": device_name,
            "device_id": device_id,
            "component_type": create_payload.get("component_type"),
            "part_id": create_payload.get("part_id"),
            "serial": create_payload.get("serial"),
            "asset_tag": create_payload.get("asset_tag"),
            "manufacturer_id": manufacturer_id,
            "parent_item_id": parent_item_id,
            "description": create_payload.get("description")
        }
    }


@mcp_tool(category="dcim")
def netbox_list_device_inventory(
    client: NetBoxClient,
    device_name: str,
    component_type: Optional[str] = None,
    include_hierarchy: bool = True
) -> Dict[str, Any]:
    """
    List all inventory items for a specific device with comprehensive details.
    
    This tool provides complete visibility into device inventory, supporting
    filtering by component type and hierarchical display for complex assemblies.
    Essential for asset management, compliance auditing, and inventory reporting.
    
    Args:
        client: NetBoxClient instance (injected)
        device_name: Target device name
        component_type: Optional filter by component type
        include_hierarchy: Include parent/child relationship information
        
    Returns:
        Comprehensive inventory listing with hierarchy and asset details
        
    Example:
        netbox_list_device_inventory(
            device_name="srv-web-01",
            component_type="Storage"
        )
    """
    
    if not device_name or not device_name.strip():
        raise ValidationError("Device name cannot be empty")
    
    device_name_normalized = normalize_device_name(device_name)
    logger.info(f"Listing Inventory for Device '{device_name}'")
    
    # STEP 1: LOOKUP DEVICE
    try:
        # ULTRATHINK FIX 1: Expand Parameters + ULTRATHINK FIX 5: List Handling
        devices = list(client.dcim.devices.filter(
            name=device_name,
            expand=["device_type", "site", "rack", "tenant", "role"]
        ))

        # ULTRATHINK FIX 6: Fallback Filtering - Client-side case-insensitive search
        if not devices:
            all_devices = list(client.dcim.devices.filter(expand=["device_type", "site", "rack", "tenant", "role"]))
            devices = [d for d in all_devices if normalize_device_name(
                d.get('name') if isinstance(d, dict) else d.name
            ) == device_name_normalized]
        
        if not devices:
            raise NotFoundError(f"Device '{device_name}' not found")
        
        device = devices[0]
        device_id = device.get('id') if isinstance(device, dict) else device.id
        device_display = device.get('display', device_name) if isinstance(device, dict) else getattr(device, 'display', device_name)
        
    except Exception as e:
        raise NotFoundError(f"Could not find device '{device_name}': {e}")
    
    # STEP 2: GET INVENTORY ITEMS
    try:
        filter_params = {"device_id": device_id}
        if component_type:
            filter_params["component_type"] = component_type
        
        inventory_items = client.dcim.inventory_items.filter(**filter_params)
        
        if not inventory_items:
            filter_desc = f" with component type '{component_type}'" if component_type else ""
            return {
                "success": True,
                "message": f"No inventory items found for Device '{device_name}'{filter_desc}.",
                "data": {
                    "device_name": device_name,
                    "device_id": device_id,
                    "inventory_count": 0,
                    "inventory_items": []
                }
            }
        
        # Process inventory items with defensive handling
        item_list = []
        for item in inventory_items:
            # Get manufacturer info if available
            manufacturer_obj = item.get('manufacturer') if isinstance(item, dict) else getattr(item, 'manufacturer', None)
            manufacturer_name = None
            if manufacturer_obj:
                if isinstance(manufacturer_obj, dict):
                    manufacturer_name = manufacturer_obj.get('name')
                else:
                    manufacturer_name = getattr(manufacturer_obj, 'name', None) if hasattr(manufacturer_obj, 'name') else str(manufacturer_obj)
            
            # Get parent item info if available
            parent_obj = item.get('parent') if isinstance(item, dict) else getattr(item, 'parent', None)
            parent_name = None
            if parent_obj:
                if isinstance(parent_obj, dict):
                    parent_name = parent_obj.get('name')
                else:
                    parent_name = getattr(parent_obj, 'name', None) if hasattr(parent_obj, 'name') else str(parent_obj)
            
            item_data = {
                "id": item.get('id') if isinstance(item, dict) else item.id,
                "name": item.get('name') if isinstance(item, dict) else item.name,
                "component_type": item.get('component_type') if isinstance(item, dict) else getattr(item, 'component_type', None),
                "component_id": item.get('component_id') if isinstance(item, dict) else getattr(item, 'component_id', None),
                "description": item.get('description') if isinstance(item, dict) else getattr(item, 'description', ''),
                "part_id": item.get('part_id') if isinstance(item, dict) else getattr(item, 'part_id', None),
                "serial": item.get('serial') if isinstance(item, dict) else getattr(item, 'serial', None),
                "asset_tag": item.get('asset_tag') if isinstance(item, dict) else getattr(item, 'asset_tag', None),
                "manufacturer": manufacturer_name,
                "parent_item": parent_name if include_hierarchy else None
            }
            item_list.append(item_data)
        
        # Sort by name for consistent output
        item_list.sort(key=lambda x: x['name'])
        
        # Generate summary statistics
        component_types = {}
        manufacturers = {}
        items_with_serial = 0
        
        for item in item_list:
            # Component type stats
            comp_type = item['component_type'] or 'Unknown'
            component_types[comp_type] = component_types.get(comp_type, 0) + 1
            
            # Manufacturer stats
            mfg = item['manufacturer'] or 'Unknown'
            manufacturers[mfg] = manufacturers.get(mfg, 0) + 1
            
            # Serial number tracking
            if item['serial']:
                items_with_serial += 1
        
        return {
            "success": True,
            "message": f"Found {len(item_list)} inventory item(s) for Device '{device_name}'.",
            "data": {
                "device_name": device_name,
                "device_display": device_display,
                "device_id": device_id,
                "inventory_count": len(item_list),
                "inventory_items": item_list,
                "summary": {
                    "component_types": component_types,
                    "manufacturers": manufacturers,
                    "items_with_serial": items_with_serial,
                    "total_items": len(item_list)
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error retrieving inventory items: {e}")
        raise ValidationError(f"Error retrieving inventory items for device '{device_name}': {e}")


@mcp_tool(category="dcim")
def netbox_update_inventory_item(
    client: NetBoxClient,
    device_name: str,
    item_name: str,
    serial: Optional[str] = None,
    asset_tag: Optional[str] = None,
    part_id: Optional[str] = None,
    description: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Update an existing inventory item with new asset information.
    
    This enterprise-grade function enables asset lifecycle management by updating
    inventory item details such as serial numbers, asset tags, and descriptions.
    Essential for maintaining accurate asset records throughout device lifecycle.
    
    Args:
        client: NetBoxClient instance (injected)
        device_name: Target device name
        item_name: Inventory item name to update
        serial: New serial number
        asset_tag: New asset tag
        part_id: New part number
        description: New description
        confirm: Must be True to execute (enterprise safety)
        
    Returns:
        Success status with updated inventory item details
        
    Example:
        netbox_update_inventory_item(
            device_name="srv-web-01",
            item_name="Drive Bay 1",
            serial="SSD8F3D92A1-NEW",
            asset_tag="ASSET-001234",
            confirm=True
        )
    """
    
    # STEP 1: DRY RUN CHECK
    if not confirm:
        updates = {}
        if serial is not None:
            updates["serial"] = serial
        if asset_tag is not None:
            updates["asset_tag"] = asset_tag
        if part_id is not None:
            updates["part_id"] = part_id
        if description is not None:
            updates["description"] = description
            
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Inventory Item would be updated. Set confirm=True to execute.",
            "would_update": {
                "device_name": device_name,
                "item_name": item_name,
                "updates": updates
            }
        }
    
    # STEP 2: PARAMETER VALIDATION
    if not device_name or not device_name.strip():
        raise ValidationError("Device name cannot be empty")
    
    if not item_name or not item_name.strip():
        raise ValidationError("Inventory item name cannot be empty")
    
    if serial:
        validate_serial_format(serial)
    
    # Check if at least one field is being updated
    has_updates = any([serial is not None, asset_tag is not None, part_id is not None, description is not None])
    if not has_updates:
        raise ValidationError("At least one field must be specified for update")
    
    device_name_normalized = normalize_device_name(device_name)
    logger.info(f"Updating Inventory Item '{item_name}' on Device '{device_name}'")
    
    # STEP 3: LOOKUP DEVICE
    try:
        devices = client.dcim.devices.filter(name=device_name)
        if not devices:
            all_devices = client.dcim.devices.all()
            devices = [d for d in all_devices if normalize_device_name(
                d.get('name') if isinstance(d, dict) else d.name
            ) == device_name_normalized]
        
        if not devices:
            raise NotFoundError(f"Device '{device_name}' not found")
        
        device = devices[0]
        device_id = device.get('id') if isinstance(device, dict) else device.id
        
    except Exception as e:
        raise NotFoundError(f"Could not find device '{device_name}': {e}")
    
    # STEP 4: LOOKUP INVENTORY ITEM
    try:
        inventory_items = client.dcim.inventory_items.filter(
            device_id=device_id,
            name=item_name
        )
        
        if not inventory_items:
            raise NotFoundError(f"Inventory item '{item_name}' not found on device '{device_name}'")
        
        inventory_item = inventory_items[0]
        item_id = inventory_item.get('id') if isinstance(inventory_item, dict) else inventory_item.id
        
    except NotFoundError:
        raise
    except Exception as e:
        raise ValidationError(f"Failed to find inventory item '{item_name}': {e}")
    
    # STEP 5: PREPARE UPDATE PAYLOAD
    update_payload = {}
    
    if serial is not None:
        update_payload["serial"] = serial
    if asset_tag is not None:
        update_payload["asset_tag"] = asset_tag
    if part_id is not None:
        update_payload["part_id"] = part_id
    if description is not None:
        update_payload["description"] = description
    
    logger.info(f"Updating Inventory Item ID {item_id} with payload: {update_payload}")
    
    # STEP 6: UPDATE INVENTORY ITEM
    try:
        # Use the direct update method with ID and confirm parameter (consistent with other MCP tools)
        updated_item = client.dcim.inventory_items.update(item_id, confirm=confirm, **update_payload)
        
        # Handle both dict and object responses
        updated_name = updated_item.get('name') if isinstance(updated_item, dict) else updated_item.name
        
        logger.info(f"Successfully updated Inventory Item '{updated_name}' (ID: {item_id})")
        
    except Exception as e:
        logger.error(f"NetBox API error during inventory item update: {e}")
        raise ValidationError(f"NetBox API error during inventory item update: {e}")
    
    # STEP 7: RETURN SUCCESS
    return {
        "success": True,
        "message": f"Inventory Item '{item_name}' successfully updated on Device '{device_name}'.",
        "data": {
            "item_id": item_id,
            "item_name": updated_name,
            "device_name": device_name,
            "device_id": device_id,
            "updates_applied": update_payload
        }
    }


@mcp_tool(category="dcim")
def netbox_remove_inventory_item(
    client: NetBoxClient,
    device_name: str,
    item_name: str,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Remove an inventory item from a device.
    
    This enterprise-grade function safely removes inventory items from devices
    with comprehensive validation and safety checks. Essential for asset
    decommissioning and inventory lifecycle management.
    
    Args:
        client: NetBoxClient instance (injected)
        device_name: Target device name
        item_name: Inventory item name to remove
        confirm: Must be True to execute (enterprise safety)
        
    Returns:
        Success status with removal confirmation
        
    Example:
        netbox_remove_inventory_item(
            device_name="srv-web-01",
            item_name="Old Drive Bay 1",
            confirm=True
        )
    """
    
    # STEP 1: DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Inventory Item would be removed. Set confirm=True to execute.",
            "would_remove": {
                "device_name": device_name,
                "item_name": item_name
            }
        }
    
    # STEP 2: PARAMETER VALIDATION
    if not device_name or not device_name.strip():
        raise ValidationError("Device name cannot be empty")
    
    if not item_name or not item_name.strip():
        raise ValidationError("Inventory item name cannot be empty")
    
    device_name_normalized = normalize_device_name(device_name)
    logger.info(f"Removing Inventory Item '{item_name}' from Device '{device_name}'")
    
    # STEP 3: LOOKUP DEVICE
    try:
        devices = client.dcim.devices.filter(name=device_name)
        if not devices:
            all_devices = client.dcim.devices.all()
            devices = [d for d in all_devices if normalize_device_name(
                d.get('name') if isinstance(d, dict) else d.name
            ) == device_name_normalized]
        
        if not devices:
            raise NotFoundError(f"Device '{device_name}' not found")
        
        device = devices[0]
        device_id = device.get('id') if isinstance(device, dict) else device.id
        
    except Exception as e:
        raise NotFoundError(f"Could not find device '{device_name}': {e}")
    
    # STEP 4: LOOKUP INVENTORY ITEM
    try:
        inventory_items = client.dcim.inventory_items.filter(
            device_id=device_id,
            name=item_name
        )
        
        if not inventory_items:
            raise NotFoundError(f"Inventory item '{item_name}' not found on device '{device_name}'")
        
        inventory_item = inventory_items[0]
        item_id = inventory_item.get('id') if isinstance(inventory_item, dict) else inventory_item.id
        
        # Check for child inventory items (hierarchical dependency)
        child_items = client.dcim.inventory_items.filter(parent_id=item_id)
        if child_items:
            child_names = [
                child.get('name') if isinstance(child, dict) else child.name 
                for child in child_items
            ]
            raise ValidationError(
                f"Cannot remove inventory item '{item_name}' because it has child items: {', '.join(child_names)}. "
                f"Remove child items first or use cascade removal if supported."
            )
        
    except NotFoundError:
        raise
    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError(f"Failed to find inventory item '{item_name}': {e}")
    
    # STEP 5: REMOVE INVENTORY ITEM
    try:
        # Use the direct delete method with ID and confirm parameter (consistent with other MCP tools)
        result = client.dcim.inventory_items.delete(item_id, confirm=confirm)
        logger.info(f"Successfully removed Inventory Item '{item_name}' (ID: {item_id})")
        
    except Exception as e:
        logger.error(f"NetBox API error during inventory item removal: {e}")
        raise ValidationError(f"NetBox API error during inventory item removal: {e}")
    
    # STEP 6: RETURN SUCCESS
    return {
        "success": True,
        "message": f"Inventory Item '{item_name}' successfully removed from Device '{device_name}'.",
        "data": {
            "removed_item_id": item_id,
            "removed_item_name": item_name,
            "device_name": device_name,
            "device_id": device_id
        }
    }


# ======================================================================
# BULK INVENTORY OPERATIONS
# ======================================================================

@mcp_tool(category="dcim")
def netbox_bulk_add_standard_inventory(
    client: NetBoxClient,
    device_name: str,
    inventory_preset: str,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Add standard inventory items to a device based on predefined presets.
    
    ⚠️ **DEPRECATION WARNING**: NetBox v4.3+ has deprecated inventory items in favor of modules.
    This function will become obsolete in future NetBox releases. Consider using module 
    management tools instead for new implementations.
    
    This enterprise-grade function enables rapid deployment of standardized
    inventory configurations, reducing manual work and ensuring consistency
    across device deployments.
    
    Args:
        client: NetBoxClient instance (injected)
        device_name: Target device name
        inventory_preset: Preset configuration name (server_standard, dell_poweredge_r750, etc.)
        confirm: Must be True to execute (enterprise safety)
        
    Returns:
        Success status with bulk creation results
        
    Available Presets:
        - server_standard: CPU, Memory slots, Drive bays
        - dell_poweredge_r750: Specific Dell R750 inventory
        - network_switch: Power supplies, Fan modules
        - storage_array: Disk shelves, Controllers
        
    Example:
        netbox_bulk_add_standard_inventory(
            device_name="srv-web-01",
            inventory_preset="server_standard",
            confirm=True
        )
    """
    
    # Define standard inventory presets
    INVENTORY_PRESETS = {
        "server_standard": [
            {"name": "CPU Socket 1", "component_type": "cpu", "description": "Primary CPU socket"},
            {"name": "CPU Socket 2", "component_type": "cpu", "description": "Secondary CPU socket"},
            {"name": "Memory Slot A1", "component_type": "memory", "description": "DDR4/DDR5 memory slot"},
            {"name": "Memory Slot A2", "component_type": "memory", "description": "DDR4/DDR5 memory slot"},
            {"name": "Memory Slot B1", "component_type": "memory", "description": "DDR4/DDR5 memory slot"},
            {"name": "Memory Slot B2", "component_type": "memory", "description": "DDR4/DDR5 memory slot"},
            {"name": "Drive Bay 1", "component_type": "storage", "description": "Primary storage bay"},
            {"name": "Drive Bay 2", "component_type": "storage", "description": "Secondary storage bay"},
            {"name": "Power Supply 1", "component_type": "general", "description": "Primary PSU"},
            {"name": "Power Supply 2", "component_type": "general", "description": "Redundant PSU"}
        ],
        "dell_poweredge_r750": [
            {"name": "CPU1", "component_type": "cpu", "description": "Intel Xeon CPU Socket 1", "part_id": "INTEL-XEON"},
            {"name": "CPU2", "component_type": "cpu", "description": "Intel Xeon CPU Socket 2", "part_id": "INTEL-XEON"},
            {"name": "DIMM_A1", "component_type": "memory", "description": "32GB DDR4-3200 RDIMM", "part_id": "32GB-DDR4"},
            {"name": "DIMM_A2", "component_type": "memory", "description": "32GB DDR4-3200 RDIMM", "part_id": "32GB-DDR4"},
            {"name": "DIMM_B1", "component_type": "memory", "description": "32GB DDR4-3200 RDIMM", "part_id": "32GB-DDR4"},
            {"name": "DIMM_B2", "component_type": "memory", "description": "32GB DDR4-3200 RDIMM", "part_id": "32GB-DDR4"},
            {"name": "Drive_Bay_1", "component_type": "storage", "description": "2.5-inch SATA/SAS/NVMe bay", "part_id": "DRIVE-BAY-2.5"},
            {"name": "Drive_Bay_2", "component_type": "storage", "description": "2.5-inch SATA/SAS/NVMe bay", "part_id": "DRIVE-BAY-2.5"},
            {"name": "PSU1", "component_type": "general", "description": "800W 80+ Platinum PSU", "part_id": "PSU-800W"},
            {"name": "PSU2", "component_type": "general", "description": "800W 80+ Platinum PSU", "part_id": "PSU-800W"}
        ],
        "network_switch": [
            {"name": "Power Module 1", "component_type": "power", "description": "Primary power module"},
            {"name": "Power Module 2", "component_type": "power", "description": "Redundant power module"},
            {"name": "Fan Module 1", "component_type": "fan", "description": "Primary cooling fan"},
            {"name": "Fan Module 2", "component_type": "fan", "description": "Secondary cooling fan"},
            {"name": "Fan Module 3", "component_type": "fan", "description": "Tertiary cooling fan"},
            {"name": "Supervisor Module", "component_type": "controller", "description": "Main control processor"},
            {"name": "Line Card Slot 1", "component_type": "general", "description": "Modular line card slot"},
            {"name": "Line Card Slot 2", "component_type": "general", "description": "Modular line card slot"}
        ],
        "storage_array": [
            {"name": "Controller A", "component_type": "controller", "description": "Primary storage controller"},
            {"name": "Controller B", "component_type": "controller", "description": "Secondary storage controller"},
            {"name": "Disk Shelf 1", "component_type": "storage", "description": "Primary disk enclosure"},
            {"name": "Disk Shelf 2", "component_type": "storage", "description": "Secondary disk enclosure"},
            {"name": "Cache Module A", "component_type": "memory", "description": "Controller A cache memory"},
            {"name": "Cache Module B", "component_type": "memory", "description": "Controller B cache memory"},
            {"name": "PSU A1", "component_type": "general", "description": "Controller A primary PSU"},
            {"name": "PSU A2", "component_type": "general", "description": "Controller A backup PSU"},
            {"name": "PSU B1", "component_type": "general", "description": "Controller B primary PSU"},
            {"name": "PSU B2", "component_type": "general", "description": "Controller B backup PSU"}
        ]
    }
    
    # STEP 1: DRY RUN CHECK
    if not confirm:
        preset_items = INVENTORY_PRESETS.get(inventory_preset, [])
        return {
            "success": True,
            "dry_run": True,
            "message": f"DRY RUN: {len(preset_items)} inventory items would be created. Set confirm=True to execute.",
            "would_create": {
                "device_name": device_name,
                "inventory_preset": inventory_preset,
                "item_count": len(preset_items),
                "items": preset_items
            }
        }
    
    # STEP 2: PARAMETER VALIDATION
    if not device_name or not device_name.strip():
        raise ValidationError("Device name cannot be empty")
    
    if not inventory_preset or not inventory_preset.strip():
        raise ValidationError("Inventory preset cannot be empty")
    
    if inventory_preset not in INVENTORY_PRESETS:
        available_presets = ", ".join(INVENTORY_PRESETS.keys())
        raise ValidationError(f"Unknown inventory preset '{inventory_preset}'. Available presets: {available_presets}")
    
    preset_items = INVENTORY_PRESETS[inventory_preset]
    device_name_normalized = normalize_device_name(device_name)
    logger.info(f"Adding {len(preset_items)} standard inventory items to Device '{device_name}' using preset '{inventory_preset}'")
    
    # STEP 3: LOOKUP DEVICE
    try:
        devices = client.dcim.devices.filter(name=device_name)
        if not devices:
            all_devices = client.dcim.devices.all()
            devices = [d for d in all_devices if normalize_device_name(
                d.get('name') if isinstance(d, dict) else d.name
            ) == device_name_normalized]
        
        if not devices:
            raise NotFoundError(f"Device '{device_name}' not found")
        
        device = devices[0]
        device_id = device.get('id') if isinstance(device, dict) else device.id
        device_display = device.get('display', device_name) if isinstance(device, dict) else getattr(device, 'display', device_name)
        
    except Exception as e:
        raise NotFoundError(f"Could not find device '{device_name}': {e}")
    
    # STEP 4: BULK CREATE INVENTORY ITEMS
    created_items = []
    failed_items = []
    skipped_items = []
    
    for item_spec in preset_items:
        try:
            # Check if item already exists
            existing_items = client.dcim.inventory_items.filter(
                device_id=device_id,
                name=item_spec["name"]
            )
            
            if existing_items:
                skipped_items.append({
                    "name": item_spec["name"],
                    "reason": "Item already exists"
                })
                logger.info(f"Skipping existing item: {item_spec['name']}")
                continue
            
            # Create inventory item with validated component_type
            validated_component_type = None
            if item_spec.get("component_type"):
                validated_component_type = validate_component_type(item_spec.get("component_type"))
                
            create_payload = {
                "device": device_id,
                "name": item_spec["name"],
                "description": item_spec.get("description", ""),
                "part_id": item_spec.get("part_id")
            }
            
            # Add validated component_type if available
            if validated_component_type is not None:
                create_payload["component_type"] = validated_component_type
            
            # Remove None values
            create_payload = {k: v for k, v in create_payload.items() if v is not None}
            
            new_item = client.dcim.inventory_items.create(confirm=confirm, **create_payload)
            
            item_id = new_item.get('id') if isinstance(new_item, dict) else new_item.id
            item_name = new_item.get('name') if isinstance(new_item, dict) else new_item.name
            
            created_items.append({
                "id": item_id,
                "name": item_name,
                "component_type": create_payload.get("component_type"),
                "description": create_payload.get("description")
            })
            
            logger.info(f"Created inventory item: {item_name} (ID: {item_id})")
            
        except Exception as e:
            failed_items.append({
                "name": item_spec["name"],
                "error": str(e)
            })
            logger.error(f"Failed to create inventory item '{item_spec['name']}': {e}")
    
    # STEP 5: RETURN RESULTS
    total_attempted = len(preset_items)
    total_created = len(created_items)
    total_failed = len(failed_items)
    total_skipped = len(skipped_items)
    
    success = total_failed == 0
    
    return {
        "success": success,
        "message": f"Bulk inventory operation completed. Created: {total_created}, Skipped: {total_skipped}, Failed: {total_failed}",
        "data": {
            "device_name": device_name,
            "device_display": device_display,
            "device_id": device_id,
            "inventory_preset": inventory_preset,
            "summary": {
                "total_attempted": total_attempted,
                "total_created": total_created,
                "total_skipped": total_skipped,
                "total_failed": total_failed
            },
            "created_items": created_items,
            "skipped_items": skipped_items,
            "failed_items": failed_items
        }
    }