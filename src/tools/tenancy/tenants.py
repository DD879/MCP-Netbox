#!/usr/bin/env python3
"""
Tenancy Management Tools

High-level tools for managing NetBox tenants, tenant groups,
resource assignments and tenant reporting with enterprise-grade functionality.
"""

from typing import Dict, List, Optional, Any
import logging
import re
from ...registry import mcp_tool
from ...client import NetBoxClient

logger = logging.getLogger(__name__)


@mcp_tool(category="tenancy")
def netbox_onboard_new_tenant(
    client: NetBoxClient,
    tenant_name: str,
    tenant_group_name: Optional[str] = None,
    description: Optional[str] = None,
    comments: Optional[str] = None,
    contact_name: Optional[str] = None,
    contact_email: Optional[str] = None,
    contact_phone: Optional[str] = None,
    contact_address: Optional[str] = None,
    tenant_status: str = "active",
    tags: Optional[List[str]] = None,
    create_group_if_missing: bool = False,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Onboard a new tenant to NetBox with formalized categorization and contact management.
    
    This enterprise-grade onboarding tool ensures proper tenant categorization and
    standardized metadata collection essential for clean administration and resource
    management in multi-tenant NetBox environments.
    
    Args:
        client: NetBoxClient instance (injected)
        tenant_name: Name of the new tenant (required)
        tenant_group_name: Tenant group for categorization (optional)
        description: Tenant description/purpose
        comments: Additional comments about the tenant
        contact_name: Primary contact person name
        contact_email: Primary contact email address
        contact_phone: Primary contact phone number
        contact_address: Primary contact address
        tenant_status: Tenant status (active, provisioning, suspended, decommissioning)
        tags: List of tag names to assign to the tenant
        create_group_if_missing: Create tenant group if it doesn't exist
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Comprehensive tenant onboarding results with categorization validation
        
    Examples:
        # Basic tenant onboarding
        netbox_onboard_new_tenant(
            tenant_name="Customer-A",
            tenant_group_name="Customers",
            description="Primary customer tenant",
            confirm=True
        )
        
        # Complete tenant onboarding with contacts
        netbox_onboard_new_tenant(
            tenant_name="IT-Department",
            tenant_group_name="Internal-Departments",
            description="Internal IT department resources",
            contact_name="John Smith",
            contact_email="john.smith@company.com",
            contact_phone="+1-555-0123",
            tenant_status="active",
            tags=["internal", "it-dept"],
            confirm=True
        )
        
        # Onboarding with automatic group creation
        netbox_onboard_new_tenant(
            tenant_name="New-Customer",
            tenant_group_name="Enterprise-Customers",
            create_group_if_missing=True,
            description="Enterprise customer requiring dedicated resources",
            confirm=True
        )
    """
    try:
        if not tenant_name:
            return {
                "success": False,
                "error": "tenant_name is required",
                "error_type": "ValidationError"
            }
        
        if not tenant_name.strip():
            return {
                "success": False,
                "error": "tenant_name cannot be empty or whitespace",
                "error_type": "ValidationError"
            }
        
        # Validate tenant status
        valid_statuses = ["active", "provisioning", "suspended", "decommissioning"]
        if tenant_status not in valid_statuses:
            return {
                "success": False,
                "error": f"Invalid tenant_status '{tenant_status}'. Must be one of: {valid_statuses}",
                "error_type": "ValidationError"
            }
        
        logger.info(f"Onboarding new tenant: {tenant_name}")
        
        # Step 1: Check if tenant already exists
        logger.debug(f"Checking for existing tenant: {tenant_name}")
        # ULTRATHINK FIX 1: Expand search parameters with comprehensive relationship data
        search_params = {
            "expand": ["group", "contacts"],
            "limit": 50
        }

        # ULTRATHINK FIX 2: ID resolution with fallback patterns
        existing_tenants = None
        if tenant_name.isdigit():
            existing_tenants = list(client.tenancy.tenants.filter(id=int(tenant_name), **search_params))

        if not existing_tenants:
            existing_tenants = list(client.tenancy.tenants.filter(name=tenant_name, **search_params))
        
        if existing_tenants:
            return {
                "success": False,
                "error": f"Tenant '{tenant_name}' already exists",
                "error_type": "ConflictError",
                "existing_tenant": existing_tenants[0]
            }
        
        # Also check by slug to be thorough
        tenant_slug = tenant_name.lower().replace(' ', '-').replace('_', '-')
        # ULTRATHINK FIX 4: Slug-based fallback with expand parameters
        existing_by_slug = list(client.tenancy.tenants.filter(slug=tenant_slug, **search_params))
        
        if existing_by_slug:
            return {
                "success": False,
                "error": f"Tenant with slug '{tenant_slug}' already exists",
                "error_type": "ConflictError",
                "existing_tenant": existing_by_slug[0]
            }
        
        # Step 2: Resolve tenant group if specified
        tenant_group_id = None
        tenant_group_obj = None
        resolved_refs = {}
        
        if tenant_group_name:
            logger.debug(f"Looking up tenant group: {tenant_group_name}")
            # ULTRATHINK FIX 1: Expand search parameters for tenant groups
            group_search_params = {
                "expand": ["parent"],
                "limit": 50
            }

            # ULTRATHINK FIX 2: ID resolution with fallback patterns
            tenant_groups = None
            if tenant_group_name.isdigit():
                tenant_groups = list(client.tenancy.tenant_groups.filter(id=int(tenant_group_name), **group_search_params))

            if not tenant_groups:
                tenant_groups = list(client.tenancy.tenant_groups.filter(name=tenant_group_name, **group_search_params))
            
            if not tenant_groups:
                # Try by slug
                # ULTRATHINK FIX 4: Slug-based fallback with expand parameters
                tenant_groups = list(client.tenancy.tenant_groups.filter(slug=tenant_group_name, **group_search_params))
            
            if tenant_groups:
                tenant_group_obj = tenant_groups[0]
                tenant_group_id = tenant_group_obj["id"]
                resolved_refs["tenant_group"] = {
                    "id": tenant_group_id,
                    "name": tenant_group_obj["name"],
                    "slug": tenant_group_obj["slug"]
                }
                logger.debug(f"Found tenant group: {tenant_group_obj['name']} (ID: {tenant_group_id})")
            else:
                if create_group_if_missing:
                    logger.info(f"Creating missing tenant group: {tenant_group_name}")
                    
                    # Create the tenant group
                    # Generate slug for the group
                    group_slug = re.sub(r'[^a-zA-Z0-9-_]', '-', tenant_group_name.lower())
                    group_slug = re.sub(r'-+', '-', group_slug).strip('-')
                    
                    group_data = {
                        "name": tenant_group_name,
                        "slug": group_slug,
                        "description": f"Auto-created group for {tenant_group_name} tenants"
                    }
                    
                    try:
                        if not confirm:
                            # Dry run mode - show what would be created
                            return {
                                "success": True,
                                "action": "dry_run",
                                "would_create": {
                                    "tenant_group": group_data,
                                    "tenant": {
                                        "name": tenant_name,
                                        "group": tenant_group_name,
                                        "status": tenant_status
                                    }
                                },
                                "dry_run": True
                            }
                        
                        created_group = client.tenancy.tenant_groups.create(confirm=True, **group_data)
                        tenant_group_id = created_group["id"]
                        tenant_group_obj = created_group
                        resolved_refs["tenant_group"] = {
                            "id": tenant_group_id,
                            "name": created_group["name"],
                            "slug": created_group["slug"],
                            "auto_created": True
                        }
                        logger.info(f"✅ Created tenant group: {tenant_group_name} (ID: {tenant_group_id})")
                        
                    except Exception as e:
                        logger.error(f"Failed to create tenant group: {e}")
                        return {
                            "success": False,
                            "error": f"Failed to create tenant group '{tenant_group_name}': {str(e)}",
                            "error_type": "TenantGroupCreationError"
                        }
                else:
                    return {
                        "success": False,
                        "error": f"Tenant group '{tenant_group_name}' not found",
                        "error_type": "NotFoundError",
                        "suggestion": "Set create_group_if_missing=True to automatically create the group"
                    }
        
        # Step 3: Resolve tags if specified
        tag_ids = []
        if tags:
            logger.debug(f"Resolving tags: {tags}")
            for tag_name in tags:
                try:
                    # Look up tag by name
                    tag_objects = client.extras.tags.filter(name=tag_name)
                    if not tag_objects:
                        # Try by slug
                        tag_objects = client.extras.tags.filter(slug=tag_name)
                    
                    if tag_objects:
                        tag_ids.append(tag_objects[0]["id"])
                        logger.debug(f"Found tag: {tag_name} (ID: {tag_objects[0]['id']})")
                    else:
                        logger.warning(f"Tag '{tag_name}' not found, skipping")
                        
                except Exception as e:
                    logger.warning(f"Failed to lookup tag '{tag_name}': {e}")
                    continue
        
        if not confirm:
            # Dry run mode - show what would be created
            return {
                "success": True,
                "action": "dry_run",
                "would_create": {
                    "tenant": {
                        "name": tenant_name,
                        "group_id": tenant_group_id,
                        "status": tenant_status,
                        "description": description,
                        "comments": comments,
                        "contact_info": {
                            "name": contact_name,
                            "email": contact_email,
                            "phone": contact_phone,
                            "address": contact_address
                        },
                        "tags": tags
                    }
                },
                "resolved_references": resolved_refs,
                "validation_results": {
                    "tenant_available": True,
                    "group_resolved": bool(tenant_group_id),
                    "tags_resolved": len(tag_ids) if tags else 0
                },
                "dry_run": True
            }
        
        # Step 4: Build tenant data
        # Generate slug from tenant name
        tenant_slug = re.sub(r'[^a-zA-Z0-9-_]', '-', tenant_name.lower())
        tenant_slug = re.sub(r'-+', '-', tenant_slug).strip('-')
        
        tenant_data = {
            "name": tenant_name,
            "slug": tenant_slug,
            "status": tenant_status
        }
        
        if description:
            tenant_data["description"] = description
        if comments:
            tenant_data["comments"] = comments
        if tenant_group_id:
            tenant_data["group"] = tenant_group_id
        if tag_ids:
            tenant_data["tags"] = tag_ids
        
        # Add contact information if provided
        custom_fields = {}
        if contact_name:
            custom_fields["contact_name"] = contact_name
        if contact_email:
            custom_fields["contact_email"] = contact_email
        if contact_phone:
            custom_fields["contact_phone"] = contact_phone
        if contact_address:
            custom_fields["contact_address"] = contact_address
        
        # Note: Custom fields would need to be defined in NetBox first
        # For now, we'll include contact info in comments if no custom fields
        if custom_fields and not tenant_data.get("comments"):
            contact_info = []
            if contact_name:
                contact_info.append(f"Contact: {contact_name}")
            if contact_email:
                contact_info.append(f"Email: {contact_email}")
            if contact_phone:
                contact_info.append(f"Phone: {contact_phone}")
            if contact_address:
                contact_info.append(f"Address: {contact_address}")
            
            if contact_info:
                tenant_data["comments"] = "\n".join(contact_info)
        
        # Step 5: Create the tenant
        logger.info(f"Creating tenant: {tenant_name}")
        
        try:
            logger.debug(f"Creating tenant with data: {tenant_data}")
            created_tenant = client.tenancy.tenants.create(confirm=True, **tenant_data)
            logger.info(f"✅ Created tenant: {tenant_name} (ID: {created_tenant['id']})")
            
        except Exception as e:
            logger.error(f"Failed to create tenant: {e}")
            
            # If we auto-created a group, we might want to clean it up
            if (tenant_group_obj and 
                resolved_refs.get("tenant_group", {}).get("auto_created") and 
                tenant_group_id):
                logger.warning("Attempting to clean up auto-created tenant group...")
                try:
                    client.tenancy.tenant_groups.delete(tenant_group_id, confirm=True)
                    logger.info("✅ Cleaned up auto-created tenant group")
                except Exception as cleanup_error:
                    logger.error(f"Failed to clean up tenant group: {cleanup_error}")
            
            return {
                "success": False,
                "error": f"Failed to create tenant: {str(e)}",
                "error_type": "TenantCreationError",
                "operation": "tenant_creation"
            }
        
        # Step 6: Apply cache invalidation pattern
        logger.debug("Invalidating tenancy cache after tenant creation...")
        try:
            client.cache.invalidate_pattern("tenancy.tenants")
            if tenant_group_id:
                client.cache.invalidate_pattern("tenancy.tenant_groups")
        except Exception as cache_error:
            # Cache invalidation failure should not fail the operation
            logger.warning(f"Cache invalidation failed after tenant creation: {cache_error}")
        
        # Step 7: Build comprehensive success response
        result = {
            "success": True,
            "action": "onboarded",
            "tenant": {
                "id": created_tenant["id"],
                "name": created_tenant["name"],
                "slug": created_tenant["slug"],
                "status": created_tenant.get("status", {}).get("value", "unknown") if isinstance(created_tenant.get("status"), dict) else created_tenant.get("status", "unknown"),
                "description": created_tenant.get("description", ""),
                "comments": created_tenant.get("comments", ""),
                "url": created_tenant.get("url", ""),
                "display_url": created_tenant.get("display_url", "")
            },
            "categorization": {
                "tenant_group_assigned": bool(tenant_group_id),
                "group_auto_created": resolved_refs.get("tenant_group", {}).get("auto_created", False),
                "tags_applied": len(tag_ids) if tag_ids else 0
            },
            "contact_information": {
                "contact_name": contact_name,
                "contact_email": contact_email,
                "contact_phone": contact_phone,
                "contact_address": contact_address,
                "stored_in_comments": bool(custom_fields and not tenant_data.get("comments"))
            },
            "resolved_references": resolved_refs,
            "dry_run": False
        }
        
        logger.info(f"✅ Tenant onboarding complete: {tenant_name} (ID: {created_tenant['id']})")
        return result
        
    except Exception as e:
        logger.error(f"Failed to onboard tenant {tenant_name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@mcp_tool(category="tenancy")
def netbox_create_tenant_group(
    client: NetBoxClient,
    group_name: str,
    parent_group: Optional[str] = None,
    description: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Create a new tenant group in NetBox with hierarchical organization support.
    
    Args:
        client: NetBoxClient instance (injected)
        group_name: Name of the tenant group
        parent_group: Optional parent group name for hierarchical structure
        description: Optional description of the group
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Created tenant group information or error details
        
    Example:
        netbox_create_tenant_group("Enterprise-Customers", description="Large enterprise customers", confirm=True)
    """
    try:
        if not group_name:
            return {
                "success": False,
                "error": "group_name is required",
                "error_type": "ValidationError"
            }
        
        logger.info(f"Creating tenant group: {group_name}")
        
        # Check if group already exists
        # ULTRATHINK FIX 1: Expand search parameters with comprehensive relationship data
        group_search_params = {
            "expand": ["parent"],
            "limit": 50
        }

        # ULTRATHINK FIX 2: ID resolution with fallback patterns
        existing_groups = None
        if group_name.isdigit():
            existing_groups = list(client.tenancy.tenant_groups.filter(id=int(group_name), **group_search_params))

        if not existing_groups:
            existing_groups = list(client.tenancy.tenant_groups.filter(name=group_name, **group_search_params))
        if existing_groups:
            return {
                "success": False,
                "error": f"Tenant group '{group_name}' already exists",
                "error_type": "ConflictError",
                "existing_group": existing_groups[0]
            }
        
        # Build group data with slug generation
        # Generate slug from group name
        group_slug = re.sub(r'[^a-zA-Z0-9-_]', '-', group_name.lower())
        group_slug = re.sub(r'-+', '-', group_slug).strip('-')
        
        group_data = {
            "name": group_name,
            "slug": group_slug
        }
        
        if description:
            group_data["description"] = description
        
        # Resolve parent group if specified
        if parent_group:
            logger.debug(f"Looking up parent group: {parent_group}")
            # ULTRATHINK FIX 1: Expand search parameters for parent groups
            parent_search_params = {
                "expand": ["parent"],
                "limit": 50
            }

            # ULTRATHINK FIX 2: ID resolution with fallback patterns
            parent_groups = None
            if parent_group.isdigit():
                parent_groups = list(client.tenancy.tenant_groups.filter(id=int(parent_group), **parent_search_params))

            if not parent_groups:
                parent_groups = list(client.tenancy.tenant_groups.filter(name=parent_group, **parent_search_params))

            # ULTRATHINK FIX 4: Slug-based fallback with expand parameters
            if not parent_groups:
                parent_groups = list(client.tenancy.tenant_groups.filter(slug=parent_group, **parent_search_params))
            
            if parent_groups:
                group_data["parent"] = parent_groups[0]["id"]
                logger.debug(f"Found parent group: {parent_groups[0]['name']} (ID: {parent_groups[0]['id']})")
            else:
                return {
                    "success": False,
                    "error": f"Parent group '{parent_group}' not found",
                    "error_type": "NotFoundError"
                }
        
        # Use dynamic API with safety
        result = client.tenancy.tenant_groups.create(confirm=confirm, **group_data)
        
        return {
            "success": True,
            "action": "created",
            "object_type": "tenant_group",
            "tenant_group": result,
            "dry_run": result.get("dry_run", False)
        }
        
    except Exception as e:
        logger.error(f"Failed to create tenant group {group_name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@mcp_tool(category="tenancy")
def netbox_list_all_tenants(
    client: NetBoxClient,
    limit: int = 100,
    group_name: Optional[str] = None,
    status: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get summarized list of tenants with optional filtering.
    
    This tool provides bulk tenant discovery across the NetBox multi-tenant 
    infrastructure, enabling efficient tenant administration, billing operations,
    and resource management. Essential for enterprise multi-tenant environments.
    
    Args:
        client: NetBoxClient instance (injected by dependency system)
        limit: Maximum number of results to return (default: 100)
        group_name: Filter by tenant group name (optional)
        status: Filter by tenant status (active, provisioning, suspended, etc.)
        
    Returns:
        Dictionary containing:
        - count: Total number of tenants found
        - tenants: List of summarized tenant information
        - filters_applied: Dictionary of filters that were applied
        - summary_stats: Aggregate statistics about the tenants
        
    Example:
        netbox_list_all_tenants(status="active", group_name="customers")
        netbox_list_all_tenants(limit=50)
    """
    try:
        logger.info(f"Listing tenants with filters - group: {group_name}, status: {status}")
        
        # Build filters dictionary - only include non-None values
        filters = {}
        if group_name:
            filters['group'] = group_name
        if status:
            filters['status'] = status
        
        # Execute filtered query with limit
        # ULTRATHINK FIX 1: Expand search parameters for comprehensive tenant data
        if 'expand' not in filters:
            filters['expand'] = ["group", "contacts"]
        if 'limit' not in filters:
            filters['limit'] = 100

        # ULTRATHINK FIX 5: List handling with proper iterator management
        tenants = list(client.tenancy.tenants.filter(**filters))
        
        # Apply limit after fetching
        if len(tenants) > limit:
            tenants = tenants[:limit]
        
        # Generate summary statistics
        status_counts = {}
        group_counts = {}
        
        # Collect resource statistics for each tenant
        total_devices = 0
        total_sites = 0
        total_prefixes = 0
        
        for tenant in tenants:
            # Status breakdown with defensive dictionary access
            status_obj = tenant.get("status", {})
            if isinstance(status_obj, dict):
                status = status_obj.get("label", "N/A")
            else:
                status = str(status_obj) if status_obj else "N/A"
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Group breakdown with defensive dictionary access
            group_obj = tenant.get("group")
            if group_obj:
                if isinstance(group_obj, dict):
                    group_name = group_obj.get("name", str(group_obj))
                else:
                    group_name = str(group_obj)
                group_counts[group_name] = group_counts.get(group_name, 0) + 1
            
            # Get basic resource counts for this tenant (efficient queries)
            tenant_id = tenant.get("id")
            tenant_devices = list(client.dcim.devices.filter(tenant_id=tenant_id))
            tenant_sites = list(client.dcim.sites.filter(tenant_id=tenant_id))
            tenant_prefixes = list(client.ipam.prefixes.filter(tenant_id=tenant_id))
            
            total_devices += len(tenant_devices)
            total_sites += len(tenant_sites)
            total_prefixes += len(tenant_prefixes)
        
        # Create human-readable tenant list
        tenant_list = []
        for tenant in tenants:
            # Get resource counts for this specific tenant
            tenant_id = tenant.get("id")
            tenant_devices = list(client.dcim.devices.filter(tenant_id=tenant_id))
            tenant_sites = list(client.dcim.sites.filter(tenant_id=tenant_id))
            tenant_prefixes = list(client.ipam.prefixes.filter(tenant_id=tenant_id))
            tenant_vlans = list(client.ipam.vlans.filter(tenant_id=tenant_id))
            
            # Defensive dictionary access for status
            status_obj = tenant.get("status", {})
            if isinstance(status_obj, dict):
                status = status_obj.get("label", "N/A")
            else:
                status = str(status_obj) if status_obj else "N/A"
            
            # Defensive dictionary access for group
            group_obj = tenant.get("group")
            group_name = None
            if group_obj:
                if isinstance(group_obj, dict):
                    group_name = group_obj.get("name")
                else:
                    group_name = str(group_obj)
            
            tenant_info = {
                "name": tenant.get("name", "Unknown"),
                "slug": tenant.get("slug", ""),
                "status": status,
                "group": group_name,
                "description": tenant.get("description"),
                "comments": tenant.get("comments"),
                "resource_counts": {
                    "devices": len(tenant_devices),
                    "sites": len(tenant_sites),
                    "prefixes": len(tenant_prefixes),
                    "vlans": len(tenant_vlans)
                },
                "total_resources": len(tenant_devices) + len(tenant_sites) + len(tenant_prefixes) + len(tenant_vlans),
                "created": tenant.get("created"),
                "last_updated": tenant.get("last_updated")
            }
            tenant_list.append(tenant_info)
        
        result = {
            "count": len(tenant_list),
            "tenants": tenant_list,
            "filters_applied": {k: v for k, v in filters.items() if v is not None},
            "summary_stats": {
                "total_tenants": len(tenant_list),
                "status_breakdown": status_counts,
                "group_breakdown": group_counts,
                "total_devices_across_tenants": total_devices,
                "total_sites_across_tenants": total_sites,
                "total_prefixes_across_tenants": total_prefixes,
                "tenants_with_resources": len([t for t in tenant_list if t['total_resources'] > 0]),
                "tenants_with_groups": len([t for t in tenant_list if t['group']]),
                "average_resources_per_tenant": total_devices + total_sites + total_prefixes / len(tenant_list) if tenant_list else 0
            }
        }
        
        logger.info(f"Found {len(tenant_list)} tenants matching criteria. Status breakdown: {status_counts}")
        return result
        
    except Exception as e:
        logger.error(f"Error listing tenants: {e}")
        return {
            "count": 0,
            "tenants": [],
            "error": str(e),
            "error_type": type(e).__name__,
            "filters_applied": {k: v for k, v in {
                'group_name': group_name,
                'status': status
            }.items() if v is not None}
        }