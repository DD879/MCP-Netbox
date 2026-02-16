#!/usr/bin/env python3
"""
Tenancy Resource Management Tools

High-level tools for managing resource assignments and tenant reporting
with enterprise-grade functionality for multi-tenant environments.
"""

from typing import Dict, List, Optional, Any
import logging
from ...registry import mcp_tool
from ...client import NetBoxClient

logger = logging.getLogger(__name__)


@mcp_tool(category="tenancy")
def netbox_assign_resources_to_tenant(
    client: NetBoxClient,
    tenant_name: str,
    resources: List[Dict[str, Any]],
    assignment_mode: str = "assign",
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Assign or unassign NetBox resources to/from a tenant for ownership tracking.
    
    This enterprise-grade resource management tool provides flexible assignment of any
    NetBox resource type to tenants, enabling comprehensive ownership tracking and
    multi-tenant resource organization across the entire NetBox infrastructure.
    
    Args:
        client: NetBoxClient instance (injected)
        tenant_name: Name of the tenant to assign resources to
        resources: List of resource dictionaries with type and identifier
        assignment_mode: Operation mode ("assign" or "unassign")
        confirm: Must be True to execute (safety mechanism)
        
    Resource Dictionary Format:
        {
            "type": "resource_type",        # e.g., "device", "prefix", "vlan", "circuit"
            "identifier": "value",          # Resource identifier (name, IP, ID, etc.)
            "identifier_field": "field"     # Optional: field to search by (default: name)
        }
        
    Supported Resource Types:
        - "device": DCIM devices
        - "prefix": IPAM prefixes  
        - "vlan": IPAM VLANs
        - "ip_address": IPAM IP addresses
        - "circuit": Circuits
        - "rack": DCIM racks
        - "site": DCIM sites
        - "cluster": Virtualization clusters
        
    Returns:
        Comprehensive assignment results with success/failure details per resource
        
    Examples:
        # Assign multiple resources to a tenant
        netbox_assign_resources_to_tenant(
            tenant_name="Customer-A",
            resources=[
                {"type": "prefix", "identifier": "10.100.0.0/24"},
                {"type": "vlan", "identifier": "Production", "identifier_field": "name"},
                {"type": "device", "identifier": "server-01"}
            ],
            confirm=True
        )
        
        # Unassign resources from a tenant
        netbox_assign_resources_to_tenant(
            tenant_name="Customer-A", 
            resources=[
                {"type": "prefix", "identifier": "10.100.0.0/24"}
            ],
            assignment_mode="unassign",
            confirm=True
        )
        
        # Assign by different identifier fields
        netbox_assign_resources_to_tenant(
            tenant_name="Customer-B",
            resources=[
                {"type": "device", "identifier": "123", "identifier_field": "id"},
                {"type": "vlan", "identifier": "200", "identifier_field": "vid"}
            ],
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
        
        if not resources or not isinstance(resources, list):
            return {
                "success": False,
                "error": "resources must be a non-empty list",
                "error_type": "ValidationError"
            }
        
        if assignment_mode not in ["assign", "unassign"]:
            return {
                "success": False,
                "error": "assignment_mode must be 'assign' or 'unassign'",
                "error_type": "ValidationError"
            }
        
        logger.info(f"{'Assigning' if assignment_mode == 'assign' else 'Unassigning'} {len(resources)} resources {'to' if assignment_mode == 'assign' else 'from'} tenant: {tenant_name}")
        
        # Step 1: Define resource type mappings
        resource_mappings = {
            "device": {
                "client_path": "dcim.devices",
                "default_field": "name",
                "supported_fields": ["name", "id", "serial", "asset_tag"]
            },
            "prefix": {
                "client_path": "ipam.prefixes", 
                "default_field": "prefix",
                "supported_fields": ["prefix", "id"]
            },
            "vlan": {
                "client_path": "ipam.vlans",
                "default_field": "name", 
                "supported_fields": ["name", "id", "vid"]
            },
            "ip_address": {
                "client_path": "ipam.ip_addresses",
                "default_field": "address",
                "supported_fields": ["address", "id"]
            },
            "circuit": {
                "client_path": "circuits.circuits",
                "default_field": "cid",
                "supported_fields": ["cid", "id"]
            },
            "rack": {
                "client_path": "dcim.racks",
                "default_field": "name",
                "supported_fields": ["name", "id"]
            },
            "site": {
                "client_path": "dcim.sites",
                "default_field": "name",
                "supported_fields": ["name", "id", "slug"]
            },
            "cluster": {
                "client_path": "virtualization.clusters",
                "default_field": "name",
                "supported_fields": ["name", "id"]
            }
        }
        
        # Step 2: Validate resource specifications
        validated_resources = []
        for i, resource in enumerate(resources):
            if not isinstance(resource, dict):
                return {
                    "success": False,
                    "error": f"Resource {i+1} must be a dictionary",
                    "error_type": "ValidationError"
                }
            
            resource_type = resource.get("type")
            identifier = resource.get("identifier")
            identifier_field = resource.get("identifier_field")
            
            if not resource_type:
                return {
                    "success": False,
                    "error": f"Resource {i+1} missing 'type' field",
                    "error_type": "ValidationError"
                }
            
            if not identifier:
                return {
                    "success": False,
                    "error": f"Resource {i+1} missing 'identifier' field", 
                    "error_type": "ValidationError"
                }
            
            if resource_type not in resource_mappings:
                supported_types = list(resource_mappings.keys())
                return {
                    "success": False,
                    "error": f"Resource {i+1} has unsupported type '{resource_type}'. Supported types: {supported_types}",
                    "error_type": "ValidationError"
                }
            
            mapping = resource_mappings[resource_type]
            
            # Use default field if not specified
            if not identifier_field:
                identifier_field = mapping["default_field"]
            
            # Validate identifier field
            if identifier_field not in mapping["supported_fields"]:
                return {
                    "success": False,
                    "error": f"Resource {i+1} has unsupported identifier_field '{identifier_field}' for type '{resource_type}'. Supported fields: {mapping['supported_fields']}",
                    "error_type": "ValidationError"
                }
            
            validated_resources.append({
                "original_index": i,
                "type": resource_type,
                "identifier": identifier,
                "identifier_field": identifier_field,
                "mapping": mapping
            })
        
        # Step 3: Resolve tenant (after resource validation)
        logger.debug(f"Looking up tenant: {tenant_name}")
        tenants = client.tenancy.tenants.filter(name=tenant_name)
        if not tenants:
            tenants = client.tenancy.tenants.filter(slug=tenant_name)
        
        if not tenants:
            return {
                "success": False,
                "error": f"Tenant '{tenant_name}' not found",
                "error_type": "NotFoundError"
            }
        
        tenant_obj = tenants[0]
        tenant_id = tenant_obj["id"]
        logger.debug(f"Found tenant: {tenant_obj['name']} (ID: {tenant_id})")
        
        if not confirm:
            # Dry run mode - show what would be processed
            return {
                "success": True,
                "action": "dry_run",
                "operation": assignment_mode,
                "tenant": {
                    "name": tenant_obj["name"],
                    "id": tenant_id
                },
                "would_process": [
                    {
                        "type": res["type"],
                        "identifier": res["identifier"],
                        "identifier_field": res["identifier_field"]
                    }
                    for res in validated_resources
                ],
                "total_resources": len(validated_resources),
                "dry_run": True
            }
        
        # Step 4: Process each resource
        assignment_results = []
        successful_assignments = 0
        
        for res_spec in validated_resources:
            resource_type = res_spec["type"]
            identifier = res_spec["identifier"]
            identifier_field = res_spec["identifier_field"]
            mapping = res_spec["mapping"]
            original_index = res_spec["original_index"]
            
            try:
                logger.debug(f"Processing {resource_type} resource: {identifier} (field: {identifier_field})")
                
                # Get the client endpoint
                client_path = mapping["client_path"]
                endpoint = client
                for path_part in client_path.split('.'):
                    endpoint = getattr(endpoint, path_part)
                
                # Find the resource
                filter_params = {identifier_field: identifier}
                found_resources = endpoint.filter(**filter_params)
                
                if not found_resources:
                    assignment_results.append({
                        "resource_index": original_index + 1,
                        "type": resource_type,
                        "identifier": identifier,
                        "identifier_field": identifier_field,
                        "success": False,
                        "error": f"{resource_type.title()} '{identifier}' not found",
                        "error_type": "NotFoundError"
                    })
                    continue
                
                resource_obj = found_resources[0]
                resource_id = resource_obj["id"]
                
                # Perform the assignment/unassignment
                update_data = {}
                if assignment_mode == "assign":
                    update_data["tenant"] = tenant_id
                    operation_desc = f"Assigned to tenant {tenant_obj['name']}"
                else:  # unassign
                    update_data["tenant"] = None
                    operation_desc = f"Unassigned from tenant"
                
                logger.debug(f"Updating {resource_type} {resource_id} with: {update_data}")
                updated_resource = endpoint.update(resource_id, confirm=True, **update_data)
                
                assignment_results.append({
                    "resource_index": original_index + 1,
                    "type": resource_type,
                    "identifier": identifier,
                    "identifier_field": identifier_field,
                    "resource_id": resource_id,
                    "success": True,
                    "operation": operation_desc,
                    "updated_resource": {
                        "id": updated_resource["id"],
                        "name": updated_resource.get("name", ""),
                        "url": updated_resource.get("url", "")
                    }
                })
                
                successful_assignments += 1
                logger.info(f"✅ {operation_desc}: {resource_type} '{identifier}' (ID: {resource_id})")
                
            except Exception as e:
                logger.error(f"Failed to {assignment_mode} {resource_type} '{identifier}': {e}")
                assignment_results.append({
                    "resource_index": original_index + 1,
                    "type": resource_type,
                    "identifier": identifier,
                    "identifier_field": identifier_field,
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__
                })
        
        # Step 5: Apply cache invalidation pattern
        logger.debug("Invalidating cache after resource assignments...")
        try:
            # Invalidate tenant cache
            client.cache.invalidate_pattern("tenancy.tenants")
            
            # Invalidate caches for affected resource types
            affected_types = set(res["type"] for res in validated_resources)
            for resource_type in affected_types:
                mapping = resource_mappings[resource_type]
                cache_pattern = mapping["client_path"].replace(".", ".")
                client.cache.invalidate_pattern(cache_pattern)
                
        except Exception as cache_error:
            logger.warning(f"Cache invalidation failed after assignments: {cache_error}")
        
        # Step 6: Build comprehensive response
        operation_success = successful_assignments > 0
        
        result = {
            "success": operation_success,
            "action": f"{assignment_mode}ed" if operation_success else "failed",
            "operation": assignment_mode,
            "tenant": {
                "name": tenant_obj["name"],
                "id": tenant_id
            },
            "summary": {
                "total_resources": len(validated_resources),
                "successful_assignments": successful_assignments,
                "failed_assignments": len(validated_resources) - successful_assignments,
                "success_rate": round((successful_assignments / len(validated_resources) * 100), 2) if validated_resources else 0
            },
            "assignment_results": assignment_results,
            "dry_run": False
        }
        
        logger.info(f"✅ Resource {assignment_mode}ment complete: {successful_assignments}/{len(validated_resources)} successful")
        return result
        
    except Exception as e:
        logger.error(f"Failed to {assignment_mode} resources to tenant {tenant_name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@mcp_tool(category="tenancy")
def netbox_get_tenant_resource_report(
    client: NetBoxClient,
    tenant_name: str,
    include_details: bool = True,
    include_utilization: bool = True,
    filter_by_site: Optional[str] = None,
    filter_by_status: Optional[str] = None,
    export_format: str = "json"
) -> Dict[str, Any]:
    """
    Generate comprehensive tenant resource report providing "single pane of glass" visibility.
    
    This enterprise-grade reporting tool provides complete visibility into all resources
    owned by a specific tenant across the entire NetBox infrastructure, essential for
    account management, compliance audits, and resource planning.
    
    Args:
        client: NetBoxClient instance (injected)
        tenant_name: Name of the tenant to generate report for
        include_details: Include detailed resource information (vs summary only)
        include_utilization: Include resource utilization statistics
        filter_by_site: Optional site filter for scoped reporting
        filter_by_status: Optional status filter (active, reserved, etc.)
        export_format: Report format (json, summary, detailed)
        
    Returns:
        Comprehensive tenant resource report with utilization statistics
        
    Examples:
        # Basic tenant resource report
        netbox_get_tenant_resource_report(
            tenant_name="Customer-A"
        )
        
        # Detailed report with utilization stats
        netbox_get_tenant_resource_report(
            tenant_name="Customer-A",
            include_details=True,
            include_utilization=True
        )
        
        # Site-scoped report for specific location
        netbox_get_tenant_resource_report(
            tenant_name="Enterprise-Customer",
            filter_by_site="Data-Center-West",
            filter_by_status="active"
        )
    """
    try:
        if not tenant_name:
            return {
                "success": False,
                "error": "tenant_name is required",
                "error_type": "ValidationError"
            }
        
        logger.info(f"Generating comprehensive resource report for tenant: {tenant_name}")
        
        # Step 1: Resolve tenant
        logger.debug(f"Looking up tenant: {tenant_name}")
        tenants = client.tenancy.tenants.filter(name=tenant_name)
        if not tenants:
            tenants = client.tenancy.tenants.filter(slug=tenant_name)
        
        if not tenants:
            return {
                "success": False,
                "error": f"Tenant '{tenant_name}' not found",
                "error_type": "NotFoundError"
            }
        
        tenant_obj = tenants[0]
        tenant_id = tenant_obj["id"]
        logger.debug(f"Found tenant: {tenant_obj['name']} (ID: {tenant_id})")
        
        # Step 2: Define resource collection endpoints
        resource_endpoints = {
            "devices": {
                "client_path": "dcim.devices",
                "display_field": "name",
                "summary_fields": ["name", "device_type", "device_role", "status", "site"]
            },
            "racks": {
                "client_path": "dcim.racks",
                "display_field": "name", 
                "summary_fields": ["name", "site", "status", "u_height"]
            },
            "sites": {
                "client_path": "dcim.sites",
                "display_field": "name",
                "summary_fields": ["name", "slug", "status", "region"]
            },
            "prefixes": {
                "client_path": "ipam.prefixes",
                "display_field": "prefix",
                "summary_fields": ["prefix", "status", "vrf", "site", "vlan"]
            },
            "vlans": {
                "client_path": "ipam.vlans",
                "display_field": "name",
                "summary_fields": ["name", "vid", "status", "site", "vlan_group"]
            },
            "ip_addresses": {
                "client_path": "ipam.ip_addresses",
                "display_field": "address",
                "summary_fields": ["address", "status", "assigned_object", "vrf"]
            },
            "circuits": {
                "client_path": "circuits.circuits",
                "display_field": "cid",
                "summary_fields": ["cid", "status", "provider", "type"]
            },
            "clusters": {
                "client_path": "virtualization.clusters",
                "display_field": "name",
                "summary_fields": ["name", "type", "status", "site"]
            }
        }
        
        # Step 3: Resolve optional site filter
        site_filter = None
        if filter_by_site:
            logger.debug(f"Resolving site filter: {filter_by_site}")
            sites = client.dcim.sites.filter(name=filter_by_site)
            if not sites:
                sites = client.dcim.sites.filter(slug=filter_by_site)
            
            if sites:
                site_filter = sites[0]["id"]
                logger.debug(f"Found site for filter: {sites[0]['name']} (ID: {site_filter})")
            else:
                logger.warning(f"Site filter '{filter_by_site}' not found, proceeding without site filtering")
        
        # Step 4: Collect resources from all endpoints
        logger.info("Collecting tenant resources from all NetBox endpoints...")
        resource_collections = {}
        total_resources = 0
        
        for resource_type, config in resource_endpoints.items():
            try:
                logger.debug(f"Collecting {resource_type} for tenant {tenant_id}")
                
                # Get the client endpoint
                client_path = config["client_path"]
                endpoint = client
                for path_part in client_path.split('.'):
                    endpoint = getattr(endpoint, path_part)
                
                # Build filter parameters
                filter_params = {"tenant": tenant_id}
                
                # Add site filter if specified and supported
                if site_filter and resource_type in ["devices", "racks", "prefixes", "vlans", "clusters"]:
                    filter_params["site"] = site_filter
                
                # Add status filter if specified
                if filter_by_status:
                    filter_params["status"] = filter_by_status
                
                # Collect resources
                logger.debug(f"Filtering {resource_type} with params: {filter_params}")
                
                # Some endpoints may not support tenant filtering - handle gracefully
                try:
                    resources = endpoint.filter(**filter_params)
                except Exception as filter_error:
                    # If tenant filtering fails, try without tenant filter and post-filter
                    logger.warning(f"Direct tenant filtering failed for {resource_type}, attempting manual filtering: {filter_error}")
                    try:
                        # Get all resources and filter manually
                        all_resources = endpoint.filter()
                        resources = []
                        
                        for resource in all_resources:
                            tenant_field = resource.get("tenant")
                            tenant_matches = False
                            
                            if tenant_field is None:
                                # No tenant assigned
                                continue
                            elif isinstance(tenant_field, dict):
                                # Tenant as object with ID
                                tenant_matches = tenant_field.get("id") == tenant_id
                            elif isinstance(tenant_field, int):
                                # Tenant as direct ID
                                tenant_matches = tenant_field == tenant_id
                            elif isinstance(tenant_field, str):
                                # Sometimes tenant might be a string ID
                                try:
                                    tenant_matches = int(tenant_field) == tenant_id
                                except (ValueError, TypeError):
                                    continue
                            
                            if tenant_matches:
                                resources.append(resource)
                        
                        logger.debug(f"Manual filtering resulted in {len(resources)} {resource_type}")
                    except Exception as manual_error:
                        logger.error(f"Manual filtering also failed for {resource_type}: {manual_error}")
                        resources = []
                
                # Process resources based on detail level
                if include_details:
                    # Full resource details
                    processed_resources = []
                    for resource in resources:
                        resource_data = {
                            "id": resource.get("id"),
                            "url": resource.get("url", ""),
                            "display_url": resource.get("display_url", "")
                        }
                        
                        # Add all available fields for detailed mode
                        for field in resource.keys():
                            if field not in ["id", "url", "display_url"]:
                                resource_data[field] = resource[field]
                        
                        processed_resources.append(resource_data)
                else:
                    # Summary mode - only key fields
                    processed_resources = []
                    summary_fields = config["summary_fields"]
                    
                    for resource in resources:
                        resource_data = {
                            "id": resource.get("id"),
                            "display": resource.get("display", ""),
                            config["display_field"]: resource.get(config["display_field"], "")
                        }
                        
                        # Add summary fields
                        for field in summary_fields:
                            if field in resource:
                                resource_data[field] = resource[field]
                        
                        processed_resources.append(resource_data)
                
                resource_collections[resource_type] = processed_resources
                resource_count = len(processed_resources)
                total_resources += resource_count
                
                logger.info(f"✅ Collected {resource_count} {resource_type} for tenant")
                
            except Exception as e:
                logger.error(f"Failed to collect {resource_type}: {e}")
                resource_collections[resource_type] = []
                logger.warning(f"⚠️ Skipping {resource_type} collection due to error")
        
        # Step 5: Calculate utilization statistics
        utilization_stats = {}
        if include_utilization:
            logger.debug("Calculating resource utilization statistics...")
            
            try:
                # Device utilization
                devices = resource_collections.get("devices", [])
                device_stats = {
                    "total_devices": len(devices),
                    "by_status": {},
                    "by_role": {},
                    "by_site": {}
                }
                
                for device in devices:
                    # Status distribution
                    status = device.get("status", {})
                    status_value = status.get("value", "unknown") if isinstance(status, dict) else str(status)
                    device_stats["by_status"][status_value] = device_stats["by_status"].get(status_value, 0) + 1
                    
                    # Role distribution  
                    role = device.get("device_role", {})
                    role_name = role.get("name", "unknown") if isinstance(role, dict) else str(role)
                    device_stats["by_role"][role_name] = device_stats["by_role"].get(role_name, 0) + 1
                    
                    # Site distribution
                    site = device.get("site", {})
                    site_name = site.get("name", "unknown") if isinstance(site, dict) else str(site)
                    device_stats["by_site"][site_name] = device_stats["by_site"].get(site_name, 0) + 1
                
                utilization_stats["devices"] = device_stats
                
                # IP Address utilization
                ip_addresses = resource_collections.get("ip_addresses", [])
                ip_stats = {
                    "total_ips": len(ip_addresses),
                    "by_status": {},
                    "assigned_vs_unassigned": {"assigned": 0, "unassigned": 0}
                }
                
                for ip in ip_addresses:
                    # Status distribution
                    status = ip.get("status", {})
                    status_value = status.get("value", "unknown") if isinstance(status, dict) else str(status)
                    ip_stats["by_status"][status_value] = ip_stats["by_status"].get(status_value, 0) + 1
                    
                    # Assignment status
                    if ip.get("assigned_object"):
                        ip_stats["assigned_vs_unassigned"]["assigned"] += 1
                    else:
                        ip_stats["assigned_vs_unassigned"]["unassigned"] += 1
                
                utilization_stats["ip_addresses"] = ip_stats
                
                # Prefix utilization
                prefixes = resource_collections.get("prefixes", [])
                prefix_stats = {
                    "total_prefixes": len(prefixes),
                    "by_status": {},
                    "total_ip_space": 0
                }
                
                for prefix in prefixes:
                    # Status distribution
                    status = prefix.get("status", {})
                    status_value = status.get("value", "unknown") if isinstance(status, dict) else str(status)
                    prefix_stats["by_status"][status_value] = prefix_stats["by_status"].get(status_value, 0) + 1
                
                utilization_stats["prefixes"] = prefix_stats
                
                # VLAN utilization
                vlans = resource_collections.get("vlans", [])
                vlan_stats = {
                    "total_vlans": len(vlans),
                    "by_status": {},
                    "vid_ranges": []
                }
                
                vids = []
                for vlan in vlans:
                    # Status distribution
                    status = vlan.get("status", {})
                    status_value = status.get("value", "unknown") if isinstance(status, dict) else str(status)
                    vlan_stats["by_status"][status_value] = vlan_stats["by_status"].get(status_value, 0) + 1
                    
                    # Collect VIDs for range analysis
                    vid = vlan.get("vid")
                    if vid:
                        vids.append(vid)
                
                if vids:
                    vlan_stats["vid_range"] = {"min": min(vids), "max": max(vids)}
                    
                utilization_stats["vlans"] = vlan_stats
                
                logger.info("✅ Utilization statistics calculated")
                
            except Exception as e:
                logger.error(f"Failed to calculate utilization statistics: {e}")
                utilization_stats = {"error": "Failed to calculate statistics"}
        
        # Step 6: Build comprehensive report
        report_timestamp = client.get_server_time() if hasattr(client, 'get_server_time') else None
        
        result = {
            "success": True,
            "action": "generated",
            "report_type": "tenant_resource_report",
            "tenant": {
                "id": tenant_id,
                "name": tenant_obj["name"],
                "slug": tenant_obj.get("slug", ""),
                "description": tenant_obj.get("description", ""),
                "url": tenant_obj.get("url", ""),
                "display_url": tenant_obj.get("display_url", "")
            },
            "filters_applied": {
                "site": filter_by_site,
                "status": filter_by_status,
                "details_included": include_details,
                "utilization_included": include_utilization
            },
            "summary": {
                "total_resources": total_resources,
                "resource_types_found": len([k for k, v in resource_collections.items() if v]),
                "resource_breakdown": {k: len(v) for k, v in resource_collections.items()},
                "report_timestamp": report_timestamp,
                "export_format": export_format
            },
            "resources": resource_collections
        }
        
        # Add utilization stats if requested
        if include_utilization and utilization_stats:
            result["utilization_statistics"] = utilization_stats
        
        # Step 7: Format output based on export format
        if export_format == "summary":
            # Return summary-only view
            result = {
                "success": True,
                "tenant": result["tenant"],
                "summary": result["summary"],
                "resource_counts": {k: len(v) for k, v in resource_collections.items() if v}
            }
        elif export_format == "detailed":
            # Ensure all details are included
            result["export_format"] = "detailed"
            result["detailed_report"] = True
        
        logger.info(f"✅ Tenant resource report generated: {total_resources} total resources across {len([k for k, v in resource_collections.items() if v])} resource types")
        return result
        
    except Exception as e:
        logger.error(f"Failed to generate tenant resource report for {tenant_name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }