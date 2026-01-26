#!/usr/bin/env python3
"""
Virtualization Cluster Type Management Tools

High-level tools for managing NetBox virtualization cluster types,
enabling standardized cluster categorization and management.
"""

from typing import Dict, Optional, Any, List
import logging
from ...registry import mcp_tool
from ...client import NetBoxClient

logger = logging.getLogger(__name__)


@mcp_tool(category="virtualization")
def netbox_create_cluster_type(
    client: NetBoxClient,
    name: str,
    slug: Optional[str] = None,
    description: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Create a new cluster type in NetBox virtualization.
    
    Cluster types categorize clusters by their virtualization platform or technology
    (e.g., VMware vSphere, Microsoft Hyper-V, KVM, etc.).
    
    Args:
        client: NetBoxClient instance (injected)
        name: Cluster type name (e.g., "VMware vSphere", "Microsoft Hyper-V")
        slug: URL-friendly identifier (auto-generated if not provided)
        description: Optional description of the cluster type
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Dict containing the created cluster type data
        
    Raises:
        ValidationError: If required parameters are missing or invalid
        ConflictError: If cluster type already exists
    """
    
    # STEP 1: DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Cluster type would be created. Set confirm=True to execute.",
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
        existing_types = list(client.virtualization.cluster_types.filter(
            name=name,
            expand=["type"],  # Expand type relationships
            no_cache=True,
            limit=10
        ))
        
        if existing_types:
            existing_type = existing_types[0]
            existing_id = existing_type.get('id') if isinstance(existing_type, dict) else existing_type.id
            raise ValueError(f"Cluster type '{name}' already exists with ID {existing_id}")
            
    except ValueError:
        raise
    except Exception as e:
        logger.warning(f"Could not check for existing cluster types: {e}")
    
    # STEP 4: CREATE CLUSTER TYPE
    create_payload = {
        "name": name,
        "slug": slug
    }
    
    if description:
        create_payload["description"] = f"[NetBox-MCP] {description}"
    
    try:
        new_cluster_type = client.virtualization.cluster_types.create(confirm=confirm, **create_payload)
        
        # Apply defensive dict/object handling
        cluster_type_id = new_cluster_type.get('id') if isinstance(new_cluster_type, dict) else new_cluster_type.id
        cluster_type_name = new_cluster_type.get('name') if isinstance(new_cluster_type, dict) else new_cluster_type.name
        cluster_type_slug = new_cluster_type.get('slug') if isinstance(new_cluster_type, dict) else new_cluster_type.slug
        
    except Exception as e:
        raise ValueError(f"NetBox API error during cluster type creation: {e}")
    
    # STEP 5: RETURN SUCCESS
    return {
        "success": True,
        "message": f"Cluster type '{name}' successfully created.",
        "data": {
            "cluster_type_id": cluster_type_id,
            "name": cluster_type_name,
            "slug": cluster_type_slug,
            "description": new_cluster_type.get('description') if isinstance(new_cluster_type, dict) else getattr(new_cluster_type, 'description', None)
        }
    }


@mcp_tool(category="virtualization")
def netbox_get_cluster_type_info(
    client: NetBoxClient,
    name: Optional[str] = None,
    slug: Optional[str] = None,
    cluster_type_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get detailed information about a specific cluster type.
    
    Args:
        client: NetBoxClient instance (injected)
        name: Cluster type name to retrieve
        slug: Cluster type slug to retrieve
        cluster_type_id: Cluster type ID to retrieve
        
    Returns:
        Dict containing detailed cluster type information
        
    Raises:
        ValidationError: If no valid identifier provided
        NotFoundError: If cluster type not found
    """
    
    if not any([name, slug, cluster_type_id]):
        raise ValueError("Either 'name', 'slug', or 'cluster_type_id' must be provided")
    
    try:
        if cluster_type_id:
            cluster_type = client.virtualization.cluster_types.get(cluster_type_id)
        elif name:
            # ULTRATHINK FIX 1: Expand parameters optimization for cluster type lookup
            cluster_types = list(client.virtualization.cluster_types.filter(
                name=name,
                expand=["type"],  # Expand type relationships
                limit=10
            ))
            if not cluster_types:
                raise ValueError(f"Cluster type '{name}' not found")
            cluster_type = cluster_types[0]
        else:  # slug
            # ULTRATHINK FIX 4: Slug-based fallback with expand parameters
            cluster_types = list(client.virtualization.cluster_types.filter(
                slug=slug,
                expand=["type"],  # Expand type relationships
                limit=10
            ))
            if not cluster_types:
                raise ValueError(f"Cluster type with slug '{slug}' not found")
            cluster_type = cluster_types[0]
        
        # Apply defensive dict/object handling
        cluster_type_id = cluster_type.get('id') if isinstance(cluster_type, dict) else cluster_type.id
        cluster_type_name = cluster_type.get('name') if isinstance(cluster_type, dict) else cluster_type.name
        cluster_type_slug = cluster_type.get('slug') if isinstance(cluster_type, dict) else cluster_type.slug
        cluster_type_description = cluster_type.get('description') if isinstance(cluster_type, dict) else getattr(cluster_type, 'description', None)
        
        # Get cluster count for this type
        # ULTRATHINK FIX 1: Expand parameters optimization for cluster counting
        cluster_count = len(list(client.virtualization.clusters.filter(
            type_id=cluster_type_id,
            expand=["group", "type"],  # Expand group and type relationships
            limit=500
        )))
        
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Failed to retrieve cluster type: {e}")
    
    return {
        "success": True,
        "message": f"Retrieved cluster type '{cluster_type_name}'.",
        "data": {
            "id": cluster_type_id,
            "name": cluster_type_name,
            "slug": cluster_type_slug,
            "description": cluster_type_description,
            "cluster_count": cluster_count,
            "url": cluster_type.get('url') if isinstance(cluster_type, dict) else getattr(cluster_type, 'url', None)
        }
    }


@mcp_tool(category="virtualization")
def netbox_list_all_cluster_types(
    client: NetBoxClient,
    name_filter: Optional[str] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Get comprehensive list of all cluster types with filtering capabilities.
    
    This tool provides bulk cluster type discovery across the virtualization infrastructure,
    enabling efficient platform analysis and cluster categorization.
    
    Args:
        client: NetBoxClient instance (injected)
        name_filter: Filter by cluster type name (partial match)
        limit: Maximum number of cluster types to return (default: 100)
        
    Returns:
        Dict containing summary list of cluster types with statistics
    """
    
    # Build filter parameters
    filter_params = {}
    if name_filter:
        filter_params["name__icontains"] = name_filter
    
    try:
        # Get cluster types with applied filters
        # ULTRATHINK FIX 1: Expand parameters optimization for bulk cluster types discovery
        cluster_types = list(client.virtualization.cluster_types.filter(
            expand=["type"],  # Expand type relationships
            limit=limit,
            **filter_params
        ))
        
        # Process cluster types with defensive dict/object handling
        types_summary = []
        total_clusters = 0
        
        for cluster_type in cluster_types:
            type_id = cluster_type.get('id') if isinstance(cluster_type, dict) else cluster_type.id
            type_name = cluster_type.get('name') if isinstance(cluster_type, dict) else cluster_type.name
            type_slug = cluster_type.get('slug') if isinstance(cluster_type, dict) else cluster_type.slug
            type_description = cluster_type.get('description') if isinstance(cluster_type, dict) else getattr(cluster_type, 'description', None)
            
            # Count clusters for this type
            # ULTRATHINK FIX 1: Expand parameters optimization for cluster type counting
            cluster_count = len(list(client.virtualization.clusters.filter(
                type_id=type_id,
                expand=["group", "type"],  # Expand group and type relationships
                limit=500
            )))
            total_clusters += cluster_count
            
            types_summary.append({
                "id": type_id,
                "name": type_name,
                "slug": type_slug,
                "description": type_description,
                "cluster_count": cluster_count
            })
            
    except Exception as e:
        raise ValueError(f"Failed to retrieve cluster types: {e}")
    
    return {
        "success": True,
        "message": f"Found {len(types_summary)} cluster types.",
        "total_cluster_types": len(types_summary),
        "total_clusters": total_clusters,
        "applied_filters": {
            "name_filter": name_filter,
            "limit": limit
        },
        "data": types_summary
    }


@mcp_tool(category="virtualization")
def netbox_update_cluster_type(
    client: NetBoxClient,
    cluster_type_id: int,
    name: Optional[str] = None,
    slug: Optional[str] = None,
    description: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Update an existing cluster type in NetBox.
    
    Args:
        client: NetBoxClient instance (injected)
        cluster_type_id: ID of the cluster type to update
        name: New name for the cluster type
        slug: New slug for the cluster type
        description: New description for the cluster type
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Dict containing the updated cluster type data
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
            "message": "DRY RUN: Cluster type would be updated. Set confirm=True to execute.",
            "would_update": {
                "cluster_type_id": cluster_type_id,
                "fields": update_fields
            }
        }
    
    # STEP 2: PARAMETER VALIDATION
    if not cluster_type_id or cluster_type_id <= 0:
        raise ValueError("cluster_type_id must be a positive integer")
    
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
    
    # STEP 4: UPDATE CLUSTER TYPE
    try:
        updated_cluster_type = client.virtualization.cluster_types.update(cluster_type_id, confirm=confirm, **update_payload)
        
        # Apply defensive dict/object handling
        type_id = updated_cluster_type.get('id') if isinstance(updated_cluster_type, dict) else updated_cluster_type.id
        type_name = updated_cluster_type.get('name') if isinstance(updated_cluster_type, dict) else updated_cluster_type.name
        type_slug = updated_cluster_type.get('slug') if isinstance(updated_cluster_type, dict) else updated_cluster_type.slug
        
    except Exception as e:
        raise ValueError(f"NetBox API error during cluster type update: {e}")
    
    # STEP 5: RETURN SUCCESS
    return {
        "success": True,
        "message": f"Cluster type ID {cluster_type_id} successfully updated.",
        "data": {
            "cluster_type_id": type_id,
            "name": type_name,
            "slug": type_slug,
            "description": updated_cluster_type.get('description') if isinstance(updated_cluster_type, dict) else getattr(updated_cluster_type, 'description', None)
        }
    }


@mcp_tool(category="virtualization")
def netbox_delete_cluster_type(
    client: NetBoxClient,
    cluster_type_id: int,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Delete a cluster type from NetBox.
    
    Args:
        client: NetBoxClient instance (injected)
        cluster_type_id: ID of the cluster type to delete
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Dict containing deletion confirmation
        
    Raises:
        ValidationError: If cluster type has associated clusters
    """
    
    # STEP 1: DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Cluster type would be deleted. Set confirm=True to execute.",
            "would_delete": {
                "cluster_type_id": cluster_type_id
            }
        }
    
    # STEP 2: PARAMETER VALIDATION
    if not cluster_type_id or cluster_type_id <= 0:
        raise ValueError("cluster_type_id must be a positive integer")
    
    # STEP 3: CHECK FOR DEPENDENCIES
    try:
        # Check if cluster type has associated clusters
        associated_clusters = list(client.virtualization.clusters.filter(type_id=cluster_type_id))
        if associated_clusters:
            cluster_names = []
            for cluster in associated_clusters[:5]:  # Show first 5
                cluster_name = cluster.get('name') if isinstance(cluster, dict) else cluster.name
                cluster_names.append(cluster_name)
            
            raise ValueError(
                f"Cannot delete cluster type - {len(associated_clusters)} associated clusters found: "
                f"{', '.join(cluster_names)}" + 
                ("..." if len(associated_clusters) > 5 else "")
            )
        
        # Get cluster type info before deletion
        cluster_type = client.virtualization.cluster_types.get(cluster_type_id)
        cluster_type_name = cluster_type.get('name') if isinstance(cluster_type, dict) else cluster_type.name
        
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Failed to validate cluster type for deletion: {e}")
    
    # STEP 4: DELETE CLUSTER TYPE
    try:
        client.virtualization.cluster_types.delete(cluster_type_id, confirm=confirm)
        
    except Exception as e:
        raise ValueError(f"NetBox API error during cluster type deletion: {e}")
    
    # STEP 5: RETURN SUCCESS
    return {
        "success": True,
        "message": f"Cluster type '{cluster_type_name}' (ID: {cluster_type_id}) successfully deleted.",
        "data": {
            "deleted_cluster_type_id": cluster_type_id,
            "deleted_cluster_type_name": cluster_type_name
        }
    }