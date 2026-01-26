#!/usr/bin/env python3
"""
Virtualization Cluster Management Tools

High-level tools for managing NetBox virtualization clusters with comprehensive
cluster lifecycle management, resource allocation, and performance monitoring.
"""

from typing import Dict, Optional, Any, List
import logging
from ...registry import mcp_tool
from ...client import NetBoxClient

logger = logging.getLogger(__name__)


@mcp_tool(category="virtualization")
def netbox_create_cluster(
    client: NetBoxClient,
    name: str,
    cluster_type: str,
    site: Optional[str] = None,
    cluster_group: Optional[str] = None,
    status: str = "active",
    description: Optional[str] = None,
    comments: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Create a new virtualization cluster in NetBox.
    
    Clusters represent virtualization infrastructure groupings that host virtual machines,
    providing centralized management and resource allocation capabilities.
    
    Args:
        client: NetBoxClient instance (injected)
        name: Cluster name (e.g., "Production-VMware-Cluster-01")
        cluster_type: Cluster type name (e.g., "VMware vSphere", "Microsoft Hyper-V")
        site: Site where the cluster is located
        cluster_group: Optional cluster group for organization
        status: Cluster status (active, planned, staged, decommissioning, offline)
        description: Optional description of the cluster
        comments: Additional comments
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Dict containing the created cluster data
        
    Raises:
        ValidationError: If required parameters are missing or invalid
        NotFoundError: If cluster type or site not found
        ConflictError: If cluster already exists
    """
    
    # STEP 1: DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Cluster would be created. Set confirm=True to execute.",
            "would_create": {
                "name": name,
                "cluster_type": cluster_type,
                "site": site,
                "cluster_group": cluster_group,
                "status": status,
                "description": f"[NetBox-MCP] {description}" if description else "",
                "comments": f"[NetBox-MCP] {comments}" if comments else ""
            }
        }
    
    # STEP 2: PARAMETER VALIDATION
    if not name or not name.strip():
        raise ValueError("name cannot be empty")
    
    if not cluster_type or not cluster_type.strip():
        raise ValueError("cluster_type cannot be empty")
    
    # STEP 3: LOOKUP CLUSTER TYPE
    try:
        # ULTRATHINK FIX 1: Expand parameters optimization for cluster type lookup
        cluster_types = list(client.virtualization.cluster_types.filter(
            name=cluster_type,
            expand=["type"],  # Expand type relationships
            limit=10
        ))
        if not cluster_types:
            raise ValueError(f"Cluster type '{cluster_type}' not found")
        
        cluster_type_obj = cluster_types[0]
        cluster_type_id = cluster_type_obj.get('id') if isinstance(cluster_type_obj, dict) else cluster_type_obj.id
        cluster_type_display = cluster_type_obj.get('display', cluster_type) if isinstance(cluster_type_obj, dict) else getattr(cluster_type_obj, 'display', cluster_type)
        
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Could not find cluster type '{cluster_type}': {e}")
    
    # STEP 4: LOOKUP SITE (if provided)
    site_id = None
    if site:
        try:
            sites = client.dcim.sites.filter(name=site)
            if not sites:
                raise ValueError(f"Site '{site}' not found")
            
            site_obj = sites[0]
            site_id = site_obj.get('id') if isinstance(site_obj, dict) else site_obj.id
            
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Could not find site '{site}': {e}")
    
    # STEP 5: LOOKUP CLUSTER GROUP (if provided)
    cluster_group_id = None
    if cluster_group:
        try:
            # ULTRATHINK FIX 1: Expand parameters optimization for cluster group lookup
            cluster_groups = list(client.virtualization.cluster_groups.filter(
                name=cluster_group,
                expand=["group"],  # Expand group relationships
                limit=10
            ))
            if not cluster_groups:
                raise ValueError(f"Cluster group '{cluster_group}' not found")
            
            cluster_group_obj = cluster_groups[0]
            cluster_group_id = cluster_group_obj.get('id') if isinstance(cluster_group_obj, dict) else cluster_group_obj.id
            
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Could not find cluster group '{cluster_group}': {e}")
    
    # STEP 6: CONFLICT DETECTION
    try:
        # ULTRATHINK FIX 1: Expand parameters optimization for conflict detection
        existing_clusters = list(client.virtualization.clusters.filter(
            name=name,
            expand=["group", "type", "site"],  # Expand relationships
            no_cache=True,
            limit=10
        ))
        
        if existing_clusters:
            existing_cluster = existing_clusters[0]
            existing_id = existing_cluster.get('id') if isinstance(existing_cluster, dict) else existing_cluster.id
            raise ValueError(f"Cluster '{name}' already exists with ID {existing_id}")
            
    except ValueError:
        raise
    except Exception as e:
        logger.warning(f"Could not check for existing clusters: {e}")
    
    # STEP 7: CREATE CLUSTER
    create_payload = {
        "name": name,
        "type": cluster_type_id,
        "status": status
    }
    
    if site_id:
        create_payload["site"] = site_id
    
    if cluster_group_id:
        create_payload["group"] = cluster_group_id
    
    if description:
        create_payload["description"] = f"[NetBox-MCP] {description}"
    
    if comments:
        create_payload["comments"] = f"[NetBox-MCP] {comments}"
    
    try:
        new_cluster = client.virtualization.clusters.create(confirm=confirm, **create_payload)
        
        # Apply defensive dict/object handling
        cluster_id = new_cluster.get('id') if isinstance(new_cluster, dict) else new_cluster.id
        cluster_name = new_cluster.get('name') if isinstance(new_cluster, dict) else new_cluster.name
        cluster_status = new_cluster.get('status') if isinstance(new_cluster, dict) else getattr(new_cluster, 'status', None)
        
    except Exception as e:
        raise ValueError(f"NetBox API error during cluster creation: {e}")
    
    # STEP 8: RETURN SUCCESS
    return {
        "success": True,
        "message": f"Cluster '{name}' successfully created.",
        "data": {
            "cluster_id": cluster_id,
            "name": cluster_name,
            "cluster_type": cluster_type,
            "site": site,
            "cluster_group": cluster_group,
            "status": cluster_status,
            "description": new_cluster.get('description') if isinstance(new_cluster, dict) else getattr(new_cluster, 'description', None)
        }
    }


@mcp_tool(category="virtualization")
def netbox_get_cluster_info(
    client: NetBoxClient,
    name: Optional[str] = None,
    cluster_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get detailed information about a specific cluster.
    
    Args:
        client: NetBoxClient instance (injected)
        name: Cluster name to retrieve
        cluster_id: Cluster ID to retrieve
        
    Returns:
        Dict containing detailed cluster information including VM count and capacity
        
    Raises:
        ValidationError: If no valid identifier provided
        NotFoundError: If cluster not found
    """
    
    if not any([name, cluster_id]):
        raise ValueError("Either 'name' or 'cluster_id' must be provided")
    
    try:
        if cluster_id:
            cluster = client.virtualization.clusters.get(cluster_id)
        else:  # name
            # ULTRATHINK FIX 1: Expand parameters optimization for cluster lookup by name
            clusters = list(client.virtualization.clusters.filter(
                name=name,
                expand=["group", "type", "site"],  # Expand relationships
                limit=10
            ))
            if not clusters:
                raise ValueError(f"Cluster '{name}' not found")
            cluster = clusters[0]
        
        # Apply defensive dict/object handling
        cluster_id = cluster.get('id') if isinstance(cluster, dict) else cluster.id
        cluster_name = cluster.get('name') if isinstance(cluster, dict) else cluster.name
        cluster_status = cluster.get('status') if isinstance(cluster, dict) else getattr(cluster, 'status', None)
        cluster_description = cluster.get('description') if isinstance(cluster, dict) else getattr(cluster, 'description', None)
        cluster_comments = cluster.get('comments') if isinstance(cluster, dict) else getattr(cluster, 'comments', None)
        
        # Get cluster type information - with proper resolution
        cluster_type_obj = cluster.get('type') if isinstance(cluster, dict) else getattr(cluster, 'type', None)
        if isinstance(cluster_type_obj, dict):
            cluster_type_id = cluster_type_obj.get('id')
            cluster_type_name = cluster_type_obj.get('name', 'N/A')
        else:
            cluster_type_id = getattr(cluster_type_obj, 'id', None) if cluster_type_obj else None
            cluster_type_name = getattr(cluster_type_obj, 'name', None) if cluster_type_obj else None
        
        # If we don't have proper cluster type name, fetch it directly
        if not cluster_type_name or cluster_type_name == 'N/A' or str(cluster_type_name).isdigit():
            try:
                if cluster_type_id and cluster_type_id != 'N/A':
                    # ULTRATHINK FIX 1: Get with optimized cache access for cluster type details
                    cluster_type_full = client.virtualization.cluster_types.get(cluster_type_id)
                    cluster_type_name = cluster_type_full.get('name') if isinstance(cluster_type_full, dict) else cluster_type_full.name
                    logger.debug(f"Fetched cluster type name from API: {cluster_type_name} for ID {cluster_type_id}")
                else:
                    cluster_type_name = 'N/A'
            except Exception as e:
                logger.warning(f"Failed to fetch cluster type name for ID {cluster_type_id}: {e}")
                cluster_type_name = 'N/A'
        
        # Get site information - with proper resolution
        site_obj = cluster.get('site') if isinstance(cluster, dict) else getattr(cluster, 'site', None)
        if isinstance(site_obj, dict):
            site_id = site_obj.get('id')
            site_name = site_obj.get('name', 'N/A')
        else:
            site_id = getattr(site_obj, 'id', None) if site_obj else None
            site_name = getattr(site_obj, 'name', None) if site_obj else None
        
        # If we don't have proper site name, fetch it directly
        if not site_name or site_name == 'N/A' or str(site_name).isdigit():
            try:
                if site_id and site_id != 'N/A':
                    site_full = client.dcim.sites.get(site_id)
                    site_name = site_full.get('name') if isinstance(site_full, dict) else site_full.name
                    logger.debug(f"Fetched site name from API: {site_name} for ID {site_id}")
                else:
                    site_name = 'N/A'
            except Exception as e:
                logger.warning(f"Failed to fetch site name for ID {site_id}: {e}")
                site_name = 'N/A'
        
        # Get cluster group information - with proper resolution
        group_obj = cluster.get('group') if isinstance(cluster, dict) else getattr(cluster, 'group', None)
        if isinstance(group_obj, dict):
            group_id = group_obj.get('id')
            group_name = group_obj.get('name', 'N/A')
        else:
            group_id = getattr(group_obj, 'id', None) if group_obj else None
            group_name = getattr(group_obj, 'name', None) if group_obj else None
        
        # If we don't have proper group name, fetch it directly
        if not group_name or group_name == 'N/A' or str(group_name).isdigit():
            try:
                if group_id and group_id != 'N/A':
                    # ULTRATHINK FIX 1: Get with optimized cache access for cluster group details
                    group_full = client.virtualization.cluster_groups.get(group_id)
                    group_name = group_full.get('name') if isinstance(group_full, dict) else group_full.name
                    logger.debug(f"Fetched cluster group name from API: {group_name} for ID {group_id}")
                else:
                    group_name = 'N/A'
            except Exception as e:
                logger.warning(f"Failed to fetch cluster group name for ID {group_id}: {e}")
                group_name = 'N/A'
        
        # Get virtual machine count and statistics
        try:
            # ULTRATHINK FIX 1: Expand parameters optimization for VM retrieval
            virtual_machines = list(client.virtualization.virtual_machines.filter(
                cluster_id=cluster_id,
                expand=["cluster", "role", "platform"],  # Expand cluster and related data
                limit=500
            ))
            vm_count = len(virtual_machines)
            
            # Calculate VM statistics
            vm_stats = {"active": 0, "offline": 0, "planned": 0, "staged": 0}
            total_vcpus = 0
            total_memory_mb = 0
            total_disk_gb = 0
            
            for vm in virtual_machines:
                vm_status = vm.get('status') if isinstance(vm, dict) else getattr(vm, 'status', {})
                if isinstance(vm_status, dict):
                    status_value = vm_status.get('value', 'unknown')
                else:
                    status_value = str(vm_status) if vm_status else 'unknown'
                
                vm_stats[status_value] = vm_stats.get(status_value, 0) + 1
                
                # Accumulate resources
                vcpus = vm.get('vcpus') if isinstance(vm, dict) else getattr(vm, 'vcpus', 0)
                memory = vm.get('memory') if isinstance(vm, dict) else getattr(vm, 'memory', 0)
                disk = vm.get('disk') if isinstance(vm, dict) else getattr(vm, 'disk', 0)
                
                total_vcpus += vcpus or 0
                total_memory_mb += memory or 0
                total_disk_gb += round(disk / 1024, 2) if disk else 0
                
        except Exception:
            vm_count = 0
            vm_stats = {}
            total_vcpus = 0
            total_memory_mb = 0
            total_disk_gb = 0
        
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Failed to retrieve cluster: {e}")
    
    return {
        "success": True,
        "message": f"Retrieved cluster '{cluster_name}'.",
        "data": {
            "cluster_id": cluster_id,
            "name": cluster_name,
            "type": cluster_type_name,
            "site": site_name,
            "group": group_name,
            "status": cluster_status,
            "description": cluster_description,
            "comments": cluster_comments,
            "virtual_machines": {
                "count": vm_count,
                "status_breakdown": vm_stats,
                "total_resources": {
                    "vcpus": total_vcpus,
                    "memory_mb": total_memory_mb,
                    "memory_gb": round(total_memory_mb / 1024, 2) if total_memory_mb else 0,
                    "disk_gb": round(total_disk_gb, 2)
                }
            },
            "url": cluster.get('url') if isinstance(cluster, dict) else getattr(cluster, 'url', None)
        }
    }


@mcp_tool(category="virtualization")
def netbox_list_all_clusters(
    client: NetBoxClient,
    cluster_type: Optional[str] = None,
    site: Optional[str] = None,
    cluster_group: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Get comprehensive list of all clusters with filtering capabilities.
    
    This tool provides bulk cluster discovery across the virtualization infrastructure,
    enabling efficient capacity planning and cluster management.
    
    Args:
        client: NetBoxClient instance (injected)
        cluster_type: Filter by cluster type name
        site: Filter by site name
        cluster_group: Filter by cluster group name
        status: Filter by status (active, planned, staged, etc.)
        limit: Maximum number of clusters to return (default: 100)
        
    Returns:
        Dict containing summary list of clusters with resource statistics
    """
    
    # Build filter parameters
    filter_params = {}
    
    if cluster_type:
        try:
            # ULTRATHINK FIX 1: Expand parameters optimization for cluster type lookup in bulk listing
            cluster_types = list(client.virtualization.cluster_types.filter(
                name=cluster_type,
                expand=["type"],  # Expand type relationships
                limit=10
            ))
            if not cluster_types:
                raise ValueError(f"Cluster type '{cluster_type}' not found")
            cluster_type_obj = cluster_types[0]
            cluster_type_id = cluster_type_obj.get('id') if isinstance(cluster_type_obj, dict) else cluster_type_obj.id
            filter_params["type_id"] = cluster_type_id
        except Exception as e:
            raise ValueError(f"Failed to find cluster type: {e}")
    
    if site:
        try:
            sites = client.dcim.sites.filter(name=site)
            if not sites:
                raise ValueError(f"Site '{site}' not found")
            site_obj = sites[0]
            site_id = site_obj.get('id') if isinstance(site_obj, dict) else site_obj.id
            filter_params["site_id"] = site_id
        except Exception as e:
            raise ValueError(f"Failed to find site: {e}")
    
    if cluster_group:
        try:
            # ULTRATHINK FIX 1: Expand parameters optimization for cluster group lookup in bulk listing
            cluster_groups = list(client.virtualization.cluster_groups.filter(
                name=cluster_group,
                expand=["group"],  # Expand group relationships
                limit=10
            ))
            if not cluster_groups:
                raise ValueError(f"Cluster group '{cluster_group}' not found")
            group_obj = cluster_groups[0]
            group_id = group_obj.get('id') if isinstance(group_obj, dict) else group_obj.id
            filter_params["group_id"] = group_id
        except Exception as e:
            raise ValueError(f"Failed to find cluster group: {e}")
    
    if status:
        filter_params["status"] = status
    
    try:
        # Get clusters with applied filters
        # ULTRATHINK FIX 1: Expand parameters optimization for bulk cluster discovery
        clusters = list(client.virtualization.clusters.filter(
            expand=["group", "type", "site"],  # Expand relationships
            limit=limit,
            **filter_params
        ))
        
        # Process clusters with defensive dict/object handling
        clusters_summary = []
        total_vms = 0
        total_vcpus = 0
        total_memory_gb = 0
        total_disk_gb = 0
        status_counts = {}
        
        for cluster in clusters:
            cluster_id = cluster.get('id') if isinstance(cluster, dict) else cluster.id
            cluster_name = cluster.get('name') if isinstance(cluster, dict) else cluster.name
            cluster_status = cluster.get('status') if isinstance(cluster, dict) else getattr(cluster, 'status', None)
            
            # Count by status
            if isinstance(cluster_status, dict):
                status_value = cluster_status.get('value', 'unknown')
            else:
                status_value = str(cluster_status) if cluster_status else 'unknown'
            status_counts[status_value] = status_counts.get(status_value, 0) + 1
            
            # Get cluster type, site, and group names
            cluster_type_obj = cluster.get('type') if isinstance(cluster, dict) else getattr(cluster, 'type', None)
            if isinstance(cluster_type_obj, dict):
                cluster_type_name = cluster_type_obj.get('name', 'N/A')
            else:
                cluster_type_name = str(cluster_type_obj) if cluster_type_obj else 'N/A'
            
            site_obj = cluster.get('site') if isinstance(cluster, dict) else getattr(cluster, 'site', None)
            if isinstance(site_obj, dict):
                site_name = site_obj.get('name', 'N/A')
            else:
                site_name = str(site_obj) if site_obj else 'N/A'
            
            group_obj = cluster.get('group') if isinstance(cluster, dict) else getattr(cluster, 'group', None)
            if isinstance(group_obj, dict):
                group_name = group_obj.get('name', 'N/A')
            else:
                group_name = str(group_obj) if group_obj else 'N/A'
            
            # Count VMs for this cluster
            try:
                # ULTRATHINK FIX 1: Expand parameters optimization for cluster VM retrieval in bulk listing
                cluster_vms = list(client.virtualization.virtual_machines.filter(
                    cluster_id=cluster_id,
                    expand=["cluster", "role", "platform"],  # Expand cluster and related data
                    limit=500
                ))
                vm_count = len(cluster_vms)
                total_vms += vm_count
                
                # Calculate resource totals for this cluster
                cluster_vcpus = sum(vm.get('vcpus', 0) if isinstance(vm, dict) else getattr(vm, 'vcpus', 0) for vm in cluster_vms)
                cluster_memory_mb = sum(vm.get('memory', 0) if isinstance(vm, dict) else getattr(vm, 'memory', 0) for vm in cluster_vms)
                cluster_memory_gb = round(cluster_memory_mb / 1024, 2) if cluster_memory_mb else 0
                cluster_disk_gb = sum((vm.get('disk', 0) if isinstance(vm, dict) else getattr(vm, 'disk', 0)) / 1024 if (vm.get('disk', 0) if isinstance(vm, dict) else getattr(vm, 'disk', 0)) else 0 for vm in cluster_vms)
                
                total_vcpus += cluster_vcpus
                total_memory_gb += cluster_memory_gb
                total_disk_gb += cluster_disk_gb
                
            except Exception:
                vm_count = 0
                cluster_vcpus = 0
                cluster_memory_gb = 0
                cluster_disk_gb = 0
            
            clusters_summary.append({
                "id": cluster_id,
                "name": cluster_name,
                "type": cluster_type_name,
                "site": site_name,
                "group": group_name,
                "status": status_value,
                "vm_count": vm_count,
                "vcpus": cluster_vcpus,
                "memory_gb": round(cluster_memory_gb, 2),
                "disk_gb": round(cluster_disk_gb, 2)
            })
            
    except Exception as e:
        raise ValueError(f"Failed to retrieve clusters: {e}")
    
    return {
        "success": True,
        "message": f"Found {len(clusters_summary)} clusters.",
        "total_clusters": len(clusters_summary),
        "total_virtual_machines": total_vms,
        "resource_totals": {
            "total_vcpus": total_vcpus,
            "total_memory_gb": round(total_memory_gb, 2),
            "total_disk_gb": round(total_disk_gb, 2)
        },
        "status_distribution": status_counts,
        "applied_filters": {
            "cluster_type": cluster_type,
            "site": site,
            "cluster_group": cluster_group,
            "status": status,
            "limit": limit
        },
        "data": clusters_summary
    }


@mcp_tool(category="virtualization")
def netbox_update_cluster(
    client: NetBoxClient,
    cluster_id: int,
    name: Optional[str] = None,
    site: Optional[str] = None,
    cluster_group: Optional[str] = None,
    status: Optional[str] = None,
    description: Optional[str] = None,
    comments: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Update an existing cluster in NetBox.
    
    Args:
        client: NetBoxClient instance (injected)
        cluster_id: ID of the cluster to update
        name: New name for the cluster
        site: New site assignment
        cluster_group: New cluster group assignment
        status: New status
        description: New description
        comments: New comments
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Dict containing the updated cluster data
    """
    
    # STEP 1: DRY RUN CHECK
    if not confirm:
        update_fields = {}
        if name: update_fields["name"] = name
        if site: update_fields["site"] = site
        if cluster_group: update_fields["cluster_group"] = cluster_group
        if status: update_fields["status"] = status
        if description: update_fields["description"] = f"[NetBox-MCP] {description}"
        if comments: update_fields["comments"] = f"[NetBox-MCP] {comments}"
        
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Cluster would be updated. Set confirm=True to execute.",
            "would_update": {
                "cluster_id": cluster_id,
                "fields": update_fields
            }
        }
    
    # STEP 2: PARAMETER VALIDATION
    if not cluster_id or cluster_id <= 0:
        raise ValueError("cluster_id must be a positive integer")
    
    if not any([name, site, cluster_group, status, description is not None, comments is not None]):
        raise ValueError("At least one field must be provided for update")
    
    # STEP 3: BUILD UPDATE PAYLOAD
    update_payload = {}
    
    if name:
        if not name.strip():
            raise ValueError("name cannot be empty")
        update_payload["name"] = name
    
    if site:
        try:
            sites = client.dcim.sites.filter(name=site)
            if not sites:
                raise ValueError(f"Site '{site}' not found")
            site_obj = sites[0]
            site_id = site_obj.get('id') if isinstance(site_obj, dict) else site_obj.id
            update_payload["site"] = site_id
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Could not find site '{site}': {e}")
    
    if cluster_group:
        try:
            # ULTRATHINK FIX 1: Expand parameters optimization for cluster group lookup in update function
            cluster_groups = list(client.virtualization.cluster_groups.filter(
                name=cluster_group,
                expand=["group"],  # Expand group relationships
                limit=10
            ))
            if not cluster_groups:
                raise ValueError(f"Cluster group '{cluster_group}' not found")
            group_obj = cluster_groups[0]
            group_id = group_obj.get('id') if isinstance(group_obj, dict) else group_obj.id
            update_payload["group"] = group_id
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Could not find cluster group '{cluster_group}': {e}")
    
    if status:
        update_payload["status"] = status
    
    if description is not None:
        update_payload["description"] = f"[NetBox-MCP] {description}" if description else ""
    
    if comments is not None:
        update_payload["comments"] = f"[NetBox-MCP] {comments}" if comments else ""
    
    # STEP 4: UPDATE CLUSTER
    try:
        updated_cluster = client.virtualization.clusters.update(cluster_id, confirm=confirm, **update_payload)
        
        # Apply defensive dict/object handling
        cluster_id_updated = updated_cluster.get('id') if isinstance(updated_cluster, dict) else updated_cluster.id
        cluster_name_updated = updated_cluster.get('name') if isinstance(updated_cluster, dict) else updated_cluster.name
        cluster_status_updated = updated_cluster.get('status') if isinstance(updated_cluster, dict) else getattr(updated_cluster, 'status', None)
        
    except Exception as e:
        raise ValueError(f"NetBox API error during cluster update: {e}")
    
    # STEP 5: RETURN SUCCESS
    return {
        "success": True,
        "message": f"Cluster ID {cluster_id} successfully updated.",
        "data": {
            "cluster_id": cluster_id_updated,
            "name": cluster_name_updated,
            "status": cluster_status_updated,
            "description": updated_cluster.get('description') if isinstance(updated_cluster, dict) else getattr(updated_cluster, 'description', None)
        }
    }


@mcp_tool(category="virtualization")
def netbox_delete_cluster(
    client: NetBoxClient,
    cluster_id: int,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Delete a cluster from NetBox.
    
    Args:
        client: NetBoxClient instance (injected)
        cluster_id: ID of the cluster to delete
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Dict containing deletion confirmation
        
    Raises:
        ValidationError: If cluster has assigned virtual machines
    """
    
    # STEP 1: DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Cluster would be deleted. Set confirm=True to execute.",
            "would_delete": {
                "cluster_id": cluster_id
            }
        }
    
    # STEP 2: PARAMETER VALIDATION
    if not cluster_id or cluster_id <= 0:
        raise ValueError("cluster_id must be a positive integer")
    
    # STEP 3: CHECK FOR DEPENDENCIES
    try:
        # Check if cluster has assigned virtual machines
        # ULTRATHINK FIX 1: Expand parameters optimization for VM dependency checking in delete function
        assigned_vms = list(client.virtualization.virtual_machines.filter(
            cluster_id=cluster_id,
            expand=["cluster", "role", "platform"],  # Expand cluster and related data
            limit=500
        ))
        if assigned_vms:
            vm_names = []
            for vm in assigned_vms[:5]:  # Show first 5
                vm_name = vm.get('name') if isinstance(vm, dict) else getattr(vm, 'name', 'N/A')
                vm_names.append(vm_name)
            
            raise ValueError(
                f"Cannot delete cluster - {len(assigned_vms)} assigned virtual machines found: "
                f"{', '.join(vm_names)}" + 
                ("..." if len(assigned_vms) > 5 else "")
            )
        
        # Get cluster info before deletion
        # ULTRATHINK FIX 1: Get with optimized cache access for cluster details before deletion
        cluster = client.virtualization.clusters.get(cluster_id)
        cluster_name = cluster.get('name') if isinstance(cluster, dict) else cluster.name
        
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Failed to validate cluster for deletion: {e}")
    
    # STEP 4: DELETE CLUSTER
    try:
        # ULTRATHINK FIX 1: Delete with optimized API access
        client.virtualization.clusters.delete(cluster_id, confirm=confirm)
        
    except Exception as e:
        raise ValueError(f"NetBox API error during cluster deletion: {e}")
    
    # STEP 5: RETURN SUCCESS
    return {
        "success": True,
        "message": f"Cluster '{cluster_name}' (ID: {cluster_id}) successfully deleted.",
        "data": {
            "deleted_cluster_id": cluster_id,
            "deleted_cluster_name": cluster_name
        }
    }