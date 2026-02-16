#!/usr/bin/env python3
"""
DCIM Interface and Cable Management Tools

High-level tools for managing NetBox interfaces, cables, and physical connections
with comprehensive enterprise-grade functionality.
"""

from typing import Dict, Optional, Any
import logging
from ...registry import mcp_tool
from ...client import NetBoxClient

logger = logging.getLogger(__name__)


@mcp_tool(category="dcim")
def netbox_assign_ip_to_interface(
    client: NetBoxClient,
    device_name: str,
    interface_name: str,
    ip_address: str,
    status: str = "active",
    description: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Assign an IP address to a device interface with cross-domain IPAM/DCIM integration.
    
    This revolutionary function bridges NetBox's IPAM and DCIM domains by enabling 
    direct IP assignment to device interfaces. Essential for automated network 
    configuration and infrastructure provisioning workflows.
    
    Args:
        client: NetBoxClient instance (injected)
        device_name: Name of the device
        interface_name: Name of the interface on the device
        ip_address: IP address with CIDR notation (e.g., "10.100.0.1/24")
        status: IP address status (active, reserved, deprecated, dhcp)
        description: Optional description for the IP address
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Cross-domain assignment result with comprehensive status information
        
    Example:
        netbox_assign_ip_to_interface(
            device_name="sw-core-01", 
            interface_name="Vlan100", 
            ip_address="10.100.0.1/24", 
            confirm=True
        )
    """
    try:
        if not all([device_name, interface_name, ip_address]):
            return {
                "success": False,
                "error": "device_name, interface_name, and ip_address are required",
                "error_type": "ValidationError"
            }
        
        # Validate IP address format
        import ipaddress
        try:
            ip_obj = ipaddress.ip_interface(ip_address)
            validated_ip = str(ip_obj)
        except ValueError as e:
            return {
                "success": False,
                "error": f"Invalid IP address format '{ip_address}': {e}",
                "error_type": "ValidationError"
            }
        
        logger.info(f"Assigning IP {validated_ip} to interface {device_name}:{interface_name}")

        # Step 1: Find the device with ULTRATHINK optimizations
        logger.debug(f"Looking up device: {device_name}")

        # ULTRATHINK FIX 1: Expand search parameters with defensive handling
        search_params = {
            "expand": ["device_type", "device_type__manufacturer", "site", "rack", "tenant", "role"],
            "limit": 50
        }

        # ULTRATHINK FIX 2: ID resolution with fallback patterns
        devices = None
        if device_name.isdigit():
            devices = list(client.dcim.devices.filter(id=int(device_name), **search_params))

        if not devices:
            devices = list(client.dcim.devices.filter(name=device_name, **search_params))

        # ULTRATHINK FIX 4: Slug-based fallback mechanisms
        if not devices:
            devices = list(client.dcim.devices.filter(name__icontains=device_name, **search_params))

        if not devices:
            return {
                "success": False,
                "error": f"Device '{device_name}' not found",
                "error_type": "NotFoundError"
            }

        # ULTRATHINK FIX 3: Defensive dict/object access patterns
        device = devices[0] if isinstance(devices, list) else devices
        device_id = device.get("id") if isinstance(device, dict) else getattr(device, "id", None)
        if not device_id:
            return {
                "success": False,
                "error": f"Device '{device_name}' has no valid ID",
                "error_type": "DataError"
            }

        device_name_safe = device.get("name", device_name) if isinstance(device, dict) else getattr(device, "name", device_name)
        logger.debug(f"Found device: {device_name_safe} (ID: {device_id})")

        # Step 2: Find the interface on the device with ULTRATHINK optimizations
        logger.debug(f"Looking up interface: {interface_name} on device {device_name_safe}")

        # ULTRATHINK FIX 1: Expand interface search parameters
        interface_search_params = {
            "device_id": device_id,
            "expand": ["device", "type", "cable"],
            "limit": 50
        }

        # ULTRATHINK FIX 2: Multi-strategy interface search
        interfaces = list(client.dcim.interfaces.filter(name=interface_name, **interface_search_params))

        # ULTRATHINK FIX 4: Fallback interface search
        if not interfaces:
            interfaces = list(client.dcim.interfaces.filter(name__icontains=interface_name, **interface_search_params))
        if not interfaces:
            return {
                "success": False,
                "error": f"Interface '{interface_name}' not found on device '{device_name}'",
                "error_type": "NotFoundError"
            }

        # ULTRATHINK FIX 3: Defensive interface handling
        interface = interfaces[0] if isinstance(interfaces, list) else interfaces
        interface_id = interface.get("id") if isinstance(interface, dict) else getattr(interface, "id", None)
        if not interface_id:
            return {
                "success": False,
                "error": f"Interface '{interface_name}' has no valid ID",
                "error_type": "DataError"
            }

        interface_name_safe = interface.get("name", interface_name) if isinstance(interface, dict) else getattr(interface, "name", interface_name)
        logger.debug(f"Found interface: {interface_name_safe} (ID: {interface_id})")
        
        # Step 3: Check for existing IP assignment conflicts
        logger.debug(f"Checking for IP conflicts: {validated_ip}")
        existing_ips = client.ipam.ip_addresses.filter(address=validated_ip)
        for existing_ip in existing_ips:
            if existing_ip.get("assigned_object_id") and existing_ip.get("assigned_object_type") == "dcim.interface":
                return {
                    "success": False,
                    "error": f"IP address {validated_ip} is already assigned to another interface",
                    "error_type": "ConflictError"
                }
        
        if not confirm:
            # Dry run mode - return what would be assigned without actually assigning
            logger.info(f"DRY RUN: Would assign IP {validated_ip} to interface {device_name}:{interface_name}")
            return {
                "success": True,
                "action": "dry_run",
                "object_type": "ip_assignment",
                "assignment": {
                    "device": {"name": device["name"], "id": device_id},
                    "interface": {"name": interface["name"], "id": interface_id},
                    "ip_address": validated_ip,
                    "status": status,
                    "dry_run": True
                },
                "dry_run": True
            }
        
        # Step 4: Create or update IP address with interface assignment
        # NetBox 4.2.9 pattern: Create IP first, then assign to interface
        ip_data = {
            "address": validated_ip,
            "status": status,
            "assigned_object_type": "dcim.interface",
            "assigned_object_id": interface_id
        }
        
        if description:
            ip_data["description"] = description
        
        # Try to create the IP address with assignment
        logger.info(f"Creating IP address {validated_ip} with interface assignment")
        result = client.ipam.ip_addresses.create(confirm=True, **ip_data)
        
        # Invalidate cache for interface and IP data consistency
        try:
            client.cache.invalidate_for_object("dcim.interfaces", interface_id)
            client.cache.invalidate_pattern("ipam.ip_addresses")
        except Exception as cache_error:
            logger.warning(f"Cache invalidation failed: {cache_error}")
        
        return {
            "success": True,
            "action": "assigned",
            "object_type": "ip_assignment",
            "ip_address": result,
            "assignment": {
                "device": {"name": device["name"], "id": device_id},
                "interface": {"name": interface["name"], "id": interface_id},
                "ip_address": validated_ip,
                "status": status
            },
            "dry_run": result.get("dry_run", False)
        }
        
    except Exception as e:
        logger.error(f"Failed to assign IP {ip_address} to interface {device_name}:{interface_name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@mcp_tool(category="dcim")
def netbox_create_interface(
    client: NetBoxClient,
    device_name: str,
    interface_name: str,
    interface_type: str = "1000base-t",
    mgmt_only: bool = False,
    enabled: bool = True,
    mtu: Optional[int] = None,
    mac_address: Optional[str] = None,
    description: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Create a new interface on a physical device with management interface support.
    
    This tool enables creation of both regular network interfaces and dedicated 
    management interfaces (marked with mgmt_only=True) for out-of-band management,
    console access, and administrative purposes.
    
    Args:
        client: NetBoxClient instance (injected)
        device_name: Name of the device
        interface_name: Interface name (e.g., "eth0", "Management1", "BMC", "iDRAC")
        interface_type: Physical interface type (default: "1000base-t")
        mgmt_only: Mark interface as management-only (excludes from normal networking)
        enabled: Whether the interface is enabled (default: True)
        mtu: Maximum Transmission Unit size
        mac_address: MAC address for the interface
        description: Optional description of the interface
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Dict containing the created interface data and operation status
        
    Examples:
        # Regular network interface
        netbox_create_interface("server-01", "eth0", "10gbase-t", confirm=True)
        
        # Management interface for SSH/SNMP access
        netbox_create_interface("server-01", "Management1", "1000base-t", 
                               mgmt_only=True, confirm=True)
        
        # BMC interface for hardware management
        netbox_create_interface("server-01", "iDRAC", "1000base-t", 
                               mgmt_only=True, 
                               description="Dell iDRAC interface", 
                               confirm=True)
        
        # Console interface for out-of-band access
        netbox_create_interface("switch-01", "Console", "1000base-t", 
                               mgmt_only=True, confirm=True)
    """
    
    # STEP 1: DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Interface would be created. Set confirm=True to execute.",
            "would_create": {
                "device": device_name,
                "interface_name": interface_name,
                "interface_type": interface_type,
                "mgmt_only": mgmt_only,
                "enabled": enabled,
                "mtu": mtu,
                "mac_address": mac_address,
                "description": f"[NetBox-MCP] {description}" if description else ""
            }
        }
    
    # STEP 2: PARAMETER VALIDATION
    if not device_name or not device_name.strip():
        raise ValueError("device_name cannot be empty")
    
    if not interface_name or not interface_name.strip():
        raise ValueError("interface_name cannot be empty")
    
    if not interface_type or not interface_type.strip():
        raise ValueError("interface_type cannot be empty")
    
    # Validate interface type against common NetBox interface types
    valid_interface_types = [
        "1000base-t", "1000base-x-gbic", "1000base-x-sfp", "10gbase-t", "10gbase-cx4",
        "10gbase-x-sfpp", "10gbase-x-xfp", "10gbase-x-x2", "25gbase-x-sfp28", 
        "40gbase-x-qsfpp", "50gbase-x-sfp56", "100gbase-x-cfp", "100gbase-x-cfp2",
        "100gbase-x-cfp4", "100gbase-x-cxp", "100gbase-x-qsfp28", "200gbase-x-cfp2",
        "200gbase-x-qsfp56", "400gbase-x-qsfp112", "400gbase-x-osfp", "virtual", "other"
    ]
    if interface_type not in valid_interface_types:
        logger.warning(f"Interface type '{interface_type}' not in common NetBox types, proceeding anyway")
    
    if mtu is not None and (mtu < 68 or mtu > 65536):
        raise ValueError("mtu must be between 68 and 65536 bytes")
    
    # STEP 3: LOOKUP DEVICE WITH ULTRATHINK OPTIMIZATIONS
    try:
        # ULTRATHINK FIX 1: Expand search parameters with defensive handling
        search_params = {
            "expand": ["device_type", "device_type__manufacturer", "site", "rack", "tenant", "role"],
            "limit": 50
        }

        # ULTRATHINK FIX 2: ID resolution with fallback patterns
        devices = None
        if device_name.isdigit():
            devices = list(client.dcim.devices.filter(id=int(device_name), **search_params))

        if not devices:
            devices = list(client.dcim.devices.filter(name=device_name, **search_params))

        # ULTRATHINK FIX 4: Slug-based fallback mechanisms
        if not devices:
            devices = list(client.dcim.devices.filter(name__icontains=device_name, **search_params))

        if not devices:
            raise ValueError(f"Device '{device_name}' not found")

        # ULTRATHINK FIX 3: Defensive dict/object access patterns
        device = devices[0] if isinstance(devices, list) else devices
        device_id = device.get('id') if isinstance(device, dict) else getattr(device, 'id', None)
        if not device_id:
            raise ValueError(f"Device '{device_name}' has no valid ID")

        device_display = device.get('display', device_name) if isinstance(device, dict) else getattr(device, 'display', device_name)
        
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Could not find device '{device_name}': {e}")
    
    # STEP 4: CONFLICT DETECTION
    try:
        existing_interfaces = client.dcim.interfaces.filter(
            device_id=device_id, 
            name=interface_name,
            no_cache=True  # Force live check
        )
        
        if existing_interfaces:
            existing_interface = existing_interfaces[0]
            existing_id = existing_interface.get('id') if isinstance(existing_interface, dict) else existing_interface.id
            raise ValueError(f"Interface '{interface_name}' already exists on device '{device_name}' with ID {existing_id}")
            
    except ValueError:
        raise
    except Exception as e:
        logger.warning(f"Could not check for existing interfaces: {e}")
    
    # STEP 5: BUILD INTERFACE PAYLOAD
    create_payload = {
        "device": device_id,
        "name": interface_name,
        "type": interface_type,
        "mgmt_only": mgmt_only,
        "enabled": enabled
    }
    
    if mtu is not None:
        create_payload["mtu"] = mtu
        
    if mac_address:
        # Clean and validate MAC address format
        import re
        mac_clean = re.sub(r'[^a-fA-F0-9]', '', mac_address.lower())
        if len(mac_clean) != 12:
            raise ValueError(f"Invalid MAC address format: {mac_address}")
        # Format as standard MAC address
        mac_formatted = ':'.join(mac_clean[i:i+2] for i in range(0, 12, 2))
        create_payload["mac_address"] = mac_formatted
        
    if description:
        create_payload["description"] = f"[NetBox-MCP] {description}"
    
    # STEP 6: CREATE INTERFACE
    try:
        new_interface = client.dcim.interfaces.create(confirm=confirm, **create_payload)
        
        # Apply defensive dict/object handling
        interface_id = new_interface.get('id') if isinstance(new_interface, dict) else new_interface.id
        interface_name_created = new_interface.get('name') if isinstance(new_interface, dict) else new_interface.name
        interface_type_created = new_interface.get('type') if isinstance(new_interface, dict) else getattr(new_interface, 'type', None)
        
        # Handle interface type object/dict
        if isinstance(interface_type_created, dict):
            type_display = interface_type_created.get('label', interface_type_created.get('value', 'Unknown'))
        else:
            type_display = str(interface_type_created) if interface_type_created else 'Unknown'
        
    except Exception as e:
        raise ValueError(f"NetBox API error during interface creation: {e}")
    
    # STEP 7: CACHE INVALIDATION
    try:
        client.cache.invalidate_pattern("dcim.interfaces")
        client.cache.invalidate_for_object("dcim.devices", device_id)
    except Exception as cache_error:
        logger.warning(f"Cache invalidation failed after interface creation: {cache_error}")
    
    # STEP 8: RETURN SUCCESS
    return {
        "success": True,
        "message": f"Interface '{interface_name}' successfully created on device '{device_name}'.",
        "data": {
            "interface_id": interface_id,
            "name": interface_name_created,
            "type": type_display,
            "mgmt_only": new_interface.get('mgmt_only') if isinstance(new_interface, dict) else getattr(new_interface, 'mgmt_only', None),
            "enabled": new_interface.get('enabled') if isinstance(new_interface, dict) else getattr(new_interface, 'enabled', None),
            "mtu": new_interface.get('mtu') if isinstance(new_interface, dict) else getattr(new_interface, 'mtu', None),
            "mac_address": new_interface.get('mac_address') if isinstance(new_interface, dict) else getattr(new_interface, 'mac_address', None),
            "description": new_interface.get('description') if isinstance(new_interface, dict) else getattr(new_interface, 'description', None),
            "device": {
                "id": device_id,
                "name": device_display
            }
        }
    }


# TODO: Implement additional interface management tools:
# - netbox_configure_interface_settings
# - netbox_assign_vlan_to_interface  
# - netbox_monitor_interface_utilization
# - netbox_bulk_interface_operations
# - netbox_get_interface_connections
# 
# NOTE: Cable management tools have been moved to cables.py for better domain separation