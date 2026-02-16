#!/usr/bin/env python3
"""
Virtualization Cluster Group Management Tools

High-level tools for managing NetBox virtualization cluster groups,
enabling hierarchical organization and management of virtualization clusters.
"""

from typing import Dict, Optional, Any, List
import logging
from ...registry import mcp_tool
from ...client import NetBoxClient

logger = logging.getLogger(__name__)


@mcp_tool(category="virtualization")
def netbox_create_cluster_group(
    client: NetBoxClient,
    name: str,
    slug: Optional[str] = None,
    description: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Create a new cluster group in NetBox virtualization.
    
    Cluster groups provide hierarchical organization for clusters, enabling
    logical grouping by location, department, or management structure.
    
    Args:
        client: NetBoxClient instance (injected)
        name: Cluster group name (e.g., "Production Clusters", "Development Environment")
        slug: URL-friendly identifier (auto-generated if not provided)
        description: Optional description of the cluster group
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Dict containing the created cluster group data
        
    Raises:
        ValidationError: If required parameters are missing or invalid
        ConflictError: If cluster group already exists
    """
    
    # STEP 1: DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Cluster group would be created. Set confirm=True to execute.",
            "would_create": {
                "name": name,
                "slug": slug or name.lower().replace(" ", "-"),
                "description": f"[NetBox-MCP] {description}" if description else ""
            }
        }
    
    # STEP 2: PARAMETER VALIDATION
    if not name or not name.strip():
        raise ValueError("name cannot be empty")
    
    # Generate slug if not provided
    if not slug:
        slug = name.lower().replace(" ", "-").replace("_", "-")
    
    # STEP 3: CONFLICT DETECTION
    try:
        # ULTRATHINK FIX 1: Expand parameters optimization for conflict detection
        existing_groups = list(client.virtualization.cluster_groups.filter(
            name=name,
            expand=["group"],  # Expand group relationships
            no_cache=True,
            limit=10
        ))
        
        if existing_groups:
            existing_group = existing_groups[0]
            existing_id = existing_group.get('id') if isinstance(existing_group, dict) else existing_group.id
            raise ValueError(f"Cluster group '{name}' already exists with ID {existing_id}")
            
    except ValueError:
        raise
    except Exception as e:
        logger.warning(f"Could not check for existing cluster groups: {e}")
    
    # STEP 4: CREATE CLUSTER GROUP
    create_payload = {
        "name": name,
        "slug": slug
    }
    
    if description:
        create_payload["description"] = f"[NetBox-MCP] {description}"
    
    try:
        new_cluster_group = client.virtualization.cluster_groups.create(confirm=confirm, **create_payload)
        
        # Apply defensive dict/object handling
        group_id = new_cluster_group.get('id') if isinstance(new_cluster_group, dict) else new_cluster_group.id
        group_name = new_cluster_group.get('name') if isinstance(new_cluster_group, dict) else new_cluster_group.name
        group_slug = new_cluster_group.get('slug') if isinstance(new_cluster_group, dict) else new_cluster_group.slug
        
    except Exception as e:
        raise ValueError(f"NetBox API error during cluster group creation: {e}")
    
    # STEP 5: RETURN SUCCESS
    return {
        "success": True,
        "message": f"Cluster group '{name}' successfully created.",
        "data": {
            "cluster_group_id": group_id,
            "name": group_name,
            "slug": group_slug,
            "description": new_cluster_group.get('description') if isinstance(new_cluster_group, dict) else getattr(new_cluster_group, 'description', None)
        }
    }


@mcp_tool(category="virtualization")
def netbox_get_cluster_group_info(
    client: NetBoxClient,
    name: Optional[str] = None,
    slug: Optional[str] = None,
    cluster_group_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get detailed information about a specific cluster group.
    
    Args:
        client: NetBoxClient instance (injected)
        name: Cluster group name to retrieve
        slug: Cluster group slug to retrieve
        cluster_group_id: Cluster group ID to retrieve
        
    Returns:
        Dict containing detailed cluster group information including cluster count
        
    Raises:
        ValidationError: If no valid identifier provided
        NotFoundError: If cluster group not found
    """
    
    if not any([name, slug, cluster_group_id]):
        raise ValueError("Either 'name', 'slug', or 'cluster_group_id' must be provided")
    
    try:
        if cluster_group_id:
            cluster_group = client.virtualization.cluster_groups.get(cluster_group_id)
        elif name:
            # ULTRATHINK FIX 1: Expand parameters optimization for cluster group lookup
            cluster_groups = list(client.virtualization.cluster_groups.filter(
                name=name,
                expand=["group"],  # Expand group relationships
                limit=10
            ))
            if not cluster_groups:
                raise ValueError(f"Cluster group '{name}' not found")
            cluster_group = cluster_groups[0]
        else:  # slug
            # ULTRATHINK FIX 4: Slug-based fallback with expand parameters
            cluster_groups = list(client.virtualization.cluster_groups.filter(
                slug=slug,
                expand=["group"],  # Expand group relationships
                limit=10
            ))
            if not cluster_groups:
                raise ValueError(f"Cluster group with slug '{slug}' not found")
            cluster_group = cluster_groups[0]
        
        # Apply defensive dict/object handling
        group_id = cluster_group.get('id') if isinstance(cluster_group, dict) else cluster_group.id
        group_name = cluster_group.get('name') if isinstance(cluster_group, dict) else cluster_group.name
        group_slug = cluster_group.get('slug') if isinstance(cluster_group, dict) else cluster_group.slug
        group_description = cluster_group.get('description') if isinstance(cluster_group, dict) else getattr(cluster_group, 'description', None)
        
        # Get cluster count for this group
        # ULTRATHINK FIX 1: Expand parameters optimization for cluster counting
        cluster_count = len(list(client.virtualization.clusters.filter(
            group_id=group_id,
            expand=["group", "type"],  # Expand group and type relationships
            limit=500
            )))
        
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Failed to retrieve cluster group: {e}")
    
    return {
        "success": True,
        "message": f"Retrieved cluster group '{group_name}'.",
        "data": {
            "id": group_id,
            "name": group_name,
            "slug": group_slug,
            "description": group_description,
            "cluster_count": cluster_count,
            "url": cluster_group.get('url') if isinstance(cluster_group, dict) else getattr(cluster_group, 'url', None)
        }
    }


@mcp_tool(category="virtualization")
def netbox_list_all_cluster_groups(
    client: NetBoxClient,
    name_filter: Optional[str] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Get comprehensive list of all cluster groups with filtering capabilities.
    
    This tool provides bulk cluster group discovery across the virtualization infrastructure,
    enabling efficient organizational analysis and hierarchical management.
    
    Args:
        client: NetBoxClient instance (injected)
        name_filter: Filter by cluster group name (partial match)
        limit: Maximum number of cluster groups to return (default: 100)
        
    Returns:
        Dict containing summary list of cluster groups with statistics
    """
    
    # Build filter parameters
    filter_params = {}
    if name_filter:
        filter_params["name__icontains"] = name_filter
    
    try:
        # Get cluster groups with applied filters
        # ULTRATHINK FIX 1: Expand parameters optimization for bulk cluster groups discovery
        cluster_groups = list(client.virtualization.cluster_groups.filter(
            expand=["group"],  # Expand group relationships
            limit=limit,
            **filter_params
        ))
        
        # Process cluster groups with defensive dict/object handling
        groups_summary = []
        total_clusters = 0
        
        for cluster_group in cluster_groups:
            group_id = cluster_group.get('id') if isinstance(cluster_group, dict) else cluster_group.id
            group_name = cluster_group.get('name') if isinstance(cluster_group, dict) else cluster_group.name
            group_slug = cluster_group.get('slug') if isinstance(cluster_group, dict) else cluster_group.slug
            group_description = cluster_group.get('description') if isinstance(cluster_group, dict) else getattr(cluster_group, 'description', None)
            
            # Count clusters for this group
            # ULTRATHINK FIX 1: Expand parameters optimization for cluster counting
            cluster_count = len(list(client.virtualization.clusters.filter(
                group_id=group_id,
                expand=["group", "type"],  # Expand group and type relationships
                limit=500
                )))
            total_clusters += cluster_count
            
            groups_summary.append({
                "id": group_id,
                "name": group_name,
                "slug": group_slug,
                "description": group_description,
                "cluster_count": cluster_count
            })
            
    except Exception as e:
        raise ValueError(f"Failed to retrieve cluster groups: {e}")
    
    return {
        "success": True,
        "message": f"Found {len(groups_summary)} cluster groups.",
        "total_cluster_groups": len(groups_summary),
        "total_clusters": total_clusters,
        "applied_filters": {
            "name_filter": name_filter,
            "limit": limit
        },
        "data": groups_summary
    }


@mcp_tool(category="virtualization")
def netbox_update_cluster_group(
    client: NetBoxClient,
    cluster_group_id: int,
    name: Optional[str] = None,
    slug: Optional[str] = None,
    description: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Update an existing cluster group in NetBox.
    
    Args:
        client: NetBoxClient instance (injected)
        cluster_group_id: ID of the cluster group to update
        name: New name for the cluster group
        slug: New slug for the cluster group
        description: New description for the cluster group
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Dict containing the updated cluster group data
    """
    
    # STEP 1: DRY RUN CHECK
    if not confirm:
        update_fields = {}
        if name: update_fields["name"] = name
        if slug: update_fields["slug"] = slug
        if description: update_fields["description"] = f"[NetBox-MCP] {description}"
        
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Cluster group would be updated. Set confirm=True to execute.",
            "would_update": {
                "cluster_group_id": cluster_group_id,
                "fields": update_fields
            }
        }
    
    # STEP 2: PARAMETER VALIDATION
    if not cluster_group_id or cluster_group_id <= 0:
        raise ValueError("cluster_group_id must be a positive integer")
    
    if not any([name, slug, description]):
        raise ValueError("At least one field (name, slug, description) must be provided for update")
    
    # STEP 3: BUILD UPDATE PAYLOAD
    update_payload = {}
    if name:
        if not name.strip():
            raise ValueError("name cannot be empty")
        update_payload["name"] = name
    
    if slug:
        if not slug.strip():
            raise ValueError("slug cannot be empty")
        update_payload["slug"] = slug
    
    if description is not None:
        update_payload["description"] = f"[NetBox-MCP] {description}" if description else ""
    
    # STEP 4: UPDATE CLUSTER GROUP
    try:
        updated_cluster_group = client.virtualization.cluster_groups.update(cluster_group_id, confirm=confirm, **update_payload)
        
        # Apply defensive dict/object handling
        group_id = updated_cluster_group.get('id') if isinstance(updated_cluster_group, dict) else updated_cluster_group.id
        group_name = updated_cluster_group.get('name') if isinstance(updated_cluster_group, dict) else updated_cluster_group.name
        group_slug = updated_cluster_group.get('slug') if isinstance(updated_cluster_group, dict) else updated_cluster_group.slug
        
    except Exception as e:
        raise ValueError(f"NetBox API error during cluster group update: {e}")
    
    # STEP 5: RETURN SUCCESS
    return {
        "success": True,
        "message": f"Cluster group ID {cluster_group_id} successfully updated.",
        "data": {
            "cluster_group_id": group_id,
            "name": group_name,
            "slug": group_slug,
            "description": updated_cluster_group.get('description') if isinstance(updated_cluster_group, dict) else getattr(updated_cluster_group, 'description', None)
        }
    }


@mcp_tool(category="virtualization")
def netbox_delete_cluster_group(
    client: NetBoxClient,
    cluster_group_id: int,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Delete a cluster group from NetBox.
    
    Args:
        client: NetBoxClient instance (injected)
        cluster_group_id: ID of the cluster group to delete
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Dict containing deletion confirmation
        
    Raises:
        ValidationError: If cluster group has associated clusters
    """
    
    # STEP 1: DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Cluster group would be deleted. Set confirm=True to execute.",
            "would_delete": {
                "cluster_group_id": cluster_group_id
            }
        }
    
    # STEP 2: PARAMETER VALIDATION
    if not cluster_group_id or cluster_group_id <= 0:
        raise ValueError("cluster_group_id must be a positive integer")
    
    # STEP 3: CHECK FOR DEPENDENCIES
    try:
        # Check if cluster group has associated clusters
        # ULTRATHINK FIX 1: Expand parameters optimization for dependency checking
        associated_clusters = list(client.virtualization.clusters.filter(
            group_id=cluster_group_id,
            expand=["group", "type"],  # Expand group and type relationships
            limit=500
        ))
        if associated_clusters:
            cluster_names = []
            for cluster in associated_clusters[:5]:  # Show first 5
                cluster_name = cluster.get('name') if isinstance(cluster, dict) else cluster.name
                cluster_names.append(cluster_name)
            
            raise ValueError(
                f"Cannot delete cluster group - {len(associated_clusters)} associated clusters found: "
                f"{', '.join(cluster_names)}" + 
                ("..." if len(associated_clusters) > 5 else "")
            )
        
        # Get cluster group info before deletion
        cluster_group = client.virtualization.cluster_groups.get(cluster_group_id)
        group_name = cluster_group.get('name') if isinstance(cluster_group, dict) else cluster_group.name
        
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Failed to validate cluster group for deletion: {e}")
    
    # STEP 4: DELETE CLUSTER GROUP
    try:
        client.virtualization.cluster_groups.delete(cluster_group_id, confirm=confirm)
        
    except Exception as e:
        raise ValueError(f"NetBox API error during cluster group deletion: {e}")
    
    # STEP 5: RETURN SUCCESS
    return {
        "success": True,
        "message": f"Cluster group '{group_name}' (ID: {cluster_group_id}) successfully deleted.",
        "data": {
            "deleted_cluster_group_id": cluster_group_id,
            "deleted_cluster_group_name": group_name
        }
    }