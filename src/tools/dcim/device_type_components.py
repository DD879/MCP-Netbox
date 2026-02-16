"""
Device Type Component Templates Management Tools

This module provides enterprise-grade tools for managing NetBox Device Type component templates.
These tools enable complete standardization of device infrastructure by defining the physical
and logical components that should be present on all devices of a specific type.

Component templates supported:
- Interface Templates: Network interfaces (ethernet, fiber, etc.)
- Console Port Templates: Serial console ports
- Power Port Templates: Power inlet ports (PSUs)
- Console Server Port Templates: Out-of-band serial management ports
- Power Outlet Templates: Power outlet ports (PDUs)
- Front Port Templates: Physical front-facing ports (patch panels)
- Rear Port Templates: Physical rear-facing ports
- Device Bay Templates: Child device bays (blade chassis)
- Module Bay Templates: Modular component bays (line cards)
"""

from src.registry import mcp_tool
from src.client import NetBoxClient
from src.exceptions import (
    NetBoxValidationError as ValidationError, 
    NetBoxNotFoundError as NotFoundError, 
    NetBoxConflictError as ConflictError
)
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


# Parameter validation functions
def validate_interface_type(interface_type: str) -> None:
    """Validate interface type parameter."""
    valid_types = [
        "1000base-t", "1000base-x-gbic", "1000base-x-sfp", "10gbase-t", "10gbase-cx4",
        "10gbase-x-sfpp", "10gbase-x-xfp", "10gbase-x-x2", "25gbase-x-sfp28", 
        "40gbase-x-qsfpp", "50gbase-x-sfp56", "100gbase-x-cfp", "100gbase-x-cfp2",
        "100gbase-x-cfp4", "100gbase-x-cxp", "100gbase-x-qsfp28", "200gbase-x-cfp2",
        "200gbase-x-qsfp56", "400gbase-x-qsfp112", "400gbase-x-osfp", "other"
    ]
    if interface_type not in valid_types:
        raise ValidationError(f"Invalid interface type '{interface_type}'. Valid types: {', '.join(valid_types[:10])}...")


def validate_power_draw(power_draw: int, field_name: str) -> None:
    """Validate power draw values (watts)."""
    if power_draw is not None:
        if not isinstance(power_draw, int) or power_draw < 0 or power_draw > 10000:
            raise ValidationError(f"{field_name} must be a positive integer between 0 and 10000 watts, got: {power_draw}")


def validate_port_positions(positions: int) -> None:
    """Validate port positions parameter."""
    if not isinstance(positions, int) or positions < 1 or positions > 144:
        raise ValidationError(f"Port positions must be an integer between 1 and 144, got: {positions}")


def validate_rear_port_position(position: int) -> None:
    """Validate rear port position parameter."""
    if not isinstance(position, int) or position < 1 or position > 144:
        raise ValidationError(f"Rear port position must be an integer between 1 and 144, got: {position}")


def validate_console_port_type(port_type: str) -> None:
    """Validate console port type parameter."""
    valid_types = ["de-9", "db-25", "rj-11", "rj-12", "rj-45", "mini-din-8", "usb-a", "usb-b", "usb-c", "usb-mini-a", "usb-mini-b", "usb-micro-a", "usb-micro-b", "other"]
    if port_type not in valid_types:
        raise ValidationError(f"Invalid console port type '{port_type}'. Valid types: {', '.join(valid_types)}")


def validate_power_port_type(port_type: str) -> None:
    """Validate power port type parameter."""
    valid_types = [
        "iec-60320-c6", "iec-60320-c8", "iec-60320-c14", "iec-60320-c16", "iec-60320-c20",
        "iec-60309-p-n-e-4h", "iec-60309-p-n-e-6h", "iec-60309-p-n-e-9h", "iec-60309-2p-e-4h",
        "iec-60309-2p-e-6h", "iec-60309-2p-e-9h", "iec-60309-3p-e-4h", "iec-60309-3p-e-6h",
        "iec-60309-3p-e-9h", "iec-60309-3p-n-e-4h", "iec-60309-3p-n-e-6h", "iec-60309-3p-n-e-9h",
        "nema-1-15p", "nema-5-15p", "nema-5-20p", "nema-5-30p", "nema-5-50p", "nema-6-15p", 
        "nema-6-20p", "nema-6-30p", "nema-6-50p", "nema-10-30p", "nema-10-50p", "nema-14-20p",
        "nema-14-30p", "nema-14-50p", "nema-14-60p", "nema-15-15p", "nema-15-20p", "nema-15-30p",
        "nema-15-50p", "nema-15-60p", "nema-l1-15p", "nema-l5-15p", "nema-l5-20p", "nema-l5-30p",
        "nema-l5-50p", "nema-l6-15p", "nema-l6-20p", "nema-l6-30p", "nema-l6-50p", "nema-l10-30p",
        "nema-l14-20p", "nema-l14-30p", "nema-l15-20p", "nema-l15-30p", "nema-l21-20p", "nema-l21-30p",
        "cs6361c", "cs6365c", "cs8165c", "cs8265c", "cs8365c", "cs8465c", "ita-e", "ita-f", "ita-g",
        "ita-h", "ita-i", "ita-j", "ita-k", "ita-l", "ita-m", "ita-n", "ita-o", "usb-a", "usb-micro-b", 
        "usb-c", "dc-terminal", "hdot-cx", "saf-d-grid", "neutrik-powercon-20a", "neutrik-powercon-32a",
        "neutrik-powercon-true1", "neutrik-powercon-true1-top", "ubiquiti-smartpower", "hardwired", "other"
    ]
    if port_type not in valid_types:
        raise ValidationError(f"Invalid power port type '{port_type}'. Valid types include: iec-60320-c14, nema-5-15p, etc.")


def validate_physical_port_type(port_type: str, context: str = "port") -> None:
    """Validate physical port type parameter for front/rear ports."""
    valid_types = [
        "8p8c", "8p6c", "8p4c", "8p2c", "6p6c", "6p4c", "6p2c", "4p4c", "4p2c", "gg45",
        "tera-4p", "tera-2p", "tera-1p", "110-punch", "bnc", "f", "n", "mrj21", "fc", "lc",
        "lc-pc", "lc-upc", "lc-apc", "lsh", "lsh-pc", "lsh-upc", "lsh-apc", "mpo", "mtrj",
        "sc", "sc-pc", "sc-upc", "sc-apc", "st", "cs", "sn", "sma-905", "sma-906", "urm-p2",
        "urm-p4", "urm-p8", "splice", "other"
    ]
    if port_type not in valid_types:
        raise ValidationError(f"Invalid {context} type '{port_type}'. Valid types include: lc, sc, mpo, fc, etc.")


def validate_feed_leg(feed_leg: str) -> None:
    """Validate feed leg parameter."""
    valid_legs = ["A", "B", "C"]
    if feed_leg not in valid_legs:
        raise ValidationError(f"Invalid feed leg '{feed_leg}'. Valid options: {', '.join(valid_legs)}")


def validate_power_outlet_type(outlet_type: str) -> None:
    """Validate power outlet type parameter."""
    valid_types = [
        "iec-60320-c5", "iec-60320-c7", "iec-60320-c13", "iec-60320-c15", "iec-60320-c19", "iec-60320-c21",
        "iec-60309-p-n-e-4h", "iec-60309-p-n-e-6h", "iec-60309-p-n-e-9h", "iec-60309-2p-e-4h", "iec-60309-2p-e-6h",
        "iec-60309-2p-e-9h", "iec-60309-3p-e-4h", "iec-60309-3p-e-6h", "iec-60309-3p-e-9h", "iec-60309-3p-n-e-4h",
        "iec-60309-3p-n-e-6h", "iec-60309-3p-n-e-9h", "iec-60906-1", "nbr-14136-10a", "nbr-14136-20a",
        "nema-1-15r", "nema-5-15r", "nema-5-20r", "nema-5-30r", "nema-5-50r", "nema-6-15r", "nema-6-20r",
        "nema-6-30r", "nema-6-50r", "nema-10-30r", "nema-10-50r", "nema-14-20r", "nema-14-30r", "nema-14-50r",
        "nema-14-60r", "nema-15-15r", "nema-15-20r", "nema-15-30r", "nema-15-50r", "nema-15-60r",
        "nema-l1-15r", "nema-l5-15r", "nema-l5-20r", "nema-l5-30r", "nema-l5-50r", "nema-l6-15r", "nema-l6-20r",
        "nema-l6-30r", "nema-l6-50r", "nema-l10-30r", "nema-l14-20r", "nema-l14-30r", "nema-l14-50r",
        "nema-l14-60r", "nema-l15-20r", "nema-l15-30r", "nema-l15-50r", "nema-l15-60r", "nema-l21-20r",
        "nema-l21-30r", "nema-l22-20r", "nema-l22-30r", "cs6360c", "cs6364c", "cs8164c", "cs8264c", "cs8364c",
        "cs8464c", "ita-e", "ita-f", "ita-g", "ita-h", "ita-i", "ita-j", "ita-k", "ita-l", "ita-m", "ita-n",
        "ita-o", "ita-multistandard", "usb-a", "usb-micro-b", "usb-c", "molex-micro-fit-1x2", "molex-micro-fit-2x2",
        "molex-micro-fit-2x4", "dc-terminal", "eaton-c39", "hdot-cx", "saf-d-grid", "neutrik-powercon-20a",
        "neutrik-powercon-32a", "neutrik-powercon-true1", "neutrik-powercon-true1-top", "ubiquiti-smartpower",
        "hardwired", "other"
    ]
    if outlet_type not in valid_types:
        raise ValidationError(f"Invalid power outlet type '{outlet_type}'. Valid types include: iec-60320-c13, nema-5-15r, etc.")


@mcp_tool(category="dcim")
def netbox_add_interface_template_to_device_type(
    client: NetBoxClient,
    device_type_model: str,
    name: str,
    type: str,
    description: Optional[str] = None,
    mgmt_only: bool = False,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Add a new Interface Template to an existing Device Type.

    This tool defines a standardized network port for all devices of a specific model.
    Interface templates are essential for network device standardization and automated
    provisioning workflows.

    Args:
        device_type_model (str): The model name of the Device Type (e.g., "Cisco C9300-24T").
        name (str): The name of the interface (e.g., "GigabitEthernet0/1", "eth0").
        type (str): The physical type of the interface. Valid types include:
            - "1000base-t": Gigabit Ethernet over copper
            - "10gbase-x-sfpp": 10 Gigabit Ethernet SFP+
            - "25gbase-x-sfp28": 25 Gigabit Ethernet SFP28
            - "40gbase-x-qsfpp": 40 Gigabit Ethernet QSFP+
            - "100gbase-x-qsfp28": 100 Gigabit Ethernet QSFP28
        description (str, optional): A description for the interface template.
        mgmt_only (bool): Whether this interface is management-only. Defaults to False.
        client (NetBoxClient): The active NetBox client.
        confirm (bool): Must be True to execute the operation.

    Returns:
        dict: A dictionary containing the operation result and created template data.
    
    Raises:
        ValidationError: If required parameters are missing or invalid.
        ConflictError: If an interface template with the same name already exists.
        NotFoundError: If the specified Device Type cannot be found.
        
    Example:
        >>> # Add a management interface template
        >>> result = netbox_add_interface_template_to_device_type(
        ...     device_type_model="Cisco C9300-24T",
        ...     name="Management1",
        ...     type="1000base-t",
        ...     description="Management interface",
        ...     mgmt_only=True,
        ...     confirm=True
        ... )
        
        >>> # Add multiple data interfaces for a switch
        >>> for port in range(1, 25):
        ...     result = netbox_add_interface_template_to_device_type(
        ...         device_type_model="Cisco C9300-24T",
        ...         name=f"GigabitEthernet1/0/{port}",
        ...         type="1000base-t",
        ...         description=f"Data port {port}",
        ...         confirm=True
        ...     )
    """
    if not confirm:
        return {
            "success": True,
        "dry_run": True,
            "message": "DRY RUN: Interface Template would be created. Set confirm=True to execute.",
            "would_create": {
                "device_type_model": device_type_model,
                "interface_name": name,
                "interface_type": type,
                "description": description,
                "mgmt_only": mgmt_only
            }
        }

    # STEP 0: PARAMETER VALIDATION
    validate_interface_type(type)
    
    if not name or not name.strip():
        raise ValidationError("Interface name cannot be empty")
    
    if not device_type_model or not device_type_model.strip():
        raise ValidationError("Device Type model cannot be empty")

    # STEP 1: ULTRATHINK OPTIMIZATION - Find Device Type with expand parameters and fallback strategies
    logger.info(f"Looking up Device Type with model: {device_type_model}")

    try:
        # ULTRATHINK FIX 1: Expand Parameters - Get manufacturer info in single call
        device_types = list(client.dcim.device_types.filter(
            model=device_type_model,
            expand=["manufacturer"]
        ))

        # ULTRATHINK FIX 4: Slug-Based Fallback - Try slug match if exact model fails
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
            raise NotFoundError(f"Device Type with model '{device_type_model}' not found.")

        # ULTRATHINK FIX 3: Defensive Dict/Object Handling
        device_type = device_types[0] if device_types else None
        if not device_type:
            raise NotFoundError(f"Device Type with model '{device_type_model}' not found.")

        device_data = device_type if isinstance(device_type, dict) else device_type.serialize()
        device_type_id = device_data.get('id')
        device_type_display = device_data.get('display', device_type_model)

        logger.info(f"Found Device Type: {device_type_display} (ID: {device_type_id})")

    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Error looking up Device Type: {e}")
        raise NotFoundError(f"Could not find Device Type '{device_type_model}': {e}")

    # STEP 2: DEFENSIVE READ - Check for conflicts (does this template already exist?)
    logger.info(f"Checking for existing Interface Template '{name}' on Device Type '{device_type_model}'")
    
    try:
        existing_templates = client.dcim.interface_templates.filter(
            device_type_id=device_type_id,
            name=name,
            no_cache=True  # Force live check for accurate conflict detection
        )
        
        if existing_templates:
            existing_template = existing_templates[0]
            logger.warning(f"Interface Template conflict detected: '{name}' already exists for Device Type '{device_type_model}' (ID: {existing_template.id})")
            raise ConflictError(
                resource_type="Interface Template",
                identifier=f"{name} for Device Type {device_type_model}",
                existing_id=existing_template.id
            )
            
    except ConflictError:
        raise
    except Exception as e:
        logger.warning(f"Could not check for existing templates: {e}")

    # STEP 3: VALIDATE PARAMETERS - Check interface type is valid
    if not type:
        raise ValidationError("Interface type is required and cannot be empty.")
    
    if not name:
        raise ValidationError("Interface name is required and cannot be empty.")

    # STEP 4: WRITE - Create the Interface Template
    template_payload = {
        "device_type": device_type_id,
        "name": name,
        "type": type,
        "description": description or "",
        "mgmt_only": mgmt_only
    }
    
    try:
        logger.info(f"Creating Interface Template '{name}' for Device Type '{device_type_model}'...")
        new_template = client.dcim.interface_templates.create(confirm=confirm, **template_payload)
        template_id = new_template.get('id') if isinstance(new_template, dict) else new_template.id
        logger.info(f"Successfully created Interface Template with ID: {template_id}")
        
    except Exception as e:
        logger.error(f"Failed to create Interface Template in NetBox: {e}")
        raise ValidationError(f"NetBox API error during Interface Template creation: {e}")

    # Cache invalidation handled by NetBox client automatically

    return {
        "success": True,
        "message": f"Interface Template '{new_template.get('name') if isinstance(new_template, dict) else new_template.name}' successfully added to Device Type '{device_type_model}'.",
        "data": {
            "template_id": template_id,
            "template_name": new_template.get('name') if isinstance(new_template, dict) else new_template.name,
            "template_type": new_template.get('type') if isinstance(new_template, dict) else new_template.type,
            "device_type_model": device_type_model,
            "device_type_id": device_type_id,
            "description": new_template.get('description') if isinstance(new_template, dict) else new_template.description,
            "mgmt_only": new_template.get('mgmt_only') if isinstance(new_template, dict) else new_template.mgmt_only,
        }
    }


@mcp_tool(category="dcim")
def netbox_add_console_port_template_to_device_type(
    client: NetBoxClient,
    device_type_model: str,
    name: str,
    type: str = "rj-45",
    description: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Add a new Console Port Template to an existing Device Type.

    This tool defines a standardized serial console port for all devices of a specific model.
    Console port templates are essential for out-of-band management and device access.

    Args:
        device_type_model (str): The model name of the Device Type.
        name (str): The name of the console port (e.g., "Console", "CON1").
        type (str): The physical type of the console port. Defaults to "rj-45".
        description (str, optional): A description for the console port template.
        client (NetBoxClient): The active NetBox client.
        confirm (bool): Must be True to execute the operation.

    Returns:
        dict: A dictionary containing the operation result and created template data.
    """
    if not confirm:
        return {
            "success": True,
        "dry_run": True, 
            "message": "DRY RUN: Console Port Template would be created. Set confirm=True to execute.",
            "would_create": {
                "device_type_model": device_type_model,
                "console_port_name": name,
                "console_port_type": type,
                "description": description
            }
        }

    # ULTRATHINK OPTIMIZATION - Enhanced Device Type lookup with expand parameters
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

        if not device_types:
            raise NotFoundError(f"Device Type with model '{device_type_model}' not found.")

        # ULTRATHINK FIX 3: Defensive Dict/Object Handling
        device_type = device_types[0] if device_types else None
        if not device_type:
            raise NotFoundError(f"Device Type with model '{device_type_model}' not found.")

        device_data = device_type if isinstance(device_type, dict) else device_type.serialize()
        device_type_id = device_data.get('id')
    except NotFoundError:
        raise
    except Exception as e:
        raise NotFoundError(f"Could not find Device Type '{device_type_model}': {e}")

    # Check for conflicts
    try:
        existing_templates = client.dcim.console_port_templates.filter(
            device_type_id=device_type_id,
            name=name,
            no_cache=True
        )
        if existing_templates:
            existing_template = existing_templates[0]
            logger.warning(f"Console Port Template conflict detected: '{name}' already exists for Device Type '{device_type_model}' (ID: {existing_template.id})")
            raise ConflictError(
                resource_type="Console Port Template",
                identifier=f"{name} for Device Type {device_type_model}",
                existing_id=existing_template.id
            )
    except ConflictError:
        raise
    except Exception as e:
        logger.warning(f"Could not check for existing console port templates: {e}")

    # Create the template
    template_payload = {
        "device_type": device_type_id,
        "name": name,
        "type": type,
        "description": description or ""
    }
    
    try:
        new_template = client.dcim.console_port_templates.create(confirm=confirm, **template_payload)
        template_id = new_template.get('id') if isinstance(new_template, dict) else new_template.id
    except Exception as e:
        raise ValidationError(f"NetBox API error during Console Port Template creation: {e}")

    return {
        "success": True,
        "message": f"Console Port Template '{new_template.get('name') if isinstance(new_template, dict) else new_template.name}' successfully added to Device Type '{device_type_model}'.",
        "data": {
            "template_id": template_id,
            "template_name": new_template.get('name') if isinstance(new_template, dict) else new_template.name,
            "template_type": new_template.get('type') if isinstance(new_template, dict) else new_template.type,
            "device_type_model": device_type_model,
            "device_type_id": device_type_id,
            "description": new_template.get('description') if isinstance(new_template, dict) else new_template.description,
        }
    }


@mcp_tool(category="dcim")
def netbox_add_power_port_template_to_device_type(
    client: NetBoxClient,
    device_type_model: str,
    name: str,
    type: str = "iec-60320-c14",
    maximum_draw: Optional[int] = None,
    allocated_draw: Optional[int] = None,
    description: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Add a new Power Port Template to an existing Device Type.

    This tool defines a standardized power inlet port for all devices of a specific model.
    Power port templates are essential for power infrastructure planning and management.

    Args:
        device_type_model (str): The model name of the Device Type.
        name (str): The name of the power port (e.g., "PSU1", "Power").
        type (str): The physical type of the power port. Common types:
            - "iec-60320-c14": Standard server power inlet (default)
            - "iec-60320-c20": High-current server power inlet  
            - "nema-5-15p": US standard 110V plug
            - "nema-l6-20p": US locking 240V plug
            - "iec-60309-3p-n-e-6h": Industrial 3-phase connector
        maximum_draw (int, optional): Maximum power draw in watts (0-10000).
        allocated_draw (int, optional): Allocated power draw in watts (0-10000).
        description (str, optional): A description for the power port template.
        client (NetBoxClient): The active NetBox client.
        confirm (bool): Must be True to execute the operation.

    Returns:
        dict: A dictionary containing the operation result and created template data.
        
    Example:
        >>> # Add dual power supplies for a server
        >>> for psu in ["PSU1", "PSU2"]:
        ...     result = netbox_add_power_port_template_to_device_type(
        ...         device_type_model="Dell PowerEdge R640",
        ...         name=psu,
        ...         type="iec-60320-c14",
        ...         maximum_draw=750,
        ...         allocated_draw=500,
        ...         description=f"Primary power supply {psu}",
        ...         confirm=True
        ...     )
    """
    if not confirm:
        return {
            "success": True,
        "dry_run": True,
            "message": "DRY RUN: Power Port Template would be created. Set confirm=True to execute.",
            "would_create": {
                "device_type_model": device_type_model,
                "power_port_name": name,
                "power_port_type": type,
                "maximum_draw": maximum_draw,
                "allocated_draw": allocated_draw,
                "description": description
            }
        }

    # PARAMETER VALIDATION
    validate_power_port_type(type)
    validate_power_draw(maximum_draw, "Maximum draw")
    validate_power_draw(allocated_draw, "Allocated draw")
    
    if not name or not name.strip():
        raise ValidationError("Power port name cannot be empty")

    # ULTRATHINK OPTIMIZATION - Enhanced Device Type lookup with expand parameters
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

        if not device_types:
            raise NotFoundError(f"Device Type with model '{device_type_model}' not found.")

        # ULTRATHINK FIX 3: Defensive Dict/Object Handling
        device_type = device_types[0] if device_types else None
        if not device_type:
            raise NotFoundError(f"Device Type with model '{device_type_model}' not found.")

        device_data = device_type if isinstance(device_type, dict) else device_type.serialize()
        device_type_id = device_data.get('id')
    except NotFoundError:
        raise
    except Exception as e:
        raise NotFoundError(f"Could not find Device Type '{device_type_model}': {e}")

    # Check for conflicts
    try:
        existing_templates = client.dcim.power_port_templates.filter(
            device_type_id=device_type_id,
            name=name,
            no_cache=True
        )
        if existing_templates:
            existing_template = existing_templates[0]
            logger.warning(f"Power Port Template conflict detected: '{name}' already exists for Device Type '{device_type_model}' (ID: {existing_template.id})")
            raise ConflictError(
                resource_type="Power Port Template",
                identifier=f"{name} for Device Type {device_type_model}",
                existing_id=existing_template.id
            )
    except ConflictError:
        raise
    except Exception as e:
        logger.warning(f"Could not check for existing power port templates: {e}")

    # Create the template
    template_payload = {
        "device_type": device_type_id,
        "name": name,
        "type": type,
        "description": description or ""
    }
    
    # Add optional power parameters if provided
    if maximum_draw is not None:
        template_payload["maximum_draw"] = maximum_draw
    if allocated_draw is not None:
        template_payload["allocated_draw"] = allocated_draw
    
    try:
        new_template = client.dcim.power_port_templates.create(confirm=confirm, **template_payload)
        template_id = new_template.get('id') if isinstance(new_template, dict) else new_template.id
    except Exception as e:
        raise ValidationError(f"NetBox API error during Power Port Template creation: {e}")

    return {
        "success": True,
        "message": f"Power Port Template '{new_template.get('name') if isinstance(new_template, dict) else new_template.name}' successfully added to Device Type '{device_type_model}'.",
        "data": {
            "template_id": template_id,
            "template_name": new_template.get('name') if isinstance(new_template, dict) else new_template.name,
            "template_type": new_template.get('type') if isinstance(new_template, dict) else new_template.type,
            "device_type_model": device_type_model,
            "device_type_id": device_type_id,
            "description": new_template.get('description') if isinstance(new_template, dict) else new_template.description,
            "maximum_draw": getattr(new_template, 'maximum_draw', None),
            "allocated_draw": getattr(new_template, 'allocated_draw', None),
        }
    }


@mcp_tool(category="dcim")
def netbox_add_console_server_port_template_to_device_type(
    client: NetBoxClient,
    device_type_model: str,
    name: str,
    type: str = "rj-45",
    description: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Add a new Console Server Port Template to an existing Device Type.

    This tool defines a standardized console server port for all devices of a specific model.
    Console server port templates are used for out-of-band serial management connections.

    Args:
        device_type_model (str): The model name of the Device Type.
        name (str): The name of the console server port (e.g., "ttyS1", "Serial1").
        type (str): The physical type of the console server port. Defaults to "rj-45".
        description (str, optional): A description for the console server port template.
        client (NetBoxClient): The active NetBox client.
        confirm (bool): Must be True to execute the operation.

    Returns:
        dict: A dictionary containing the operation result and created template data.
    """
    if not confirm:
        return {
            "success": True,
        "dry_run": True,
            "message": "DRY RUN: Console Server Port Template would be created. Set confirm=True to execute.",
            "would_create": {
                "device_type_model": device_type_model,
                "console_server_port_name": name,
                "console_server_port_type": type,
                "description": description
            }
        }

    # ULTRATHINK OPTIMIZATION - Enhanced Device Type lookup with expand parameters
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

        if not device_types:
            raise NotFoundError(f"Device Type with model '{device_type_model}' not found.")

        # ULTRATHINK FIX 3: Defensive Dict/Object Handling
        device_type = device_types[0] if device_types else None
        if not device_type:
            raise NotFoundError(f"Device Type with model '{device_type_model}' not found.")

        device_data = device_type if isinstance(device_type, dict) else device_type.serialize()
        device_type_id = device_data.get('id')
    except NotFoundError:
        raise
    except Exception as e:
        raise NotFoundError(f"Could not find Device Type '{device_type_model}': {e}")

    # Check for conflicts
    try:
        existing_templates = client.dcim.console_server_port_templates.filter(
            device_type_id=device_type_id,
            name=name,
            no_cache=True
        )
        if existing_templates:
            existing_template = existing_templates[0]
            logger.warning(f"Console Server Port Template conflict detected: '{name}' already exists for Device Type '{device_type_model}' (ID: {existing_template.id})")
            raise ConflictError(
                resource_type="Console Server Port Template",
                identifier=f"{name} for Device Type {device_type_model}",
                existing_id=existing_template.id
            )
    except ConflictError:
        raise
    except Exception as e:
        logger.warning(f"Could not check for existing console server port templates: {e}")

    # Create the template
    template_payload = {
        "device_type": device_type_id,
        "name": name,
        "type": type,
        "description": description or ""
    }
    
    try:
        new_template = client.dcim.console_server_port_templates.create(confirm=confirm, **template_payload)
        template_id = new_template.get('id') if isinstance(new_template, dict) else new_template.id
    except Exception as e:
        raise ValidationError(f"NetBox API error during Console Server Port Template creation: {e}")

    return {
        "success": True,
        "message": f"Console Server Port Template '{new_template.get('name') if isinstance(new_template, dict) else new_template.name}' successfully added to Device Type '{device_type_model}'.",
        "data": {
            "template_id": template_id,
            "template_name": new_template.get('name') if isinstance(new_template, dict) else new_template.name,
            "template_type": new_template.get('type') if isinstance(new_template, dict) else new_template.type,
            "device_type_model": device_type_model,
            "device_type_id": device_type_id,
            "description": new_template.get('description') if isinstance(new_template, dict) else new_template.description,
        }
    }


@mcp_tool(category="dcim")
def netbox_add_power_outlet_template_to_device_type(
    client: NetBoxClient,
    device_type_model: str,
    name: str,
    type: str = "iec-60320-c13",
    power_port_template: Optional[str] = None,
    feed_leg: Optional[str] = None,
    description: Optional[str] = None,
    confirm: bool = False  
) -> Dict[str, Any]:
    """
    Add a new Power Outlet Template to an existing Device Type.

    This tool defines a standardized power outlet port for all devices of a specific model.
    Power outlet templates are essential for PDUs (Power Distribution Units), UPS systems,
    and power distribution infrastructure, enabling comprehensive power chain documentation
    from source to load.

    Power outlet templates define the physical power receptacles that deliver power to
    connected equipment. These templates are crucial for:
    - PDU outlet modeling and capacity planning
    - UPS output port documentation
    - Power strip and distribution panel configuration
    - Electrical load balancing across feed legs
    - Power consumption tracking and billing

    Args:
        device_type_model (str): The model name of the Device Type (e.g., "APC AP7922", "Raritan PX3-5190R").
        name (str): The name of the power outlet (e.g., "Outlet1", "C13-01", "Bank-A-01").
        type (str): The physical type of the power outlet. Common types:
            - "iec-60320-c13": Standard server power outlet (default)
            - "iec-60320-c19": High-current server power outlet
            - "nema-5-15r": US standard 110V receptacle
            - "nema-5-20r": US 20A 110V receptacle
            - "nema-l6-20r": US locking 240V receptacle
            - "iec-60309-3p-n-e-6h": Industrial 3-phase receptacle
        power_port_template (str, optional): Name of associated power port template.
            This links the outlet to its power source within the device.
        feed_leg (str, optional): Feed leg identifier for load balancing. Valid options:
            - "A": Phase A/Leg A
            - "B": Phase B/Leg B  
            - "C": Phase C/Leg C
        description (str, optional): A description for the power outlet template.
        client (NetBoxClient): The active NetBox client.
        confirm (bool): Must be True to execute the operation.

    Returns:
        dict: A dictionary containing the operation result and created template data.
        
    Raises:
        ValidationError: If required parameters are missing or invalid.
        ConflictError: If a power outlet template with the same name already exists.
        NotFoundError: If the specified Device Type or power port template cannot be found.
        
    Example:
        >>> # Create a 24-port PDU with C13 outlets distributed across 3 feed legs
        >>> # First, create the power port templates for input feeds
        >>> for leg in ["A", "B", "C"]:
        ...     result = netbox_add_power_port_template_to_device_type(
        ...         device_type_model="APC AP7922",
        ...         name=f"Input-{leg}",
        ...         type="iec-60320-c20",
        ...         maximum_draw=3680,  # 16A @ 230V
        ...         description=f"Input power feed {leg}",
        ...         confirm=True
        ...     )
        
        >>> # Then create 24 C13 outlets, 8 per feed leg for load balancing
        >>> for outlet_num in range(1, 25):
        ...     # Distribute outlets across feed legs: A (1-8), B (9-16), C (17-24)
        ...     if outlet_num <= 8:
        ...         feed = "A"
        ...         port_template = "Input-A"
        ...     elif outlet_num <= 16:
        ...         feed = "B"
        ...         port_template = "Input-B"
        ...     else:
        ...         feed = "C"
        ...         port_template = "Input-C"
        ...
        ...     result = netbox_add_power_outlet_template_to_device_type(
        ...         device_type_model="APC AP7922",
        ...         name=f"Outlet-{outlet_num:02d}",
        ...         type="iec-60320-c13",
        ...         power_port_template=port_template,
        ...         feed_leg=feed,
        ...         description=f"C13 outlet {outlet_num} on feed {feed}",
        ...         confirm=True
        ...     )
        
        >>> # Create UPS outlets with different power ratings
        >>> # High-power outlets for servers
        >>> for outlet_num in range(1, 5):
        ...     result = netbox_add_power_outlet_template_to_device_type(
        ...         device_type_model="APC Smart-UPS SRT 6000VA",
        ...         name=f"Server-Outlet-{outlet_num}",
        ...         type="iec-60320-c19",
        ...         power_port_template="UPS-Output",
        ...         description=f"High-current server outlet {outlet_num}",
        ...         confirm=True
        ...     )
        
        >>> # Standard outlets for network equipment
        >>> for outlet_num in range(1, 9):
        ...     result = netbox_add_power_outlet_template_to_device_type(
        ...         device_type_model="APC Smart-UPS SRT 6000VA",
        ...         name=f"Network-Outlet-{outlet_num}",
        ...         type="iec-60320-c13",
        ...         power_port_template="UPS-Output",
        ...         description=f"Standard network equipment outlet {outlet_num}",
        ...         confirm=True
        ...     )
        
        >>> # Create office power strip outlets
        >>> for outlet_num in range(1, 13):
        ...     result = netbox_add_power_outlet_template_to_device_type(
        ...         device_type_model="Tripp Lite RS-1215",
        ...         name=f"Desktop-{outlet_num:02d}",
        ...         type="nema-5-15r",
        ...         power_port_template="AC-Input",
        ...         description=f"Desktop outlet {outlet_num}",
        ...         confirm=True
        ...     )
        
        >>> # Create industrial 3-phase distribution outlets
        >>> for outlet_num in range(1, 7):
        ...     result = netbox_add_power_outlet_template_to_device_type(
        ...         device_type_model="Square D I-Line Panelboard",
        ...         name=f"3Phase-{outlet_num}",
        ...         type="iec-60309-3p-n-e-6h",
        ...         power_port_template="Main-Feed",
        ...         description=f"3-phase industrial outlet {outlet_num}",
        ...         confirm=True
        ...     )
    """
    if not confirm:
        return {
            "success": True,
        "dry_run": True,
            "message": "DRY RUN: Power Outlet Template would be created. Set confirm=True to execute.",
            "would_create": {
                "device_type_model": device_type_model,
                "power_outlet_name": name,
                "power_outlet_type": type,
                "power_port_template": power_port_template,
                "feed_leg": feed_leg,
                "description": description
            }
        }

    # STEP 0: PARAMETER VALIDATION
    validate_power_outlet_type(type)
    
    if feed_leg is not None:
        validate_feed_leg(feed_leg)
    
    if not name or not name.strip():
        raise ValidationError("Power outlet name cannot be empty")
    
    if not device_type_model or not device_type_model.strip():
        raise ValidationError("Device Type model cannot be empty")

    # STEP 1: ULTRATHINK OPTIMIZATION - Find Device Type with expand parameters and fallback strategies
    logger.info(f"Looking up Device Type with model: {device_type_model}")

    try:
        # ULTRATHINK FIX 1: Expand Parameters - Get manufacturer info in single call
        device_types = list(client.dcim.device_types.filter(
            model=device_type_model,
            expand=["manufacturer"]
        ))

        # ULTRATHINK FIX 4: Slug-Based Fallback - Try slug match if exact model fails
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
            raise NotFoundError(f"Device Type with model '{device_type_model}' not found.")

        # ULTRATHINK FIX 3: Defensive Dict/Object Handling
        device_type = device_types[0] if device_types else None
        if not device_type:
            raise NotFoundError(f"Device Type with model '{device_type_model}' not found.")

        device_data = device_type if isinstance(device_type, dict) else device_type.serialize()
        device_type_id = device_data.get('id')
        device_type_display = device_data.get('display', device_type_model)

        logger.info(f"Found Device Type: {device_type_display} (ID: {device_type_id})")

    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Error looking up Device Type: {e}")
        raise NotFoundError(f"Could not find Device Type '{device_type_model}': {e}")

    # STEP 2: DEFENSIVE READ - Check for conflicts (does this template already exist?)
    logger.info(f"Checking for existing Power Outlet Template '{name}' on Device Type '{device_type_model}'")
    
    try:
        existing_templates = client.dcim.power_outlet_templates.filter(
            device_type_id=device_type_id,
            name=name,
            no_cache=True  # Force live check for accurate conflict detection
        )
        
        if existing_templates:
            existing_template = existing_templates[0]
            logger.warning(f"Power Outlet Template conflict detected: '{name}' already exists for Device Type '{device_type_model}' (ID: {existing_template.id})")
            raise ConflictError(
                resource_type="Power Outlet Template",
                identifier=f"{name} for Device Type {device_type_model}",
                existing_id=existing_template.id
            )
            
    except ConflictError:
        raise
    except Exception as e:
        logger.warning(f"Could not check for existing power outlet templates: {e}")

    # STEP 3: VALIDATE - Resolve power port template if specified
    power_port_template_id = None
    if power_port_template:
        logger.info(f"Looking up Power Port Template '{power_port_template}' for Device Type '{device_type_model}'")
        
        try:
            power_port_templates = client.dcim.power_port_templates.filter(
                device_type_id=device_type_id,
                name=power_port_template
            )
            if power_port_templates:
                power_port_template_id = power_port_templates[0].id
                logger.info(f"Resolved power port template '{power_port_template}' to ID: {power_port_template_id}")
            else:
                logger.error(f"Power Port Template '{power_port_template}' not found for Device Type '{device_type_model}'")
                raise NotFoundError(f"Power Port Template '{power_port_template}' not found for Device Type '{device_type_model}'. Create the power port template first.")
        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error resolving power port template '{power_port_template}': {e}")
            raise ValidationError(f"Failed to resolve power port template '{power_port_template}': {e}")

    # STEP 4: VALIDATE PARAMETERS - Check required fields
    if not type:
        raise ValidationError("Power outlet type is required and cannot be empty.")
    
    if not name:
        raise ValidationError("Power outlet name is required and cannot be empty.")

    # STEP 5: WRITE - Create the Power Outlet Template
    template_payload = {
        "device_type": device_type_id,
        "name": name,
        "type": type,
        "description": description or ""
    }
    
    if power_port_template_id:
        template_payload["power_port"] = power_port_template_id
    if feed_leg:
        template_payload["feed_leg"] = feed_leg
    
    try:
        logger.info(f"Creating Power Outlet Template '{name}' for Device Type '{device_type_model}'...")
        new_template = client.dcim.power_outlet_templates.create(confirm=confirm, **template_payload)
        template_id = new_template.get('id') if isinstance(new_template, dict) else new_template.id
        logger.info(f"Successfully created Power Outlet Template with ID: {template_id}")
        
    except Exception as e:
        logger.error(f"Failed to create Power Outlet Template in NetBox: {e}")
        raise ValidationError(f"NetBox API error during Power Outlet Template creation: {e}")

    # Cache invalidation handled by NetBox client automatically

    return {
        "success": True,
        "message": f"Power Outlet Template '{new_template.get('name') if isinstance(new_template, dict) else new_template.name}' successfully added to Device Type '{device_type_model}'.",
        "data": {
            "template_id": template_id,
            "template_name": new_template.get('name') if isinstance(new_template, dict) else new_template.name,
            "template_type": new_template.get('type') if isinstance(new_template, dict) else new_template.type,
            "device_type_model": device_type_model,  
            "device_type_id": device_type_id,
            "description": new_template.get('description') if isinstance(new_template, dict) else new_template.description,
            "power_port_template": power_port_template,
            "feed_leg": feed_leg,
        }
    }


@mcp_tool(category="dcim")
def netbox_add_front_port_template_to_device_type(
    client: NetBoxClient,
    device_type_model: str,
    name: str,
    type: str,
    rear_port_template: str,
    rear_port_position: int = 1,
    description: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Add a new Front Port Template to an existing Device Type.

    This tool defines a standardized front-facing physical port for all devices of a specific model.
    Front port templates are essential for patch panels, fiber distribution equipment, and structured 
    cabling systems where front ports provide user-accessible connections that map to rear ports
    through internal pathways or splicing.

    Front ports represent the user-facing side of patch panels and distribution equipment, while
    rear ports represent the infrastructure/backbone side. The relationship between front and rear
    ports is defined by the rear_port_position parameter, which maps a front port to a specific
    position on a rear port (important for multi-position connectors like MPO).

    Args:
        device_type_model (str): The model name of the Device Type (e.g., "Panduit FP12-C").
        name (str): The name of the front port (e.g., "Port 1", "F01", "LC-01").
        type (str): The physical type of the front port. Valid types include:
            - "lc": Lucent Connector (duplex/single fiber)
            - "sc": Subscriber Connector (duplex/single fiber)
            - "fc": Fiber Channel connector
            - "st": Straight Tip connector
            - "mpo": Multi-fiber Push-On connector
            - "mtrj": MT-RJ small form factor connector
            - "8p8c": 8-position 8-contact (RJ45 for copper)
            - "bnc": Bayonet Neill-Concelman connector
            - "f": F-type coaxial connector
            - "splice": Fiber splice connection
        rear_port_template (str): Name of the associated rear port template that this front port
            connects to. The rear port template must exist before creating the front port.
        rear_port_position (int): Position on the rear port (1-144). For single-position rear ports,
            this is typically 1. For multi-position rear ports (like MPO), this specifies which
            position/strand this front port uses. Defaults to 1.
        description (str, optional): A description for the front port template.
        client (NetBoxClient): The active NetBox client.
        confirm (bool): Must be True to execute the operation.

    Returns:
        dict: A dictionary containing the operation result and created template data.
        
    Raises:
        ValidationError: If required parameters are missing or invalid.
        ConflictError: If a front port template with the same name already exists.
        NotFoundError: If the specified Device Type or rear port template cannot be found.
        
    Example:
        >>> # First create a rear port template for 24-fiber MPO backbone
        >>> rear_result = netbox_add_rear_port_template_to_device_type(
        ...     device_type_model="Panduit FP24-C",
        ...     name="MPO-1",
        ...     type="mpo",
        ...     positions=24,
        ...     description="24-fiber MPO backbone connection",
        ...     confirm=True
        ... )
        
        >>> # Then create 12 duplex LC front ports mapping to the MPO rear port
        >>> for port in range(1, 13):
        ...     # Each duplex LC port uses 2 positions on the MPO
        ...     rear_position = (port - 1) * 2 + 1
        ...     result = netbox_add_front_port_template_to_device_type(
        ...         device_type_model="Panduit FP24-C",
        ...         name=f"LC-{port:02d}",
        ...         type="lc",
        ...         rear_port_template="MPO-1",
        ...         rear_port_position=rear_position,
        ...         description=f"Duplex LC port {port}",
        ...         confirm=True
        ...     )
        
        >>> # Create front ports for copper patch panel
        >>> # First create rear port template
        >>> rear_result = netbox_add_rear_port_template_to_device_type(
        ...     device_type_model="Leviton 5G108-R24",
        ...     name="Rear-Block",
        ...     type="110-punch",
        ...     positions=24,
        ...     description="110-punch termination block",
        ...     confirm=True
        ... )
        
        >>> # Then create RJ45 front ports
        >>> for port in range(1, 25):
        ...     result = netbox_add_front_port_template_to_device_type(
        ...         device_type_model="Leviton 5G108-R24",
        ...         name=f"Port-{port}",
        ...         type="8p8c",
        ...         rear_port_template="Rear-Block",
        ...         rear_port_position=port,
        ...         description=f"Cat6A RJ45 port {port}",
        ...         confirm=True
        ...     )
        
        >>> # Simple 1:1 front-to-rear mapping for SC patch panel
        >>> # Create rear ports first
        >>> for port in range(1, 13):
        ...     rear_result = netbox_add_rear_port_template_to_device_type(
        ...         device_type_model="Generic 12-Port SC Panel",
        ...         name=f"SC-R{port:02d}",
        ...         type="sc",
        ...         positions=1,
        ...         description=f"SC rear port {port}",
        ...         confirm=True
        ...     )
        
        >>> # Then create corresponding front ports
        >>> for port in range(1, 13):
        ...     result = netbox_add_front_port_template_to_device_type(
        ...         device_type_model="Generic 12-Port SC Panel",
        ...         name=f"SC-F{port:02d}",
        ...         type="sc",
        ...         rear_port_template=f"SC-R{port:02d}",
        ...         rear_port_position=1,
        ...         description=f"SC front port {port}",
        ...         confirm=True
        ...     )
    """
    if not confirm:
        return {
            "success": True,
        "dry_run": True,
            "message": "DRY RUN: Front Port Template would be created. Set confirm=True to execute.",
            "would_create": {
                "device_type_model": device_type_model,
                "front_port_name": name,
                "front_port_type": type,
                "rear_port_template": rear_port_template,
                "rear_port_position": rear_port_position,
                "description": description
            }
        }

    # STEP 0: PARAMETER VALIDATION
    validate_physical_port_type(type, "front port")
    validate_rear_port_position(rear_port_position)
    
    if not name or not name.strip():
        raise ValidationError("Front port name cannot be empty")
    
    if not device_type_model or not device_type_model.strip():
        raise ValidationError("Device Type model cannot be empty")
    
    if not rear_port_template or not rear_port_template.strip():
        raise ValidationError("Rear port template name cannot be empty")

    # STEP 1: ULTRATHINK OPTIMIZATION - Find Device Type with expand parameters and fallback strategies
    logger.info(f"Looking up Device Type with model: {device_type_model}")

    try:
        # ULTRATHINK FIX 1: Expand Parameters - Get manufacturer info in single call
        device_types = list(client.dcim.device_types.filter(
            model=device_type_model,
            expand=["manufacturer"]
        ))

        # ULTRATHINK FIX 4: Slug-Based Fallback - Try slug match if exact model fails
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
            raise NotFoundError(f"Device Type with model '{device_type_model}' not found.")

        # ULTRATHINK FIX 3: Defensive Dict/Object Handling
        device_type = device_types[0] if device_types else None
        if not device_type:
            raise NotFoundError(f"Device Type with model '{device_type_model}' not found.")

        device_data = device_type if isinstance(device_type, dict) else device_type.serialize()
        device_type_id = device_data.get('id')
        device_type_display = device_data.get('display', device_type_model)

        logger.info(f"Found Device Type: {device_type_display} (ID: {device_type_id})")

    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Error looking up Device Type: {e}")
        raise NotFoundError(f"Could not find Device Type '{device_type_model}': {e}")

    # STEP 2: VALIDATE - Find the rear port template
    logger.info(f"Looking up Rear Port Template '{rear_port_template}' for Device Type '{device_type_model}'")
    
    try:
        rear_port_templates = client.dcim.rear_port_templates.filter(
            device_type_id=device_type_id,
            name=rear_port_template
        )
        if not rear_port_templates:
            logger.error(f"Rear Port Template '{rear_port_template}' not found for Device Type '{device_type_model}'")
            raise NotFoundError(f"Rear Port Template '{rear_port_template}' not found for Device Type '{device_type_model}'. Create the rear port template first.")
        
        rear_port_template_obj = rear_port_templates[0]
        # Handle both dict and object responses from NetBox API
        rear_port_template_id = rear_port_template_obj.get('id') if isinstance(rear_port_template_obj, dict) else rear_port_template_obj.id
        rear_port_positions = rear_port_template_obj.get('positions') if isinstance(rear_port_template_obj, dict) else rear_port_template_obj.positions
        logger.info(f"Resolved rear port template '{rear_port_template}' to ID: {rear_port_template_id}")
        
        # Validate rear port position against rear port positions
        if rear_port_position > rear_port_positions:
            raise ValidationError(f"Rear port position {rear_port_position} exceeds available positions ({rear_port_positions}) on rear port template '{rear_port_template}'")
        
    except NotFoundError:
        raise
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Error resolving rear port template '{rear_port_template}': {e}")
        raise ValidationError(f"Failed to resolve rear port template '{rear_port_template}': {e}")

    # STEP 3: DEFENSIVE READ - Check for conflicts (does this template already exist?)
    logger.info(f"Checking for existing Front Port Template '{name}' on Device Type '{device_type_model}'")
    
    try:
        existing_templates = client.dcim.front_port_templates.filter(
            device_type_id=device_type_id,
            name=name,
            no_cache=True  # Force live check for accurate conflict detection
        )
        
        if existing_templates:
            existing_template = existing_templates[0]
            logger.warning(f"Front Port Template conflict detected: '{name}' already exists for Device Type '{device_type_model}' (ID: {existing_template.id})")
            raise ConflictError(
                resource_type="Front Port Template",
                identifier=f"{name} for Device Type {device_type_model}",
                existing_id=existing_template.id
            )
            
    except ConflictError:
        raise
    except Exception as e:
        logger.warning(f"Could not check for existing front port templates: {e}")

    # STEP 4: VALIDATE PARAMETERS - Check required fields
    if not type:
        raise ValidationError("Front port type is required and cannot be empty.")

    # STEP 5: WRITE - Create the Front Port Template
    template_payload = {
        "device_type": device_type_id,
        "name": name,
        "type": type,
        "rear_port": rear_port_template_id,
        "rear_port_position": rear_port_position,
        "description": description or ""
    }
    
    try:
        logger.info(f"Creating Front Port Template '{name}' for Device Type '{device_type_model}'...")
        new_template = client.dcim.front_port_templates.create(confirm=confirm, **template_payload)
        template_id = new_template.get('id') if isinstance(new_template, dict) else new_template.id
        logger.info(f"Successfully created Front Port Template with ID: {template_id}")
        
    except Exception as e:
        logger.error(f"Failed to create Front Port Template in NetBox: {e}")
        raise ValidationError(f"NetBox API error during Front Port Template creation: {e}")


    return {
        "success": True,
        "message": f"Front Port Template '{new_template.get('name') if isinstance(new_template, dict) else new_template.name}' successfully added to Device Type '{device_type_model}'.",
        "data": {
            "template_id": template_id,
            "template_name": new_template.get('name') if isinstance(new_template, dict) else new_template.name,
            "template_type": new_template.get('type') if isinstance(new_template, dict) else new_template.type,
            "device_type_model": device_type_model,
            "device_type_id": device_type_id,
            "description": new_template.get('description') if isinstance(new_template, dict) else new_template.description,
            "rear_port_template": rear_port_template,
            "rear_port_position": rear_port_position,
            "rear_port_max_positions": rear_port_positions,
            "netbox_url": f"{client.config.url}/dcim/device-types/{device_type_id}/front-port-templates/"
        }
    }


@mcp_tool(category="dcim")
def netbox_add_rear_port_template_to_device_type(
    client: NetBoxClient,
    device_type_model: str,
    name: str,
    type: str,
    positions: int = 1,
    description: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Add a new Rear Port Template to an existing Device Type.

    This tool defines a standardized rear-facing physical port for all devices of a specific model.
    Rear port templates are essential for patch panels, fiber distribution equipment, and optical
    infrastructure where front ports connect to rear ports through internal pathways.

    Args:
        device_type_model (str): The model name of the Device Type (e.g., "Panduit FP12-C").
        name (str): The name of the rear port (e.g., "MPO-1", "R1", "Backbone-A").
        type (str): The physical type of the rear port. Valid types include:
            - "mpo": Multi-fiber Push-On connector (12/24 fiber)
            - "lc": Lucent Connector (single/duplex fiber)
            - "sc": Subscriber Connector (single/duplex fiber)  
            - "fc": Fiber Channel connector
            - "st": Straight Tip connector
            - "8p8c": 8-position 8-contact (RJ45)
            - "bnc": Bayonet Neill-Concelman connector
            - "f": F-type coaxial connector
            - "splice": Fiber splice point
        positions (int): Number of positions/channels on this port (1-144). For MPO connectors,
            this typically represents the number of individual fiber strands. Defaults to 1.
        description (str, optional): A description for the rear port template.
        client (NetBoxClient): The active NetBox client.
        confirm (bool): Must be True to execute the operation.

    Returns:
        dict: A dictionary containing the operation result and created template data.
        
    Raises:
        ValidationError: If required parameters are missing or invalid.
        ConflictError: If a rear port template with the same name already exists.
        NotFoundError: If the specified Device Type cannot be found.
        
    Example:
        >>> # Create MPO rear port for 24-port fiber patch panel
        >>> result = netbox_add_rear_port_template_to_device_type(
        ...     device_type_model="Panduit FP24-C",
        ...     name="MPO-1", 
        ...     type="mpo",
        ...     positions=24,
        ...     description="24-fiber MPO backbone connection",
        ...     confirm=True
        ... )
        
        >>> # Create standard LC rear ports for duplex patch panel
        >>> for port in range(1, 13):
        ...     result = netbox_add_rear_port_template_to_device_type(
        ...         device_type_model="Generic 12-Port LC Panel",
        ...         name=f"LC-R{port:02d}",
        ...         type="lc",
        ...         positions=2,
        ...         description=f"Duplex LC rear port {port}",
        ...         confirm=True
        ...     )
        
        >>> # Create copper rear ports for Category 6A patch panel
        >>> for port in range(1, 25):
        ...     result = netbox_add_rear_port_template_to_device_type(
        ...         device_type_model="Leviton 5G108-R24",
        ...         name=f"R{port}",
        ...         type="8p8c", 
        ...         positions=1,
        ...         description=f"Cat6A rear port {port}",
        ...         confirm=True
        ...     )
    """
    if not confirm:
        return {
            "success": True,
        "dry_run": True,
            "message": "DRY RUN: Rear Port Template would be created. Set confirm=True to execute.",
            "would_create": {
                "device_type_model": device_type_model,
                "rear_port_name": name,
                "rear_port_type": type,
                "positions": positions,
                "description": description
            }
        }

    # STEP 0: PARAMETER VALIDATION
    validate_physical_port_type(type, "rear port")
    validate_port_positions(positions)
    
    if not name or not name.strip():
        raise ValidationError("Rear port name cannot be empty")
    
    if not device_type_model or not device_type_model.strip():
        raise ValidationError("Device Type model cannot be empty")

    # STEP 1: ULTRATHINK OPTIMIZATION - Find Device Type with expand parameters and fallback strategies
    logger.info(f"Looking up Device Type with model: {device_type_model}")

    try:
        # ULTRATHINK FIX 1: Expand Parameters - Get manufacturer info in single call
        device_types = list(client.dcim.device_types.filter(
            model=device_type_model,
            expand=["manufacturer"]
        ))

        # ULTRATHINK FIX 4: Slug-Based Fallback - Try slug match if exact model fails
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
            raise NotFoundError(f"Device Type with model '{device_type_model}' not found.")

        # ULTRATHINK FIX 3: Defensive Dict/Object Handling
        device_type = device_types[0] if device_types else None
        if not device_type:
            raise NotFoundError(f"Device Type with model '{device_type_model}' not found.")

        device_data = device_type if isinstance(device_type, dict) else device_type.serialize()
        device_type_id = device_data.get('id')
        device_type_display = device_data.get('display', device_type_model)

        logger.info(f"Found Device Type: {device_type_display} (ID: {device_type_id})")

    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Error looking up Device Type: {e}")
        raise NotFoundError(f"Could not find Device Type '{device_type_model}': {e}")

    # STEP 2: DEFENSIVE READ - Check for conflicts (does this template already exist?)
    logger.info(f"Checking for existing Rear Port Template '{name}' on Device Type '{device_type_model}'")
    
    try:
        existing_templates = client.dcim.rear_port_templates.filter(
            device_type_id=device_type_id,
            name=name,
            no_cache=True  # Force live check for accurate conflict detection
        )
        
        if existing_templates:
            existing_template = existing_templates[0]
            logger.warning(f"Rear Port Template conflict detected: '{name}' already exists for Device Type '{device_type_model}' (ID: {existing_template.id})")
            raise ConflictError(
                resource_type="Rear Port Template",
                identifier=f"{name} for Device Type {device_type_model}",
                existing_id=existing_template.id
            )
            
    except ConflictError:
        raise
    except Exception as e:
        logger.warning(f"Could not check for existing rear port templates: {e}")

    # STEP 3: VALIDATE PARAMETERS - Check required fields
    if not type:
        raise ValidationError("Rear port type is required and cannot be empty.")

    # STEP 4: WRITE - Create the Rear Port Template
    template_payload = {
        "device_type": device_type_id,
        "name": name,
        "type": type,
        "positions": positions,
        "description": description or ""
    }
    
    try:
        logger.info(f"Creating Rear Port Template '{name}' for Device Type '{device_type_model}'...")
        new_template = client.dcim.rear_port_templates.create(confirm=confirm, **template_payload)
        template_id = new_template.get('id') if isinstance(new_template, dict) else new_template.id
        logger.info(f"Successfully created Rear Port Template with ID: {template_id}")
        
    except Exception as e:
        logger.error(f"Failed to create Rear Port Template in NetBox: {e}")
        raise ValidationError(f"NetBox API error during Rear Port Template creation: {e}")


    return {
        "success": True,
        "message": f"Rear Port Template '{new_template.get('name') if isinstance(new_template, dict) else new_template.name}' successfully added to Device Type '{device_type_model}'.",
        "data": {
            "template_id": template_id,
            "template_name": new_template.get('name') if isinstance(new_template, dict) else new_template.name,
            "template_type": new_template.get('type') if isinstance(new_template, dict) else new_template.type,
            "device_type_model": device_type_model,
            "device_type_id": device_type_id,
            "description": new_template.get('description') if isinstance(new_template, dict) else new_template.description,
            "positions": new_template.get('positions') if isinstance(new_template, dict) else new_template.positions,
        }
    }


@mcp_tool(category="dcim")
def netbox_add_device_bay_template_to_device_type(
    client: NetBoxClient,
    device_type_model: str,
    name: str,
    description: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Add a new Device Bay Template to an existing Device Type.

    This tool defines a standardized device bay for all devices of a specific model.
    Device bay templates are essential for chassis-based equipment that houses child devices.

    Args:
        device_type_model (str): The model name of the Device Type.
        name (str): The name of the device bay (e.g., "Slot 1", "Bay A").
        description (str, optional): A description for the device bay template.
        client (NetBoxClient): The active NetBox client.
        confirm (bool): Must be True to execute the operation.

    Returns:
        dict: A dictionary containing the operation result and created template data.
    """
    if not confirm:
        return {
            "success": True,
        "dry_run": True,
            "message": "DRY RUN: Device Bay Template would be created. Set confirm=True to execute.",
            "would_create": {
                "device_type_model": device_type_model,
                "device_bay_name": name,
                "description": description
            }
        }

    # ULTRATHINK OPTIMIZATION - Enhanced Device Type lookup with expand parameters
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

        if not device_types:
            raise NotFoundError(f"Device Type with model '{device_type_model}' not found.")

        # ULTRATHINK FIX 3: Defensive Dict/Object Handling
        device_type = device_types[0] if device_types else None
        if not device_type:
            raise NotFoundError(f"Device Type with model '{device_type_model}' not found.")

        device_data = device_type if isinstance(device_type, dict) else device_type.serialize()
        device_type_id = device_data.get('id')
    except NotFoundError:
        raise
    except Exception as e:
        raise NotFoundError(f"Could not find Device Type '{device_type_model}': {e}")

    # Check for conflicts
    try:
        existing_templates = client.dcim.device_bay_templates.filter(
            device_type_id=device_type_id,
            name=name,
            no_cache=True
        )
        if existing_templates:
            existing_template = existing_templates[0]
            logger.warning(f"Device Bay Template conflict detected: '{name}' already exists for Device Type '{device_type_model}' (ID: {existing_template.id})")
            raise ConflictError(
                resource_type="Device Bay Template",
                identifier=f"{name} for Device Type {device_type_model}",
                existing_id=existing_template.id
            )
    except ConflictError:
        raise
    except Exception as e:
        logger.warning(f"Could not check for existing device bay templates: {e}")

    # Create the template
    template_payload = {
        "device_type": device_type_id,
        "name": name,
        "description": description or ""
    }
    
    try:
        new_template = client.dcim.device_bay_templates.create(confirm=confirm, **template_payload)
        template_id = new_template.get('id') if isinstance(new_template, dict) else new_template.id
    except Exception as e:
        raise ValidationError(f"NetBox API error during Device Bay Template creation: {e}")

    return {
        "success": True,
        "message": f"Device Bay Template '{new_template.get('name') if isinstance(new_template, dict) else new_template.name}' successfully added to Device Type '{device_type_model}'.",
        "data": {
            "template_id": template_id,
            "template_name": new_template.get('name') if isinstance(new_template, dict) else new_template.name,
            "device_type_model": device_type_model,
            "device_type_id": device_type_id,
            "description": new_template.get('description') if isinstance(new_template, dict) else new_template.description,
        }
    }


@mcp_tool(category="dcim")
def netbox_add_module_bay_template_to_device_type(
    client: NetBoxClient,
    device_type_model: str,
    name: str,
    position: Optional[str] = None,
    description: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Add a new Module Bay Template to an existing Device Type.

    This tool defines a standardized module bay for all devices of a specific model.
    Module bay templates are essential for modular equipment that houses line cards and modules.

    Args:
        device_type_model (str): The model name of the Device Type.
        name (str): The name of the module bay (e.g., "Slot 1", "LC-0").
        position (str, optional): The position identifier for the module bay.
        description (str, optional): A description for the module bay template.
        client (NetBoxClient): The active NetBox client.
        confirm (bool): Must be True to execute the operation.

    Returns:
        dict: A dictionary containing the operation result and created template data.
    """
    if not confirm:
        return {
            "success": True,
        "dry_run": True,
            "message": "DRY RUN: Module Bay Template would be created. Set confirm=True to execute.",
            "would_create": {
                "device_type_model": device_type_model,
                "module_bay_name": name,
                "position": position,
                "description": description
            }
        }

    # ULTRATHINK OPTIMIZATION - Enhanced Device Type lookup with expand parameters
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

        if not device_types:
            raise NotFoundError(f"Device Type with model '{device_type_model}' not found.")

        # ULTRATHINK FIX 3: Defensive Dict/Object Handling
        device_type = device_types[0] if device_types else None
        if not device_type:
            raise NotFoundError(f"Device Type with model '{device_type_model}' not found.")

        device_data = device_type if isinstance(device_type, dict) else device_type.serialize()
        device_type_id = device_data.get('id')
    except NotFoundError:
        raise
    except Exception as e:
        raise NotFoundError(f"Could not find Device Type '{device_type_model}': {e}")

    # Check for conflicts
    try:
        existing_templates = client.dcim.module_bay_templates.filter(
            device_type_id=device_type_id,
            name=name,
            no_cache=True
        )
        if existing_templates:
            existing_template = existing_templates[0]
            logger.warning(f"Module Bay Template conflict detected: '{name}' already exists for Device Type '{device_type_model}' (ID: {existing_template.id})")
            raise ConflictError(
                resource_type="Module Bay Template",
                identifier=f"{name} for Device Type {device_type_model}",
                existing_id=existing_template.id
            )
    except ConflictError:
        raise
    except Exception as e:
        logger.warning(f"Could not check for existing module bay templates: {e}")

    # Create the template
    template_payload = {
        "device_type": device_type_id,
        "name": name,
        "description": description or ""
    }
    
    if position:
        template_payload["position"] = position
    
    try:
        new_template = client.dcim.module_bay_templates.create(confirm=confirm, **template_payload)
        template_id = new_template.get('id') if isinstance(new_template, dict) else new_template.id
    except Exception as e:
        raise ValidationError(f"NetBox API error during Module Bay Template creation: {e}")

    return {
        "success": True,
        "message": f"Module Bay Template '{new_template.get('name') if isinstance(new_template, dict) else new_template.name}' successfully added to Device Type '{device_type_model}'.",
        "data": {
            "template_id": template_id,
            "template_name": new_template.get('name') if isinstance(new_template, dict) else new_template.name,
            "device_type_model": device_type_model,
            "device_type_id": device_type_id,
            "description": new_template.get('description') if isinstance(new_template, dict) else new_template.description,
            "position": getattr(new_template, 'position', None),
        }
    }