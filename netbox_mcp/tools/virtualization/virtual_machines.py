#!/usr/bin/env python3
"""
Virtual Machine Management Tools

High-level tools for managing NetBox virtual machines with comprehensive
VM lifecycle management, resource allocation, and provisioning automation.
"""

from typing import Dict, Optional, Any, List
import logging
from ...registry import mcp_tool
from ...client import NetBoxClient

logger = logging.getLogger(__name__)


@mcp_tool(category="virtualization")
def netbox_create_virtual_machine(
    client: NetBoxClient,
    name: str,
    cluster: str,
    vcpus: Optional[int] = None,
    memory_mb: Optional[int] = None,
    disk_gb: Optional[int] = None,
    status: str = "active",
    role: Optional[str] = None,
    tenant: Optional[str] = None,
    platform: Optional[str] = None,
    description: Optional[str] = None,
    comments: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Create a new virtual machine in NetBox.
    
    Virtual machines represent compute instances running on virtualization clusters,
    providing comprehensive resource tracking and lifecycle management.
    
    Args:
        client: NetBoxClient instance (injected)
        name: VM name (e.g., "web-server-01", "db-primary")
        cluster: Cluster name where the VM will be hosted
        vcpus: Number of virtual CPUs allocated
        memory_mb: Memory allocation in megabytes
        disk_gb: Disk space allocation in gigabytes
        status: VM status (active, offline, planned, staged, failed, decommissioning)
        role: VM role/function (e.g., "Web Server", "Database")
        tenant: Tenant assignment for multi-tenancy
        platform: Operating system platform
        description: Optional description of the VM
        comments: Additional comments
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Dict containing the created virtual machine data
        
    Raises:
        ValidationError: If required parameters are missing or invalid
        NotFoundError: If cluster, role, tenant, or platform not found
        ConflictError: If VM already exists
    """
    
    # STEP 1: DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Virtual machine would be created. Set confirm=True to execute.",
            "would_create": {
                "name": name,
                "cluster": cluster,
                "vcpus": vcpus,
                "memory_mb": memory_mb,
                "disk_gb": disk_gb,
                "status": status,
                "role": role,
                "tenant": tenant,
                "platform": platform,
                "description": f"[NetBox-MCP] {description}" if description else "",
                "comments": f"[NetBox-MCP] {comments}" if comments else ""
            }
        }
    
    # STEP 2: PARAMETER VALIDATION
    if not name or not name.strip():
        raise ValueError("name cannot be empty")
    
    if not cluster or not cluster.strip():
        raise ValueError("cluster cannot be empty")
    
    # STEP 3: LOOKUP CLUSTER
    try:
        clusters = client.virtualization.clusters.filter(name=cluster)
        if not clusters:
            raise ValueError(f"Cluster '{cluster}' not found")
        
        cluster_obj = clusters[0]
        cluster_id = cluster_obj.get('id') if isinstance(cluster_obj, dict) else cluster_obj.id
        cluster_display = cluster_obj.get('display', cluster) if isinstance(cluster_obj, dict) else getattr(cluster_obj, 'display', cluster)
        
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Could not find cluster '{cluster}': {e}")
    
    # STEP 4: LOOKUP ROLE (if provided)
    role_id = None
    if role:
        try:
            roles = client.dcim.device_roles.filter(name=role)
            if not roles:
                raise ValueError(f"Role '{role}' not found")
            
            role_obj = roles[0]
            role_id = role_obj.get('id') if isinstance(role_obj, dict) else role_obj.id
            
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Could not find role '{role}': {e}")
    
    # STEP 5: LOOKUP TENANT (if provided)
    tenant_id = None
    if tenant:
        try:
            tenants = client.tenancy.tenants.filter(name=tenant)
            if not tenants:
                raise ValueError(f"Tenant '{tenant}' not found")
            
            tenant_obj = tenants[0]
            tenant_id = tenant_obj.get('id') if isinstance(tenant_obj, dict) else tenant_obj.id
            
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Could not find tenant '{tenant}': {e}")
    
    # STEP 6: LOOKUP PLATFORM (if provided)
    platform_id = None
    if platform:
        try:
            platforms = client.dcim.platforms.filter(name=platform)
            if not platforms:
                raise ValueError(f"Platform '{platform}' not found")
            
            platform_obj = platforms[0]
            platform_id = platform_obj.get('id') if isinstance(platform_obj, dict) else platform_obj.id
            
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Could not find platform '{platform}': {e}")
    
    # STEP 7: CONFLICT DETECTION
    try:
        existing_vms = client.virtualization.virtual_machines.filter(
            name=name,
            no_cache=True
        )
        
        if existing_vms:
            existing_vm = existing_vms[0]
            existing_id = existing_vm.get('id') if isinstance(existing_vm, dict) else existing_vm.id
            raise ValueError(f"Virtual machine '{name}' already exists with ID {existing_id}")
            
    except ValueError:
        raise
    except Exception as e:
        logger.warning(f"Could not check for existing virtual machines: {e}")
    
    # STEP 8: CREATE VIRTUAL MACHINE
    create_payload = {
        "name": name,
        "cluster": cluster_id,
        "status": status
    }
    
    if vcpus:
        create_payload["vcpus"] = vcpus
    
    if memory_mb:
        create_payload["memory"] = memory_mb
    
    if disk_gb:
        create_payload["disk"] = disk_gb
    
    if role_id:
        create_payload["role"] = role_id
    
    if tenant_id:
        create_payload["tenant"] = tenant_id
    
    if platform_id:
        create_payload["platform"] = platform_id
    
    if description:
        create_payload["description"] = f"[NetBox-MCP] {description}"
    
    if comments:
        create_payload["comments"] = f"[NetBox-MCP] {comments}"
    
    try:
        new_vm = client.virtualization.virtual_machines.create(confirm=confirm, **create_payload)
        
        # Apply defensive dict/object handling
        vm_id = new_vm.get('id') if isinstance(new_vm, dict) else new_vm.id
        vm_name = new_vm.get('name') if isinstance(new_vm, dict) else new_vm.name
        vm_status = new_vm.get('status') if isinstance(new_vm, dict) else getattr(new_vm, 'status', None)
        vm_vcpus = new_vm.get('vcpus') if isinstance(new_vm, dict) else getattr(new_vm, 'vcpus', None)
        vm_memory = new_vm.get('memory') if isinstance(new_vm, dict) else getattr(new_vm, 'memory', None)
        vm_disk = new_vm.get('disk') if isinstance(new_vm, dict) else getattr(new_vm, 'disk', None)
        
    except Exception as e:
        raise ValueError(f"NetBox API error during virtual machine creation: {e}")
    
    # STEP 9: RETURN SUCCESS
    return {
        "success": True,
        "message": f"Virtual machine '{name}' successfully created.",
        "data": {
            "vm_id": vm_id,
            "name": vm_name,
            "cluster": cluster,
            "status": vm_status,
            "resources": {
                "vcpus": vm_vcpus,
                "memory_mb": vm_memory,
                "disk_gb": vm_disk
            },
            "role": role,
            "tenant": tenant,
            "platform": platform,
            "description": new_vm.get('description') if isinstance(new_vm, dict) else getattr(new_vm, 'description', None)
        }
    }


@mcp_tool(category="virtualization")
def netbox_get_virtual_machine_info(
    client: NetBoxClient,
    name: Optional[str] = None,
    vm_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get detailed information about a specific virtual machine.
    
    Args:
        client: NetBoxClient instance (injected)
        name: VM name to retrieve
        vm_id: VM ID to retrieve
        
    Returns:
        Dict containing detailed VM information including interfaces and resources
        
    Raises:
        ValidationError: If no valid identifier provided
        NotFoundError: If VM not found
    """
    
    if not any([name, vm_id]):
        raise ValueError("Either 'name' or 'vm_id' must be provided")
    
    try:
        if vm_id:
            vm = client.virtualization.virtual_machines.get(vm_id)
        else:  # name
            # ULTRATHINK FIX 1: Expand search parameters with comprehensive relationship data
            search_params = {
                "expand": ["cluster", "tenant", "role", "platform"],
                "limit": 50
            }

            # ULTRATHINK FIX 2: ID resolution with fallback patterns
            vms = None
            if name.isdigit():
                vms = list(client.virtualization.virtual_machines.filter(id=int(name), **search_params))

            if not vms:
                vms = list(client.virtualization.virtual_machines.filter(name=name, **search_params))

            # ULTRATHINK FIX 4: Slug-based fallback mechanisms
            if not vms:
                vms = list(client.virtualization.virtual_machines.filter(name__icontains=name, **search_params))
            if not vms:
                raise ValueError(f"Virtual machine '{name}' not found")
            # ULTRATHINK FIX 3: Defensive dict/object access patterns
            vm = vms[0] if isinstance(vms, list) else vms
        
        # Apply defensive dict/object handling
        vm_id = vm.get('id') if isinstance(vm, dict) else vm.id
        vm_name = vm.get('name') if isinstance(vm, dict) else vm.name
        vm_status = vm.get('status') if isinstance(vm, dict) else getattr(vm, 'status', None)
        vm_vcpus = vm.get('vcpus') if isinstance(vm, dict) else getattr(vm, 'vcpus', None)
        vm_memory = vm.get('memory') if isinstance(vm, dict) else getattr(vm, 'memory', None)
        vm_disk = vm.get('disk') if isinstance(vm, dict) else getattr(vm, 'disk', None)
        vm_description = vm.get('description') if isinstance(vm, dict) else getattr(vm, 'description', None)
        vm_comments = vm.get('comments') if isinstance(vm, dict) else getattr(vm, 'comments', None)
        
        # Get cluster information
        cluster_obj = vm.get('cluster') if isinstance(vm, dict) else getattr(vm, 'cluster', None)
        if isinstance(cluster_obj, dict):
            cluster_name = cluster_obj.get('name', 'N/A')
            cluster_id = cluster_obj.get('id', 'N/A')
        else:
            cluster_name = str(cluster_obj) if cluster_obj else 'N/A'
            cluster_id = getattr(cluster_obj, 'id', 'N/A') if cluster_obj else 'N/A'
        
        # Get role information
        role_obj = vm.get('role') if isinstance(vm, dict) else getattr(vm, 'role', None)
        if isinstance(role_obj, dict):
            role_name = role_obj.get('name', 'N/A')
        else:
            role_name = str(role_obj) if role_obj else 'N/A'
        
        # Get tenant information
        tenant_obj = vm.get('tenant') if isinstance(vm, dict) else getattr(vm, 'tenant', None)
        if isinstance(tenant_obj, dict):
            tenant_name = tenant_obj.get('name', 'N/A')
        else:
            tenant_name = str(tenant_obj) if tenant_obj else 'N/A'
        
        # Get platform information
        platform_obj = vm.get('platform') if isinstance(vm, dict) else getattr(vm, 'platform', None)
        if isinstance(platform_obj, dict):
            platform_name = platform_obj.get('name', 'N/A')
        else:
            platform_name = str(platform_obj) if platform_obj else 'N/A'
        
        # Get interfaces for this VM
        try:
            vm_interfaces = list(client.virtualization.interfaces.filter(virtual_machine_id=vm_id))
            interface_count = len(vm_interfaces)
            
            interfaces_summary = []
            for interface in vm_interfaces[:5]:  # Show first 5
                iface_name = interface.get('name') if isinstance(interface, dict) else getattr(interface, 'name', 'N/A')
                iface_enabled = interface.get('enabled') if isinstance(interface, dict) else getattr(interface, 'enabled', False)
                iface_mac = interface.get('mac_address') if isinstance(interface, dict) else getattr(interface, 'mac_address', None)
                
                interfaces_summary.append({
                    "name": iface_name,
                    "enabled": iface_enabled,
                    "mac_address": iface_mac
                })
                
        except Exception:
            interface_count = 0
            interfaces_summary = []
        
        # Get virtual disks for this VM
        try:
            vm_disks = list(client.virtualization.virtual_disks.filter(virtual_machine_id=vm_id))
            disk_count = len(vm_disks)
            total_disk_gb = 0
            
            for disk in vm_disks:
                disk_size_mb = disk.get('size', 0) if isinstance(disk, dict) else getattr(disk, 'size', 0)
                total_disk_gb += round(disk_size_mb / 1024, 2) if disk_size_mb else 0
                
        except Exception:
            disk_count = 0
            total_disk_gb = 0
        
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Failed to retrieve virtual machine: {e}")
    
    return {
        "success": True,
        "message": f"Retrieved virtual machine '{vm_name}'.",
        "data": {
            "vm_id": vm_id,
            "name": vm_name,
            "status": vm_status,
            "cluster": {
                "id": cluster_id,
                "name": cluster_name
            },
            "resources": {
                "vcpus": vm_vcpus,
                "memory_mb": vm_memory,
                "memory_gb": round(vm_memory / 1024, 2) if vm_memory else None,
                "disk_gb": round(vm_disk / 1024, 2) if vm_disk else None,
                "total_virtual_disks_gb": round(total_disk_gb, 2)
            },
            "role": role_name,
            "tenant": tenant_name,
            "platform": platform_name,
            "description": vm_description,
            "comments": vm_comments,
            "interfaces": {
                "count": interface_count,
                "summary": interfaces_summary
            },
            "virtual_disks": {
                "count": disk_count,
                "total_gb": round(total_disk_gb, 2)
            },
            "url": vm.get('url') if isinstance(vm, dict) else getattr(vm, 'url', None)
        }
    }


@mcp_tool(category="virtualization")
def netbox_list_all_virtual_machines(
    client: NetBoxClient,
    cluster: Optional[str] = None,
    status: Optional[str] = None,
    role: Optional[str] = None,
    tenant: Optional[str] = None,
    platform: Optional[str] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Get comprehensive list of all virtual machines with filtering capabilities.
    
    This tool provides bulk VM discovery across the virtualization infrastructure,
    enabling efficient resource management and capacity planning.
    
    Args:
        client: NetBoxClient instance (injected)
        cluster: Filter by cluster name
        status: Filter by status (active, offline, planned, etc.)
        role: Filter by role name
        tenant: Filter by tenant name
        platform: Filter by platform name
        limit: Maximum number of VMs to return (default: 100)
        
    Returns:
        Dict containing summary list of VMs with resource statistics
    """
    
    # Build filter parameters
    filter_params = {}
    
    if cluster:
        try:
            clusters = client.virtualization.clusters.filter(name=cluster)
            if not clusters:
                raise ValueError(f"Cluster '{cluster}' not found")
            cluster_obj = clusters[0]
            cluster_id = cluster_obj.get('id') if isinstance(cluster_obj, dict) else cluster_obj.id
            filter_params["cluster_id"] = cluster_id
        except Exception as e:
            raise ValueError(f"Failed to find cluster: {e}")
    
    if status:
        filter_params["status"] = status
    
    if role:
        try:
            roles = client.dcim.device_roles.filter(name=role)
            if not roles:
                raise ValueError(f"Role '{role}' not found")
            role_obj = roles[0]
            role_id = role_obj.get('id') if isinstance(role_obj, dict) else role_obj.id
            filter_params["role_id"] = role_id
        except Exception as e:
            raise ValueError(f"Failed to find role: {e}")
    
    if tenant:
        try:
            tenants = client.tenancy.tenants.filter(name=tenant)
            if not tenants:
                raise ValueError(f"Tenant '{tenant}' not found")
            tenant_obj = tenants[0]
            tenant_id = tenant_obj.get('id') if isinstance(tenant_obj, dict) else tenant_obj.id
            filter_params["tenant_id"] = tenant_id
        except Exception as e:
            raise ValueError(f"Failed to find tenant: {e}")
    
    if platform:
        try:
            platforms = client.dcim.platforms.filter(name=platform)
            if not platforms:
                raise ValueError(f"Platform '{platform}' not found")
            platform_obj = platforms[0]
            platform_id = platform_obj.get('id') if isinstance(platform_obj, dict) else platform_obj.id
            filter_params["platform_id"] = platform_id
        except Exception as e:
            raise ValueError(f"Failed to find platform: {e}")
    
    try:
        # Get VMs with applied filters
        virtual_machines = list(client.virtualization.virtual_machines.filter(**filter_params)[:limit])
        
        # Process VMs with defensive dict/object handling
        vms_summary = []
        total_vcpus = 0
        total_memory_gb = 0
        total_disk_gb = 0
        status_counts = {}
        cluster_counts = {}
        
        for vm in virtual_machines:
            vm_id = vm.get('id') if isinstance(vm, dict) else vm.id
            vm_name = vm.get('name') if isinstance(vm, dict) else vm.name
            vm_status = vm.get('status') if isinstance(vm, dict) else getattr(vm, 'status', None)
            vm_vcpus = vm.get('vcpus') if isinstance(vm, dict) else getattr(vm, 'vcpus', 0)
            vm_memory = vm.get('memory') if isinstance(vm, dict) else getattr(vm, 'memory', 0)
            vm_disk = vm.get('disk') if isinstance(vm, dict) else getattr(vm, 'disk', 0)
            
            # Count by status
            if isinstance(vm_status, dict):
                status_value = vm_status.get('value', 'unknown')
            else:
                status_value = str(vm_status) if vm_status else 'unknown'
            status_counts[status_value] = status_counts.get(status_value, 0) + 1
            
            # Get cluster, role, tenant, platform names
            cluster_obj = vm.get('cluster') if isinstance(vm, dict) else getattr(vm, 'cluster', None)
            if isinstance(cluster_obj, dict):
                cluster_name = cluster_obj.get('name', 'N/A')
            else:
                cluster_name = str(cluster_obj) if cluster_obj else 'N/A'
            
            # Count by cluster
            cluster_counts[cluster_name] = cluster_counts.get(cluster_name, 0) + 1
            
            role_obj = vm.get('role') if isinstance(vm, dict) else getattr(vm, 'role', None)
            if isinstance(role_obj, dict):
                role_name = role_obj.get('name', 'N/A')
            else:
                role_name = str(role_obj) if role_obj else 'N/A'
            
            tenant_obj = vm.get('tenant') if isinstance(vm, dict) else getattr(vm, 'tenant', None)
            if isinstance(tenant_obj, dict):
                tenant_name = tenant_obj.get('name', 'N/A')
            else:
                tenant_name = str(tenant_obj) if tenant_obj else 'N/A'
            
            platform_obj = vm.get('platform') if isinstance(vm, dict) else getattr(vm, 'platform', None)
            if isinstance(platform_obj, dict):
                platform_name = platform_obj.get('name', 'N/A')
            else:
                platform_name = str(platform_obj) if platform_obj else 'N/A'
            
            # Accumulate resource totals
            total_vcpus += vm_vcpus or 0
            total_memory_gb += round(vm_memory / 1024, 2) if vm_memory else 0
            total_disk_gb += round(vm_disk / 1024, 2) if vm_disk else 0
            
            vms_summary.append({
                "id": vm_id,
                "name": vm_name,
                "status": status_value,
                "cluster": cluster_name,
                "role": role_name,
                "tenant": tenant_name,
                "platform": platform_name,
                "resources": {
                    "vcpus": vm_vcpus,
                    "memory_mb": vm_memory,
                    "memory_gb": round(vm_memory / 1024, 2) if vm_memory else 0,
                    "disk_gb": round(vm_disk / 1024, 2) if vm_disk else 0
                }
            })
            
    except Exception as e:
        raise ValueError(f"Failed to retrieve virtual machines: {e}")
    
    return {
        "success": True,
        "message": f"Found {len(vms_summary)} virtual machines.",
        "total_vms": len(vms_summary),
        "resource_totals": {
            "total_vcpus": total_vcpus,
            "total_memory_gb": round(total_memory_gb, 2),
            "total_disk_gb": round(total_disk_gb, 2),
            "average_vcpus": round(total_vcpus / len(vms_summary), 1) if vms_summary else 0,
            "average_memory_gb": round(total_memory_gb / len(vms_summary), 2) if vms_summary else 0,
            "average_disk_gb": round(total_disk_gb / len(vms_summary), 2) if vms_summary else 0
        },
        "distribution": {
            "status_counts": status_counts,
            "cluster_counts": cluster_counts
        },
        "applied_filters": {
            "cluster": cluster,
            "status": status,
            "role": role,
            "tenant": tenant,
            "platform": platform,
            "limit": limit
        },
        "data": vms_summary
    }


@mcp_tool(category="virtualization")
def netbox_update_virtual_machine(
    client: NetBoxClient,
    vm_id: int,
    name: Optional[str] = None,
    vcpus: Optional[int] = None,
    memory_mb: Optional[int] = None,
    disk_gb: Optional[int] = None,
    status: Optional[str] = None,
    role: Optional[str] = None,
    tenant: Optional[str] = None,
    platform: Optional[str] = None,
    description: Optional[str] = None,
    comments: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Update an existing virtual machine in NetBox.
    
    Args:
        client: NetBoxClient instance (injected)
        vm_id: ID of the VM to update
        name: New name for the VM
        vcpus: New vCPU allocation
        memory_mb: New memory allocation in MB
        disk_gb: New disk allocation in GB
        status: New status
        role: New role assignment
        tenant: New tenant assignment
        platform: New platform assignment
        description: New description
        comments: New comments
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Dict containing the updated VM data
    """
    
    # STEP 1: DRY RUN CHECK
    if not confirm:
        update_fields = {}
        if name: update_fields["name"] = name
        if vcpus: update_fields["vcpus"] = vcpus
        if memory_mb: update_fields["memory_mb"] = memory_mb
        if disk_gb: update_fields["disk_gb"] = disk_gb
        if status: update_fields["status"] = status
        if role: update_fields["role"] = role
        if tenant: update_fields["tenant"] = tenant
        if platform: update_fields["platform"] = platform
        if description: update_fields["description"] = f"[NetBox-MCP] {description}"
        if comments: update_fields["comments"] = f"[NetBox-MCP] {comments}"
        
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Virtual machine would be updated. Set confirm=True to execute.",
            "would_update": {
                "vm_id": vm_id,
                "fields": update_fields
            }
        }
    
    # STEP 2: PARAMETER VALIDATION
    if not vm_id or vm_id <= 0:
        raise ValueError("vm_id must be a positive integer")
    
    if not any([name, vcpus, memory_mb, disk_gb, status, role, tenant, platform, description is not None, comments is not None]):
        raise ValueError("At least one field must be provided for update")
    
    # STEP 3: BUILD UPDATE PAYLOAD
    update_payload = {}
    
    if name:
        if not name.strip():
            raise ValueError("name cannot be empty")
        update_payload["name"] = name
    
    if vcpus:
        if vcpus <= 0:
            raise ValueError("vcpus must be a positive integer")
        update_payload["vcpus"] = vcpus
    
    if memory_mb:
        if memory_mb <= 0:
            raise ValueError("memory_mb must be a positive integer")
        update_payload["memory"] = memory_mb
    
    if disk_gb:
        if disk_gb <= 0:
            raise ValueError("disk_gb must be a positive integer")
        update_payload["disk"] = disk_gb
    
    if status:
        update_payload["status"] = status
    
    if role:
        try:
            roles = client.dcim.device_roles.filter(name=role)
            if not roles:
                raise ValueError(f"Role '{role}' not found")
            role_obj = roles[0]
            role_id = role_obj.get('id') if isinstance(role_obj, dict) else role_obj.id
            update_payload["role"] = role_id
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Could not find role '{role}': {e}")
    
    if tenant:
        try:
            tenants = client.tenancy.tenants.filter(name=tenant)
            if not tenants:
                raise ValueError(f"Tenant '{tenant}' not found")
            tenant_obj = tenants[0]
            tenant_id = tenant_obj.get('id') if isinstance(tenant_obj, dict) else tenant_obj.id
            update_payload["tenant"] = tenant_id
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Could not find tenant '{tenant}': {e}")
    
    if platform:
        try:
            platforms = client.dcim.platforms.filter(name=platform)
            if not platforms:
                raise ValueError(f"Platform '{platform}' not found")
            platform_obj = platforms[0]
            platform_id = platform_obj.get('id') if isinstance(platform_obj, dict) else platform_obj.id
            update_payload["platform"] = platform_id
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Could not find platform '{platform}': {e}")
    
    if description is not None:
        update_payload["description"] = f"[NetBox-MCP] {description}" if description else ""
    
    if comments is not None:
        update_payload["comments"] = f"[NetBox-MCP] {comments}" if comments else ""
    
    # STEP 4: UPDATE VM
    try:
        updated_vm = client.virtualization.virtual_machines.update(vm_id, confirm=confirm, **update_payload)
        
        # Apply defensive dict/object handling
        vm_id_updated = updated_vm.get('id') if isinstance(updated_vm, dict) else updated_vm.id
        vm_name_updated = updated_vm.get('name') if isinstance(updated_vm, dict) else updated_vm.name
        vm_status_updated = updated_vm.get('status') if isinstance(updated_vm, dict) else getattr(updated_vm, 'status', None)
        
    except Exception as e:
        raise ValueError(f"NetBox API error during VM update: {e}")
    
    # STEP 5: RETURN SUCCESS
    return {
        "success": True,
        "message": f"Virtual machine ID {vm_id} successfully updated.",
        "data": {
            "vm_id": vm_id_updated,
            "name": vm_name_updated,
            "status": vm_status_updated,
            "resources": {
                "vcpus": updated_vm.get('vcpus') if isinstance(updated_vm, dict) else getattr(updated_vm, 'vcpus', None),
                "memory_mb": updated_vm.get('memory') if isinstance(updated_vm, dict) else getattr(updated_vm, 'memory', None),
                "disk_gb": updated_vm.get('disk') if isinstance(updated_vm, dict) else getattr(updated_vm, 'disk', None)
            }
        }
    }


@mcp_tool(category="virtualization")
def netbox_delete_virtual_machine(
    client: NetBoxClient,
    vm_id: int,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Delete a virtual machine from NetBox.
    
    Args:
        client: NetBoxClient instance (injected)
        vm_id: ID of the VM to delete
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Dict containing deletion confirmation
        
    Raises:
        ValidationError: If VM has assigned interfaces with IP addresses
    """
    
    # STEP 1: DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Virtual machine would be deleted. Set confirm=True to execute.",
            "would_delete": {
                "vm_id": vm_id
            }
        }
    
    # STEP 2: PARAMETER VALIDATION
    if not vm_id or vm_id <= 0:
        raise ValueError("vm_id must be a positive integer")
    
    # STEP 3: CHECK FOR DEPENDENCIES
    try:
        # Get VM info before deletion
        vm = client.virtualization.virtual_machines.get(vm_id)
        vm_name = vm.get('name') if isinstance(vm, dict) else vm.name
        
        # Check for VM interfaces with IP assignments
        vm_interfaces = list(client.virtualization.interfaces.filter(virtual_machine_id=vm_id))
        interfaces_with_ips = []
        
        for interface in vm_interfaces:
            interface_id = interface.get('id') if isinstance(interface, dict) else interface.id
            assigned_ips = list(client.ipam.ip_addresses.filter(assigned_object_id=interface_id))
            if assigned_ips:
                interface_name = interface.get('name') if isinstance(interface, dict) else getattr(interface, 'name', 'N/A')
                ip_count = len(assigned_ips)
                interfaces_with_ips.append(f"{interface_name} ({ip_count} IPs)")
        
        if interfaces_with_ips:
            raise ValueError(
                f"Cannot delete VM - interfaces with IP assignments found: {', '.join(interfaces_with_ips[:3])}" +
                ("..." if len(interfaces_with_ips) > 3 else "") +
                ". Remove IP assignments first."
            )
        
        # Check for virtual disks
        vm_disks = list(client.virtualization.virtual_disks.filter(virtual_machine_id=vm_id))
        if vm_disks:
            logger.info(f"VM has {len(vm_disks)} virtual disks that will be deleted along with the VM")
        
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Failed to validate VM for deletion: {e}")
    
    # STEP 4: DELETE VM
    try:
        client.virtualization.virtual_machines.delete(vm_id, confirm=confirm)
        
    except Exception as e:
        raise ValueError(f"NetBox API error during VM deletion: {e}")
    
    # STEP 5: RETURN SUCCESS
    return {
        "success": True,
        "message": f"Virtual machine '{vm_name}' (ID: {vm_id}) successfully deleted.",
        "data": {
            "deleted_vm_id": vm_id,
            "deleted_vm_name": vm_name
        }
    }