#!/usr/bin/env python3
"""
Virtual Machine Disk Management Tools

High-level tools for managing NetBox virtual machine disks,
enabling comprehensive VM storage configuration and capacity management.
"""

from typing import Dict, Optional, Any, List
import logging
from ...registry import mcp_tool
from ...client import NetBoxClient

logger = logging.getLogger(__name__)


@mcp_tool(category="virtualization")
def netbox_create_virtual_disk(
    client: NetBoxClient,
    virtual_machine_name: str,
    disk_name: str,
    size_gb: int,
    description: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Create a new virtual disk for a virtual machine in NetBox.
    
    Virtual disks represent storage volumes attached to VMs, enabling
    comprehensive storage capacity planning and configuration management.
    
    Args:
        client: NetBoxClient instance (injected)
        virtual_machine_name: Name of the virtual machine
        disk_name: Name/identifier for the virtual disk (e.g., "disk1", "root", "data")
        size_gb: Disk size in gigabytes
        description: Optional description of the virtual disk
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Dict containing the created virtual disk data
        
    Raises:
        ValidationError: If required parameters are missing or invalid
        NotFoundError: If virtual machine not found
        ConflictError: If virtual disk already exists
    """
    
    # STEP 1: DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Virtual disk would be created. Set confirm=True to execute.",
            "would_create": {
                "virtual_machine": virtual_machine_name,
                "disk_name": disk_name,
                "size_gb": size_gb,
                "description": f"[NetBox-MCP] {description}" if description else ""
            }
        }
    
    # STEP 2: PARAMETER VALIDATION
    if not virtual_machine_name or not virtual_machine_name.strip():
        raise ValueError("virtual_machine_name cannot be empty")
    
    if not disk_name or not disk_name.strip():
        raise ValueError("disk_name cannot be empty")
    
    if not size_gb or size_gb <= 0:
        raise ValueError("size_gb must be a positive integer")
    
    # STEP 3: LOOKUP VIRTUAL MACHINE
    try:
        # ULTRATHINK FIX 1: Expand search parameters with comprehensive relationship data\n        vm_search_params = {\n            \"expand\": [\"cluster\", \"tenant\", \"role\", \"platform\"],\n            \"limit\": 50\n        }\n\n        # ULTRATHINK FIX 2: ID resolution with fallback patterns\n        virtual_machines = None\n        if virtual_machine_name.isdigit():\n            virtual_machines = list(client.virtualization.virtual_machines.filter(id=int(virtual_machine_name), **vm_search_params))\n\n        if not virtual_machines:\n            virtual_machines = list(client.virtualization.virtual_machines.filter(name=virtual_machine_name, **vm_search_params))\n\n        # ULTRATHINK FIX 4: Slug-based fallback mechanisms\n        if not virtual_machines:\n            virtual_machines = list(client.virtualization.virtual_machines.filter(name__icontains=virtual_machine_name, **vm_search_params))
        if not virtual_machines:
            raise ValueError(f"Virtual machine '{virtual_machine_name}' not found")
        
        virtual_machine = virtual_machines[0]
        vm_id = virtual_machine.get('id') if isinstance(virtual_machine, dict) else virtual_machine.id
        vm_display = virtual_machine.get('display', virtual_machine_name) if isinstance(virtual_machine, dict) else getattr(virtual_machine, 'display', virtual_machine_name)
        
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Could not find virtual machine '{virtual_machine_name}': {e}")
    
    # STEP 4: CONFLICT DETECTION
    try:
        existing_disks = client.virtualization.virtual_disks.filter(
            virtual_machine_id=vm_id,
            name=disk_name,
            no_cache=True
        )
        
        if existing_disks:
            existing_disk = existing_disks[0]
            existing_id = existing_disk.get('id') if isinstance(existing_disk, dict) else existing_disk.id
            raise ValueError(f"Virtual disk '{disk_name}' already exists on VM '{virtual_machine_name}' with ID {existing_id}")
            
    except ValueError:
        raise
    except Exception as e:
        logger.warning(f"Could not check for existing virtual disks: {e}")
    
    # STEP 5: CREATE VIRTUAL DISK
    create_payload = {
        "virtual_machine": vm_id,
        "name": disk_name,
        "size": size_gb * 1024  # Convert GB to MB for NetBox API
    }
    
    if description:
        create_payload["description"] = f"[NetBox-MCP] {description}"
    
    try:
        new_disk = client.virtualization.virtual_disks.create(confirm=confirm, **create_payload)
        
        # Apply defensive dict/object handling
        disk_id = new_disk.get('id') if isinstance(new_disk, dict) else new_disk.id
        disk_name_created = new_disk.get('name') if isinstance(new_disk, dict) else new_disk.name
        disk_size_mb = new_disk.get('size') if isinstance(new_disk, dict) else getattr(new_disk, 'size', 0)
        disk_size_gb = round(disk_size_mb / 1024, 2) if disk_size_mb else 0
        
    except Exception as e:
        raise ValueError(f"NetBox API error during virtual disk creation: {e}")
    
    # STEP 6: RETURN SUCCESS
    return {
        "success": True,
        "message": f"Virtual disk '{disk_name}' successfully created for '{virtual_machine_name}'.",
        "data": {
            "disk_id": disk_id,
            "disk_name": disk_name_created,
            "size_gb": round(disk_size_gb, 2),
            "size_mb": disk_size_mb,
            "virtual_machine_id": vm_id,
            "virtual_machine_name": virtual_machine_name,
            "description": new_disk.get('description') if isinstance(new_disk, dict) else getattr(new_disk, 'description', None)
        }
    }


@mcp_tool(category="virtualization")
def netbox_get_virtual_disk_info(
    client: NetBoxClient,
    virtual_machine_name: Optional[str] = None,
    disk_name: Optional[str] = None,
    disk_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get detailed information about a specific virtual disk.
    
    Args:
        client: NetBoxClient instance (injected)
        virtual_machine_name: Virtual machine name (used with disk_name)
        disk_name: Disk name to retrieve
        disk_id: Disk ID to retrieve
        
    Returns:
        Dict containing detailed virtual disk information
        
    Raises:
        ValidationError: If no valid identifier provided
        NotFoundError: If virtual disk not found
    """
    
    if disk_id:
        try:
            virtual_disk = client.virtualization.virtual_disks.get(disk_id)
        except Exception as e:
            raise ValueError(f"Virtual disk with ID {disk_id} not found: {e}")
    elif virtual_machine_name and disk_name:
        try:
            # First find the VM
            # ULTRATHINK FIX 1: Expand search parameters with comprehensive relationship data\n        vm_search_params = {\n            \"expand\": [\"cluster\", \"tenant\", \"role\", \"platform\"],\n            \"limit\": 50\n        }\n\n        # ULTRATHINK FIX 2: ID resolution with fallback patterns\n        virtual_machines = None\n        if virtual_machine_name.isdigit():\n            virtual_machines = list(client.virtualization.virtual_machines.filter(id=int(virtual_machine_name), **vm_search_params))\n\n        if not virtual_machines:\n            virtual_machines = list(client.virtualization.virtual_machines.filter(name=virtual_machine_name, **vm_search_params))\n\n        # ULTRATHINK FIX 4: Slug-based fallback mechanisms\n        if not virtual_machines:\n            virtual_machines = list(client.virtualization.virtual_machines.filter(name__icontains=virtual_machine_name, **vm_search_params))
            if not virtual_machines:
                raise ValueError(f"Virtual machine '{virtual_machine_name}' not found")
            
            vm = virtual_machines[0]
            vm_id = vm.get('id') if isinstance(vm, dict) else vm.id
            
            # Then find the disk
            disks = client.virtualization.virtual_disks.filter(
                virtual_machine_id=vm_id,
                name=disk_name
            )
            if not disks:
                raise ValueError(f"Virtual disk '{disk_name}' not found on VM '{virtual_machine_name}'")
            
            virtual_disk = disks[0]
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to find virtual disk: {e}")
    else:
        raise ValueError("Either 'disk_id' or both 'virtual_machine_name' and 'disk_name' must be provided")
    
    # Apply defensive dict/object handling
    disk_id = virtual_disk.get('id') if isinstance(virtual_disk, dict) else virtual_disk.id
    disk_name = virtual_disk.get('name') if isinstance(virtual_disk, dict) else virtual_disk.name
    disk_size_mb = virtual_disk.get('size') if isinstance(virtual_disk, dict) else getattr(virtual_disk, 'size', 0)
    disk_size_gb = disk_size_mb / 1024 if disk_size_mb else 0
    disk_description = virtual_disk.get('description') if isinstance(virtual_disk, dict) else getattr(virtual_disk, 'description', None)
    
    # Get virtual machine information - with proper resolution
    vm_obj = virtual_disk.get('virtual_machine') if isinstance(virtual_disk, dict) else getattr(virtual_disk, 'virtual_machine', None)
    if isinstance(vm_obj, dict):
        vm_id = vm_obj.get('id')
        vm_name = vm_obj.get('name', 'N/A')
    else:
        vm_id = getattr(vm_obj, 'id', None) if vm_obj else None
        vm_name = getattr(vm_obj, 'name', None) if vm_obj else None
    
    # If we don't have proper VM name, fetch it directly
    if not vm_name or vm_name == 'N/A' or str(vm_name).isdigit():
        try:
            if vm_id and vm_id != 'N/A':
                vm_full = client.virtualization.virtual_machines.get(vm_id)
                vm_name = vm_full.get('name') if isinstance(vm_full, dict) else vm_full.name
                logger.debug(f"Fetched VM name from API: {vm_name} for ID {vm_id}")
            else:
                vm_name = 'N/A'
                vm_id = 'N/A'
        except Exception as e:
            logger.warning(f"Failed to fetch VM name for ID {vm_id}: {e}")
            vm_name = 'N/A'
            vm_id = vm_id or 'N/A'
    
    return {
        "success": True,
        "message": f"Retrieved virtual disk '{disk_name}'.",
        "data": {
            "disk_id": disk_id,
            "name": disk_name,
            "size_gb": round(disk_size_gb, 2),
            "size_mb": disk_size_mb,
            "description": disk_description,
            "virtual_machine": {
                "id": vm_id,
                "name": vm_name
            },
            "url": virtual_disk.get('url') if isinstance(virtual_disk, dict) else getattr(virtual_disk, 'url', None)
        }
    }


@mcp_tool(category="virtualization")
def netbox_list_all_virtual_disks(
    client: NetBoxClient,
    virtual_machine_name: Optional[str] = None,
    size_gb_min: Optional[int] = None,
    size_gb_max: Optional[int] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Get comprehensive list of all virtual disks with filtering capabilities.
    
    This tool provides bulk virtual disk discovery across the virtualization infrastructure,
    enabling efficient storage capacity analysis and disk management.
    
    Args:
        client: NetBoxClient instance (injected)
        virtual_machine_name: Filter by virtual machine name
        size_gb_min: Filter by minimum disk size in GB
        size_gb_max: Filter by maximum disk size in GB
        limit: Maximum number of disks to return (default: 100)
        
    Returns:
        Dict containing summary list of virtual disks with capacity statistics
    """
    
    # Build filter parameters
    filter_params = {}
    
    if virtual_machine_name:
        # First find the VM ID
        try:
            # ULTRATHINK FIX 1: Expand search parameters with comprehensive relationship data\n            vm_search_params = {\n                \"expand\": [\"cluster\", \"tenant\", \"role\", \"platform\"],\n                \"limit\": 50\n            }\n\n            # ULTRATHINK FIX 2: ID resolution with fallback patterns\n            vms = None\n            if virtual_machine_name.isdigit():\n                vms = list(client.virtualization.virtual_machines.filter(id=int(virtual_machine_name), **vm_search_params))\n\n            if not vms:\n                vms = list(client.virtualization.virtual_machines.filter(name=virtual_machine_name, **vm_search_params))\n\n            # ULTRATHINK FIX 4: Slug-based fallback mechanisms\n            if not vms:\n                vms = list(client.virtualization.virtual_machines.filter(name__icontains=virtual_machine_name, **vm_search_params))
            if not vms:
                raise ValueError(f"Virtual machine '{virtual_machine_name}' not found")
            vm = vms[0]
            vm_id = vm.get('id') if isinstance(vm, dict) else vm.id
            filter_params["virtual_machine_id"] = vm_id
        except Exception as e:
            raise ValueError(f"Failed to find virtual machine: {e}")
    
    if size_gb_min:
        filter_params["size__gte"] = size_gb_min * 1024  # Convert GB to MB
    
    if size_gb_max:
        filter_params["size__lte"] = size_gb_max * 1024  # Convert GB to MB
    
    try:
        # Get virtual disks with applied filters
        # ULTRATHINK FIX 1: Add expand parameters to virtual disk filter\n        if 'expand' not in filter_params:\n            filter_params['expand'] = [\"virtual_machine\"]\n        if 'limit' not in filter_params:\n            filter_params['limit'] = limit\n        virtual_disks = list(client.virtualization.virtual_disks.filter(**filter_params))
        
        # Process disks with defensive dict/object handling
        disks_summary = []
        total_capacity_gb = 0
        size_distribution = {"small": 0, "medium": 0, "large": 0}  # <10GB, 10-100GB, >100GB
        
        for disk in virtual_disks:
            disk_id = disk.get('id') if isinstance(disk, dict) else disk.id
            disk_name = disk.get('name') if isinstance(disk, dict) else disk.name
            disk_size_mb = disk.get('size') if isinstance(disk, dict) else getattr(disk, 'size', 0)
            disk_size_gb = round(disk_size_mb / 1024, 2) if disk_size_mb else 0
            disk_description = disk.get('description') if isinstance(disk, dict) else getattr(disk, 'description', None)
            
            # Accumulate total capacity
            total_capacity_gb += disk_size_gb
            
            # Categorize by size
            if disk_size_gb < 10:
                size_distribution["small"] += 1
            elif disk_size_gb <= 100:
                size_distribution["medium"] += 1
            else:
                size_distribution["large"] += 1
            
            # Get VM information - with proper resolution
            vm_obj = disk.get('virtual_machine') if isinstance(disk, dict) else getattr(disk, 'virtual_machine', None)
            if isinstance(vm_obj, dict):
                vm_id = vm_obj.get('id')
                vm_name = vm_obj.get('name', 'N/A')
            else:
                vm_id = getattr(vm_obj, 'id', None) if vm_obj else None
                vm_name = getattr(vm_obj, 'name', None) if vm_obj else None
            
            # If we don't have proper VM name, fetch it directly
            if not vm_name or vm_name == 'N/A' or str(vm_name).isdigit():
                try:
                    if vm_id and vm_id != 'N/A':
                        vm_full = client.virtualization.virtual_machines.get(vm_id)
                        vm_name = vm_full.get('name') if isinstance(vm_full, dict) else vm_full.name
                        logger.debug(f"Fetched VM name from API in list: {vm_name} for ID {vm_id}")
                    else:
                        vm_name = 'N/A'
                except Exception as e:
                    logger.warning(f"Failed to fetch VM name in list for ID {vm_id}: {e}")
                    vm_name = 'N/A'
            
            disks_summary.append({
                "id": disk_id,
                "name": disk_name,
                "size_gb": round(disk_size_gb, 2),
                "size_mb": disk_size_mb,
                "description": disk_description,
                "virtual_machine_name": vm_name
            })
            
    except Exception as e:
        raise ValueError(f"Failed to retrieve virtual disks: {e}")
    
    return {
        "success": True,
        "message": f"Found {len(disks_summary)} virtual disks.",
        "total_disks": len(disks_summary),
        "capacity_statistics": {
            "total_capacity_gb": round(total_capacity_gb, 2),
            "average_disk_size_gb": round(total_capacity_gb / len(disks_summary), 2) if disks_summary else 0,
            "size_distribution": size_distribution
        },
        "applied_filters": {
            "virtual_machine_name": virtual_machine_name,
            "size_gb_min": size_gb_min,
            "size_gb_max": size_gb_max,
            "limit": limit
        },
        "data": disks_summary
    }


@mcp_tool(category="virtualization")
def netbox_update_virtual_disk(
    client: NetBoxClient,
    disk_id: int,
    disk_name: Optional[str] = None,
    size_gb: Optional[int] = None,
    description: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Update an existing virtual disk in NetBox.
    
    Args:
        client: NetBoxClient instance (injected)
        disk_id: ID of the virtual disk to update
        disk_name: New name for the disk
        size_gb: New size in gigabytes
        description: New description for the disk
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Dict containing the updated virtual disk data
    """
    
    # STEP 1: DRY RUN CHECK
    if not confirm:
        update_fields = {}
        if disk_name: update_fields["name"] = disk_name
        if size_gb: update_fields["size_gb"] = size_gb
        if description: update_fields["description"] = f"[NetBox-MCP] {description}"
        
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Virtual disk would be updated. Set confirm=True to execute.",
            "would_update": {
                "disk_id": disk_id,
                "fields": update_fields
            }
        }
    
    # STEP 2: PARAMETER VALIDATION
    if not disk_id or disk_id <= 0:
        raise ValueError("disk_id must be a positive integer")
    
    if not any([disk_name, size_gb, description is not None]):
        raise ValueError("At least one field (disk_name, size_gb, description) must be provided for update")
    
    if size_gb and size_gb <= 0:
        raise ValueError("size_gb must be a positive integer")
    
    # STEP 3: BUILD UPDATE PAYLOAD
    update_payload = {}
    
    if disk_name:
        if not disk_name.strip():
            raise ValueError("disk_name cannot be empty")
        update_payload["name"] = disk_name
    
    if size_gb:
        update_payload["size"] = size_gb * 1024  # Convert GB to MB
    
    if description is not None:
        update_payload["description"] = f"[NetBox-MCP] {description}" if description else ""
    
    # STEP 4: UPDATE VIRTUAL DISK
    try:
        updated_disk = client.virtualization.virtual_disks.update(disk_id, confirm=confirm, **update_payload)
        
        # Apply defensive dict/object handling
        disk_id_updated = updated_disk.get('id') if isinstance(updated_disk, dict) else updated_disk.id
        disk_name_updated = updated_disk.get('name') if isinstance(updated_disk, dict) else updated_disk.name
        disk_size_mb = updated_disk.get('size') if isinstance(updated_disk, dict) else getattr(updated_disk, 'size', 0)
        disk_size_gb = round(disk_size_mb / 1024, 2) if disk_size_mb else 0
        
    except Exception as e:
        raise ValueError(f"NetBox API error during virtual disk update: {e}")
    
    # STEP 5: RETURN SUCCESS
    return {
        "success": True,
        "message": f"Virtual disk ID {disk_id} successfully updated.",
        "data": {
            "disk_id": disk_id_updated,
            "name": disk_name_updated,
            "size_gb": round(disk_size_gb, 2),
            "size_mb": disk_size_mb,
            "description": updated_disk.get('description') if isinstance(updated_disk, dict) else getattr(updated_disk, 'description', None)
        }
    }


@mcp_tool(category="virtualization")
def netbox_delete_virtual_disk(
    client: NetBoxClient,
    disk_id: int,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Delete a virtual disk from NetBox.

    Args:
        client: NetBoxClient instance (injected)
        disk_id: ID of the virtual disk to delete
        confirm: Must be True to execute (safety mechanism)

    Returns:
        Dict containing deletion confirmation
    """

    # 🛡️ ULTRATHINK FIX: Detect phantom calls from cached conversation state
    if not disk_id or disk_id <= 0:
        return {
            "success": False,
            "error": "PHANTOM_CALL_BLOCKED",
            "message": "Blocked phantom virtual disk delete call (likely from cached conversation state). disk_id is required and must be positive.",
            "debug_info": {
                "disk_id_received": disk_id,
                "confirm_received": confirm,
                "source": "Possibly cached conversation state replay"
            }
        }

    # STEP 1: DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Virtual disk would be deleted. Set confirm=True to execute.",
            "would_delete": {
                "disk_id": disk_id
            }
        }
    
    # STEP 2: PARAMETER VALIDATION
    if not disk_id or disk_id <= 0:
        raise ValueError("disk_id must be a positive integer")
    
    # STEP 3: GET DISK INFO BEFORE DELETION
    try:
        virtual_disk = client.virtualization.virtual_disks.get(disk_id)
        disk_name = virtual_disk.get('name') if isinstance(virtual_disk, dict) else virtual_disk.name
        
        # Get VM name
        vm_obj = virtual_disk.get('virtual_machine') if isinstance(virtual_disk, dict) else getattr(virtual_disk, 'virtual_machine', None)
        if isinstance(vm_obj, dict):
            vm_name = vm_obj.get('name', 'N/A')
        else:
            vm_name = str(vm_obj) if vm_obj else 'N/A'
        
    except Exception as e:
        raise ValueError(f"Failed to find virtual disk for deletion: {e}")
    
    # STEP 4: DELETE VIRTUAL DISK
    try:
        client.virtualization.virtual_disks.delete(disk_id, confirm=confirm)
        
    except Exception as e:
        raise ValueError(f"NetBox API error during virtual disk deletion: {e}")
    
    # STEP 5: RETURN SUCCESS
    return {
        "success": True,
        "message": f"Virtual disk '{disk_name}' on '{vm_name}' (ID: {disk_id}) successfully deleted.",
        "data": {
            "deleted_disk_id": disk_id,
            "deleted_disk_name": disk_name,
            "virtual_machine_name": vm_name
        }
    }