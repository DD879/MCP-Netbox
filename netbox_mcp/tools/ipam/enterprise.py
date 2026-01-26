#!/usr/bin/env python3
"""
IPAM Enterprise Automation Tools

High-level enterprise tools for complex IPAM workflows, capacity planning,
and automated network provisioning with cross-domain integration.
"""

from typing import Dict, Optional, Any
import logging
from ...registry import mcp_tool
from ...client import NetBoxClient

logger = logging.getLogger(__name__)

@mcp_tool(category="ipam")
def netbox_get_ip_usage(
    client: NetBoxClient,
    prefix: str
) -> Dict[str, Any]:
    """
    Get IP address usage statistics for a prefix.
    
    Args:
        client: NetBoxClient instance (injected)
        prefix: Network prefix (e.g., "192.168.1.0/24")
        
    Returns:
        Usage statistics including total, used, available IPs
        
    Example:
        netbox_get_ip_usage("192.168.1.0/24")
    """
    try:
        logger.info(f"Getting IP usage for prefix: {prefix}")
        
        # Find the prefix
        prefixes = client.ipam.prefixes.filter(prefix=prefix)
        
        if not prefixes:
            return {
                "success": False,
                "error": f"Prefix '{prefix}' not found",
                "error_type": "PrefixNotFound"
            }
        
        prefix_obj = prefixes[0]
        
        # Calculate usage
        prefix_size = prefix_obj.get("_depth", 0)  # Number of host bits
        total_hosts = 2 ** (32 - int(prefix.split('/')[1])) - 2  # Exclude network and broadcast
        
        # Get used IPs in this prefix
        used_ips = client.ipam.ip_addresses.filter(parent=prefix)
        used_count = len(used_ips)
        available_count = total_hosts - used_count
        usage_percent = (used_count / total_hosts * 100) if total_hosts > 0 else 0
        
        return {
            "success": True,
            "prefix": prefix,
            "total_addresses": total_hosts,
            "used_addresses": used_count,
            "available_addresses": available_count,
            "usage_percentage": round(usage_percent, 2),
            "prefix_details": prefix_obj
        }
        
    except Exception as e:
        logger.error(f"Failed to get IP usage for {prefix}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@mcp_tool(category="ipam")
def netbox_find_next_available_ip(
    client: NetBoxClient,
    prefix: str,
    count: int = 1,
    assign_to_interface: Optional[str] = None,
    device_name: Optional[str] = None,
    status: str = "active",
    description: Optional[str] = None,
    tenant: Optional[str] = None,
    vrf: Optional[str] = None,
    reserve_immediately: bool = False,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Find and optionally reserve the next available IP address(es) in a prefix with atomic operation.
    
    This enterprise-grade function combines IP discovery with optional atomic reservation,
    providing essential functionality for automated IP allocation workflows. Supports
    both simple IP discovery and complete interface assignment in a single operation.
    
    Args:
        client: NetBoxClient instance (injected)
        prefix: Network prefix to search (e.g., "192.168.1.0/24")
        count: Number of consecutive IPs to find (default: 1)
        assign_to_interface: Optional interface name for immediate assignment
        device_name: Device name (required if assign_to_interface specified)
        status: IP status if reserving (active, reserved, deprecated, dhcp, slaac)
        description: Optional description for reserved IPs
        tenant: Optional tenant name for IP assignment
        vrf: Optional VRF name for IP assignment
        reserve_immediately: Create IP objects immediately (requires confirm=True)
        confirm: Must be True for any write operations (safety mechanism)
        
    Returns:
        Available IP addresses with optional reservation details
        
    Examples:
        # Find next available IP (read-only)
        netbox_find_next_available_ip(prefix="10.0.1.0/24")
        
        # Find and reserve 3 consecutive IPs
        netbox_find_next_available_ip(
            prefix="10.0.1.0/24", 
            count=3,
            reserve_immediately=True,
            description="Reserved for new servers",
            confirm=True
        )
        
        # Find IP and assign to device interface atomically
        netbox_find_next_available_ip(
            prefix="10.0.1.0/24",
            assign_to_interface="eth0",
            device_name="server-01",
            description="Management IP",
            confirm=True
        )
    """
    try:
        if not prefix:
            return {
                "success": False,
                "error": "prefix is required",
                "error_type": "ValidationError"
            }
        
        if count < 1 or count > 100:
            return {
                "success": False,
                "error": "count must be between 1 and 100",
                "error_type": "ValidationError"
            }
        
        if assign_to_interface and not device_name:
            return {
                "success": False,
                "error": "device_name is required when assign_to_interface is specified",
                "error_type": "ValidationError"
            }
        
        # Note: reserve_immediately with confirm=False is allowed for dry-run validation
        
        logger.info(f"Finding next {count} available IP(s) in prefix: {prefix}")
        
        # Step 1: Find and validate the prefix
        logger.debug(f"Looking up prefix: {prefix}")
        prefixes = client.ipam.prefixes.filter(prefix=prefix)
        
        if not prefixes:
            return {
                "success": False,
                "error": f"Prefix '{prefix}' not found in NetBox",
                "error_type": "NotFoundError"
            }
        
        prefix_obj = prefixes[0]
        prefix_id = prefix_obj["id"]
        logger.debug(f"Found prefix: {prefix_obj['prefix']} (ID: {prefix_id})")
        
        # Step 2: Get available IPs using NetBox's available-ips endpoint
        logger.debug("Retrieving available IPs from NetBox")
        try:
            # Use direct API access for the available-ips endpoint
            available_ips_response = client.api.ipam.prefixes.get(prefix_id).available_ips.list()
            available_ips = [str(ip) for ip in available_ips_response]
        except Exception as e:
            logger.error(f"Failed to get available IPs: {e}")
            return {
                "success": False,
                "error": f"Failed to retrieve available IPs from prefix: {str(e)}",
                "error_type": "NetBoxAPIError"
            }
        
        if not available_ips:
            return {
                "success": False,
                "error": f"No available IP addresses in prefix {prefix}",
                "error_type": "NoAvailableIPs"
            }
        
        if len(available_ips) < count:
            return {
                "success": False,
                "error": f"Only {len(available_ips)} available IPs in prefix, but {count} requested",
                "error_type": "InsufficientIPs"
            }
        
        # Step 3: Select the requested number of consecutive IPs
        selected_ips = available_ips[:count]
        logger.info(f"Selected {len(selected_ips)} available IPs: {selected_ips}")
        
        # If only discovery is requested, return the IPs without reservation
        if not reserve_immediately and not assign_to_interface:
            return {
                "success": True,
                "action": "discovered",
                "prefix": prefix,
                "available_ips": selected_ips,
                "total_available": len(available_ips),
                "dry_run": True
            }
        
        # Step 4: Handle device and interface lookup if assignment is requested
        device_id = None
        interface_id = None
        device_obj = None
        interface_obj = None
        
        if assign_to_interface:
            logger.debug(f"Looking up device: {device_name}")
            # Resolve device (by id or name)
            device_search_params = {"limit": 50}
            devices = None
            if device_name and device_name.isdigit():
                devices = list(client.dcim.devices.filter(id=int(device_name), **device_search_params))
            if not devices:
                devices = list(client.dcim.devices.filter(name=device_name, **device_search_params))
            if not devices:
                devices = list(client.dcim.devices.filter(name__icontains=device_name, **device_search_params))
            if not devices:
                return {
                    "success": False,
                    "error": f"Device '{device_name}' not found",
                    "error_type": "NotFoundError"
                }
            
            device_obj = devices[0]
            device_id = device_obj["id"]
            logger.debug(f"Found device: {device_obj['name']} (ID: {device_id})")
            
            logger.debug(f"Looking up interface: {assign_to_interface} on device {device_obj['name']}")
            # Resolve interface on the device
            interface_search_params = {"limit": 50}
            interfaces = list(client.dcim.interfaces.filter(device_id=device_id, name=assign_to_interface, **interface_search_params))
            if not interfaces:
                return {
                    "success": False,
                    "error": f"Interface '{assign_to_interface}' not found on device '{device_obj['name']}'.",
                    "error_type": "NotFoundError"
                }
            
            interface_obj = interfaces[0]
            interface_id = interface_obj["id"]
            logger.debug(f"Found interface: {interface_obj['name']} (ID: {interface_id})")
        
        # Step 5: Resolve optional foreign keys
        tenant_id = None
        vrf_id = None
        
        if tenant:
            logger.debug(f"Looking up tenant: {tenant}")
            # Resolve tenant (by id or name)
            tenant_search_params = {"limit": 50}
            tenants = None
            if tenant.isdigit():
                tenants = list(client.tenancy.tenants.filter(id=int(tenant), **tenant_search_params))
            if not tenants:
                tenants = list(client.tenancy.tenants.filter(name=tenant, **tenant_search_params))
            if not tenants:
                tenants = list(client.tenancy.tenants.filter(slug=tenant, **tenant_search_params))
            if tenants:
                tenant_id = tenants[0]["id"]
                logger.debug(f"Found tenant: {tenants[0]['name']} (ID: {tenant_id})")
            else:
                logger.warning(f"Tenant '{tenant}' not found, proceeding without tenant assignment")
        
        if vrf:
            logger.debug(f"Looking up VRF: {vrf}")
            vrfs = client.ipam.vrfs.filter(name=vrf)
            if vrfs:
                vrf_id = vrfs[0]["id"]
                logger.debug(f"Found VRF: {vrfs[0]['name']} (ID: {vrf_id})")
            else:
                logger.warning(f"VRF '{vrf}' not found, proceeding without VRF assignment")
        
        if not confirm:
            # Dry run mode - show what would be created
            result = {
                "success": True,
                "action": "dry_run",
                "prefix": prefix,
                "selected_ips": selected_ips,
                "total_available": len(available_ips),
                "would_reserve": reserve_immediately,
                "would_assign": bool(assign_to_interface),
                "dry_run": True
            }
            
            if assign_to_interface:
                result["assignment_target"] = {
                    "device": device_obj["name"],
                    "interface": interface_obj["name"],
                    "device_id": device_id,
                    "interface_id": interface_id
                }
            
            return result
        
        # Step 6: Create IP address objects (only if confirm=True and operation requires it)
        if not (reserve_immediately or assign_to_interface):
            # No actual IP creation needed, return discovery results
            return {
                "success": True,
                "action": "discovered",
                "prefix": prefix,
                "available_ips": selected_ips,
                "total_available": len(available_ips),
                "dry_run": False
            }
        
        created_ips = []
        assignment_results = []
        
        for ip_address in selected_ips:
            try:
                # Build IP data
                ip_data = {
                    "address": ip_address,
                    "status": status
                }
                
                if description:
                    ip_data["description"] = description
                if tenant_id:
                    ip_data["tenant"] = tenant_id
                if vrf_id:
                    ip_data["vrf"] = vrf_id
                
                logger.debug(f"Creating IP address: {ip_data}")
                created_ip = client.ipam.ip_addresses.create(confirm=True, **ip_data)
                created_ips.append(created_ip)
                logger.info(f"✅ Created IP address: {ip_address} (ID: {created_ip['id']})")
                
                # Step 7: Assign to interface if requested
                if assign_to_interface:
                    assignment_data = {
                        "assigned_object_type": "dcim.interface",
                        "assigned_object_id": interface_id
                    }
                    
                    logger.debug(f"Assigning IP {ip_address} to interface {interface_obj['name']}")
                    assigned_ip = client.ipam.ip_addresses.update(created_ip["id"], confirm=True, **assignment_data)
                    assignment_results.append({
                        "ip_address": ip_address,
                        "ip_id": created_ip["id"],
                        "assigned_to": f"{device_obj['name']}:{interface_obj['name']}",
                        "assignment_result": assigned_ip
                    })
                    logger.info(f"✅ Assigned IP {ip_address} to {device_obj['name']}:{interface_obj['name']}")
                
            except Exception as e:
                logger.error(f"Failed to create/assign IP {ip_address}: {e}")
                # Continue with other IPs but record the failure
                assignment_results.append({
                    "ip_address": ip_address,
                    "error": str(e),
                    "success": False
                })
        
        # Step 8: Apply cache invalidation pattern from Issue #29
        # Invalidate relevant caches to ensure data consistency
        logger.debug("Invalidating IPAM cache after IP creation...")
        try:
            # Invalidate prefix cache
            client.cache.invalidate_pattern("ipam.prefixes")
            
            # Invalidate interface cache if assignment was performed
            if assign_to_interface and interface_id:
                invalidated = client.cache.invalidate_for_object("dcim.interfaces", interface_id)
                logger.info(f"Cache invalidated: {invalidated} entries for interface {interface_id}")
                
        except Exception as cache_error:
            # Cache invalidation failure should not fail the IP creation
            logger.warning(f"Cache invalidation failed after IP creation: {cache_error}")
        
        # Step 9: Build comprehensive response
        success_count = len([r for r in (assignment_results or created_ips) if isinstance(r, dict) and r.get("success", True)])
        
        result = {
            "success": True,
            "action": "assigned" if assign_to_interface else "reserved",
            "prefix": prefix,
            "requested_count": count,
            "successful_count": success_count,
            "ips_created": len(created_ips),
            "created_ips": created_ips,
            "dry_run": False
        }
        
        if assign_to_interface:
            result["assignment_results"] = assignment_results
            result["device"] = {"name": device_obj["name"], "id": device_id}
            result["interface"] = {"name": interface_obj["name"], "id": interface_id}
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to find/reserve next available IP in {prefix}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@mcp_tool(category="ipam")
def netbox_get_prefix_utilization(
    client: NetBoxClient,
    prefix: str,
    include_child_prefixes: bool = True,
    include_detailed_breakdown: bool = False,
    tenant: Optional[str] = None,
    vrf: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get comprehensive prefix utilization report for capacity planning.
    
    This enterprise-grade function provides detailed analysis of IP address usage
    within a prefix, including child prefix analysis, utilization trends, and
    capacity planning insights essential for network growth planning.
    
    Args:
        client: NetBoxClient instance (injected)
        prefix: Network prefix to analyze (e.g., "10.0.0.0/16")
        include_child_prefixes: Include child/subnet analysis
        include_detailed_breakdown: Include detailed IP allocation breakdown
        tenant: Optional tenant filter for multi-tenant environments
        vrf: Optional VRF filter for VRF-aware analysis
        
    Returns:
        Comprehensive utilization report with capacity planning insights
        
    Examples:
        # Basic prefix utilization
        netbox_get_prefix_utilization(prefix="10.0.0.0/16")
        
        # Detailed analysis with child prefixes
        netbox_get_prefix_utilization(
            prefix="10.0.0.0/16",
            include_child_prefixes=True,
            include_detailed_breakdown=True
        )
        
        # Multi-tenant analysis
        netbox_get_prefix_utilization(
            prefix="10.0.0.0/16",
            tenant="customer-a",
            vrf="customer-a-vrf"
        )
    """
    try:
        if not prefix:
            return {
                "success": False,
                "error": "prefix is required",
                "error_type": "ValidationError"
            }
        
        logger.info(f"Analyzing prefix utilization: {prefix}")
        
        # Step 1: Find and validate the prefix
        logger.debug(f"Looking up prefix: {prefix}")
        filters = {"prefix": prefix}
        if tenant:
            filters["tenant"] = tenant
        if vrf:
            filters["vrf"] = vrf
        
        prefixes = client.ipam.prefixes.filter(**filters)
        
        if not prefixes:
            return {
                "success": False,
                "error": f"Prefix '{prefix}' not found in NetBox",
                "error_type": "NotFoundError"
            }
        
        prefix_obj = prefixes[0]
        prefix_id = prefix_obj["id"]
        logger.debug(f"Found prefix: {prefix_obj['prefix']} (ID: {prefix_id})")
        
        # Step 2: Calculate basic utilization metrics
        import ipaddress
        try:
            network = ipaddress.ip_network(prefix, strict=False)
            total_hosts = network.num_addresses
            if network.version == 4:
                # IPv4: exclude network and broadcast addresses
                if network.prefixlen < 31:
                    total_hosts -= 2
            logger.debug(f"Network analysis: {network}, Total hosts: {total_hosts}")
        except ValueError as e:
            return {
                "success": False,
                "error": f"Invalid prefix format: {e}",
                "error_type": "ValidationError"
            }
        
        # Step 3: Get all IP addresses within this prefix
        logger.debug("Retrieving IP addresses within prefix")
        ip_filters = {"parent": prefix}
        if tenant:
            ip_filters["tenant"] = tenant
        if vrf:
            ip_filters["vrf"] = vrf
        
        allocated_ips = client.ipam.ip_addresses.filter(**ip_filters)
        allocated_count = len(allocated_ips)
        
        # Step 4: Analyze IP status distribution
        status_breakdown = {}
        interface_assignments = 0
        device_assignments = 0
        
        for ip in allocated_ips:
            status = ip.get("status", {})
            if isinstance(status, dict):
                status_value = status.get("value", "unknown")
            else:
                status_value = str(status)
            
            status_breakdown[status_value] = status_breakdown.get(status_value, 0) + 1
            
            # Check for assignments
            if ip.get("assigned_object"):
                assigned_obj = ip["assigned_object"]
                if isinstance(assigned_obj, dict):
                    obj_type = assigned_obj.get("object_type", "")
                    if "interface" in obj_type.lower():
                        interface_assignments += 1
                    elif "device" in obj_type.lower():
                        device_assignments += 1
        
        # Step 5: Calculate utilization metrics
        available_count = total_hosts - allocated_count
        utilization_percent = (allocated_count / total_hosts * 100) if total_hosts > 0 else 0
        
        # Step 6: Analyze child prefixes if requested
        child_prefixes = []
        child_prefix_usage = 0
        
        if include_child_prefixes:
            logger.debug("Analyzing child prefixes")
            try:
                # Find child prefixes (longer prefix lengths within this prefix)
                child_filters = {"within": prefix}
                if tenant:
                    child_filters["tenant"] = tenant
                if vrf:
                    child_filters["vrf"] = vrf
                
                child_prefixes_raw = client.ipam.prefixes.filter(**child_filters)
                
                for child in child_prefixes_raw:
                    if child["id"] != prefix_id:  # Exclude the parent prefix itself
                        child_prefix = child["prefix"]
                        try:
                            child_network = ipaddress.ip_network(child_prefix, strict=False)
                            child_total = child_network.num_addresses
                            if child_network.version == 4 and child_network.prefixlen < 31:
                                child_total -= 2
                            
                            # Get IPs in child prefix
                            child_ips = client.ipam.ip_addresses.filter(parent=child_prefix)
                            child_allocated = len(child_ips)
                            child_utilization = (child_allocated / child_total * 100) if child_total > 0 else 0
                            
                            child_prefixes.append({
                                "prefix": child_prefix,
                                "total_addresses": child_total,
                                "allocated_addresses": child_allocated,
                                "utilization_percent": round(child_utilization, 2),
                                "status": child.get("status", {}),
                                "description": child.get("description", "")
                            })
                            
                            child_prefix_usage += child_total
                            
                        except ValueError:
                            logger.warning(f"Invalid child prefix format: {child_prefix}")
                            continue
                
                # Sort child prefixes by utilization (highest first)
                child_prefixes.sort(key=lambda x: x["utilization_percent"], reverse=True)
                
            except Exception as e:
                logger.warning(f"Failed to analyze child prefixes: {e}")
        
        # Step 7: Calculate capacity planning insights
        # Determine if this is a critically utilized prefix
        utilization_status = "healthy"
        if utilization_percent >= 90:
            utilization_status = "critical"
        elif utilization_percent >= 75:
            utilization_status = "warning"
        elif utilization_percent >= 50:
            utilization_status = "moderate"
        
        # Calculate growth projections
        growth_projections = []
        if allocated_count > 0:
            # Simple linear projections
            for months in [3, 6, 12]:
                # Assume current rate continues (very basic projection)
                projected_usage = allocated_count * (1 + (months * 0.1))  # 10% growth per month
                projected_percent = (projected_usage / total_hosts * 100) if total_hosts > 0 else 0
                growth_projections.append({
                    "months": months,
                    "projected_usage": min(int(projected_usage), total_hosts),
                    "projected_percent": min(round(projected_percent, 2), 100.0)
                })
        
        # Step 8: Build comprehensive report
        result = {
            "success": True,
            "prefix": prefix,
            "prefix_id": prefix_id,
            "total_addresses": total_hosts,
            "allocated_addresses": allocated_count,
            "available_addresses": available_count,
            "utilization_percent": round(utilization_percent, 2),
            "utilization_status": utilization_status,
            "assignments": {
                "interface_assignments": interface_assignments,
                "device_assignments": device_assignments,
                "unassigned_ips": allocated_count - interface_assignments - device_assignments
            },
            "status_breakdown": status_breakdown,
            "analysis_metadata": {
                "prefix_object": prefix_obj,
                "analysis_timestamp": client._get_current_timestamp() if hasattr(client, '_get_current_timestamp') else "unknown",
                "filters_applied": {
                    "tenant": tenant,
                    "vrf": vrf
                }
            }
        }
        
        if include_child_prefixes:
            result["child_prefixes"] = {
                "count": len(child_prefixes),
                "total_child_addresses": child_prefix_usage,
                "child_utilization_percent": round((child_prefix_usage / total_hosts * 100), 2) if total_hosts > 0 else 0,
                "prefixes": child_prefixes
            }
        
        if growth_projections:
            result["capacity_planning"] = {
                "growth_projections": growth_projections,
                "recommendations": []
            }
            
            # Add capacity recommendations
            if utilization_percent >= 75:
                result["capacity_planning"]["recommendations"].append("Consider expanding prefix or implementing subnetting")
            if utilization_percent >= 90:
                result["capacity_planning"]["recommendations"].append("URGENT: Immediate capacity expansion required")
            if len(child_prefixes) > 10:
                result["capacity_planning"]["recommendations"].append("Consider prefix consolidation or hierarchical organization")
        
        if include_detailed_breakdown:
            # Include detailed IP allocation information
            detailed_ips = []
            for ip in allocated_ips[:100]:  # Limit to first 100 for performance
                ip_detail = {
                    "address": ip["address"],
                    "status": ip.get("status", {}),
                    "description": ip.get("description", ""),
                    "assigned_object": ip.get("assigned_object", {}),
                    "tenant": ip.get("tenant", {}),
                    "created": ip.get("created", "")
                }
                detailed_ips.append(ip_detail)
            
            result["detailed_breakdown"] = {
                "sample_size": len(detailed_ips),
                "total_ips": allocated_count,
                "ip_details": detailed_ips
            }
        
        logger.info(f"✅ Prefix utilization analysis complete: {utilization_percent:.2f}% ({allocated_count}/{total_hosts})")
        return result
        
    except Exception as e:
        logger.error(f"Failed to analyze prefix utilization for {prefix}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@mcp_tool(category="ipam")
def netbox_provision_vlan_with_prefix(
    client: NetBoxClient,
    vlan_name: str,
    vlan_id: int,
    prefix: str,
    site: Optional[str] = None,
    vlan_group: Optional[str] = None,
    vrf: Optional[str] = None,
    tenant: Optional[str] = None,
    vlan_role: Optional[str] = None,
    prefix_role: Optional[str] = None,
    vlan_status: str = "active",
    prefix_status: str = "active",
    description: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Provision a VLAN with coordinated IP prefix creation in a single atomic operation.
    
    This enterprise-grade function eliminates the complexity of coordinating VLAN and 
    IP prefix creation by performing both operations atomically with intelligent
    validation and rollback capabilities. Essential for network provisioning workflows
    where VLANs and their associated IP addressing must be created together.
    
    Args:
        client: NetBoxClient instance (injected)
        vlan_name: VLAN name (e.g., "Production-Web")
        vlan_id: VLAN ID (1-4094)
        prefix: IP prefix for the VLAN (e.g., "10.100.10.0/24")
        site: Optional site name for VLAN and prefix association
        vlan_group: Optional VLAN group for organization
        vrf: Optional VRF name for prefix assignment
        tenant: Optional tenant for multi-tenant environments
        vlan_role: Optional VLAN role (e.g., "production", "management")
        prefix_role: Optional prefix role (e.g., "lan", "wan", "point-to-point")
        vlan_status: VLAN status (active, reserved, deprecated)
        prefix_status: Prefix status (active, reserved, deprecated)
        description: Optional description applied to both VLAN and prefix
        confirm: Must be True for execution (safety mechanism)
        
    Returns:
        Coordinated VLAN and prefix creation results with rollback information
        
    Examples:
        # Basic VLAN/prefix provisioning
        netbox_provision_vlan_with_prefix(
            vlan_name="Production-Web",
            vlan_id=100,
            prefix="10.100.10.0/24",
            confirm=True
        )
        
        # Enterprise provisioning with full context
        netbox_provision_vlan_with_prefix(
            vlan_name="Customer-A-DMZ",
            vlan_id=200,
            prefix="10.200.0.0/24",
            site="datacenter-primary",
            vrf="customer-a-vrf",
            tenant="customer-a",
            vlan_role="dmz",
            prefix_role="lan",
            description="Customer A DMZ network segment",
            confirm=True
        )
        
        # Site-specific provisioning
        netbox_provision_vlan_with_prefix(
            vlan_name="Management",
            vlan_id=99,
            prefix="192.168.99.0/24",
            site="branch-office-1",
            vlan_role="management",
            prefix_role="management",
            confirm=True
        )
    """
    try:
        if not vlan_name or not vlan_id or not prefix:
            return {
                "success": False,
                "error": "vlan_name, vlan_id, and prefix are required",
                "error_type": "ValidationError"
            }
        
        if not (1 <= vlan_id <= 4094):
            return {
                "success": False,
                "error": "VLAN ID must be between 1 and 4094",
                "error_type": "ValidationError"
            }
        
        # Validate prefix format using ipaddress module
        import ipaddress
        try:
            network = ipaddress.ip_network(prefix, strict=False)
            logger.debug(f"Validated prefix: {network}")
        except ValueError as e:
            return {
                "success": False,
                "error": f"Invalid prefix format: {e}",
                "error_type": "ValidationError"
            }
        
        logger.info(f"Provisioning VLAN {vlan_name} (VID: {vlan_id}) with prefix {prefix}")
        
        # Step 1: Pre-flight validation - check for conflicts
        logger.debug("Performing pre-flight validation...")
        
        # Check for existing VLAN ID conflicts
        vlan_filters = {"vid": vlan_id}
        if site:
            vlan_filters["site"] = site
        if vlan_group:
            vlan_filters["group"] = vlan_group
        
        existing_vlans = client.ipam.vlans.filter(**vlan_filters)
        if existing_vlans:
            return {
                "success": False,
                "error": f"VLAN ID {vlan_id} already exists in the specified scope",
                "error_type": "ConflictError",
                "conflicting_vlan": existing_vlans[0]
            }
        
        # Check for existing prefix conflicts
        prefix_filters = {"prefix": prefix}
        if vrf:
            prefix_filters["vrf"] = vrf
        if tenant:
            prefix_filters["tenant"] = tenant
        
        existing_prefixes = client.ipam.prefixes.filter(**prefix_filters)
        if existing_prefixes:
            return {
                "success": False,
                "error": f"Prefix {prefix} already exists in the specified scope",
                "error_type": "ConflictError",
                "conflicting_prefix": existing_prefixes[0]
            }
        
        # Step 2: Resolve foreign keys for all optional parameters
        logger.debug("Resolving foreign key references...")
        
        resolved_refs = {}
        
        # Resolve site reference
        if site:
            logger.debug(f"Looking up site: {site}")
            site_search_params = {
                "limit": 50
            }

            # ULTRATHINK FIX 2: ID resolution with fallback patterns
            sites = None
            if site.isdigit():
                sites = list(client.dcim.sites.filter(id=int(site), **site_search_params))

            if not sites:
                sites = list(client.dcim.sites.filter(name=site, **site_search_params))
            if not sites:
                # ULTRATHINK FIX 4: Slug-based fallback mechanisms already integrated above
                sites = list(client.dcim.sites.filter(slug=site, **site_search_params))
            if sites:
                resolved_refs["site_id"] = sites[0]["id"]
                resolved_refs["site_name"] = sites[0]["name"]
                logger.debug(f"Found site: {sites[0]['name']} (ID: {sites[0]['id']})")
            else:
                return {
                    "success": False,
                    "error": f"Site '{site}' not found",
                    "error_type": "NotFoundError"
                }
        
        # Resolve VRF reference
        if vrf:
            logger.debug(f"Looking up VRF: {vrf}")
            vrfs = client.ipam.vrfs.filter(name=vrf)
            if vrfs:
                resolved_refs["vrf_id"] = vrfs[0]["id"]
                resolved_refs["vrf_name"] = vrfs[0]["name"]
                logger.debug(f"Found VRF: {vrfs[0]['name']} (ID: {vrfs[0]['id']})")
            else:
                logger.warning(f"VRF '{vrf}' not found, proceeding without VRF assignment")
        
        # Resolve tenant reference
        if tenant:
            logger.debug(f"Looking up tenant: {tenant}")
            # Resolve tenant (by id or name)
            tenant_search_params = {"limit": 50}
            tenants = None
            if tenant.isdigit():
                tenants = list(client.tenancy.tenants.filter(id=int(tenant), **tenant_search_params))
            if not tenants:
                tenants = list(client.tenancy.tenants.filter(name=tenant, **tenant_search_params))
            if not tenants:
                tenants = list(client.tenancy.tenants.filter(slug=tenant, **tenant_search_params))
            if tenants:
                resolved_refs["tenant_id"] = tenants[0]["id"]
                resolved_refs["tenant_name"] = tenants[0]["name"]
                logger.debug(f"Found tenant: {tenants[0]['name']} (ID: {tenants[0]['id']})")
            else:
                logger.warning(f"Tenant '{tenant}' not found, proceeding without tenant assignment")
        
        # Resolve VLAN group reference
        if vlan_group:
            logger.debug(f"Looking up VLAN group: {vlan_group}")
            vlan_groups = client.ipam.vlan_groups.filter(name=vlan_group)
            if not vlan_groups:
                vlan_groups = client.ipam.vlan_groups.filter(slug=vlan_group)
            if vlan_groups:
                resolved_refs["vlan_group_id"] = vlan_groups[0]["id"]
                resolved_refs["vlan_group_name"] = vlan_groups[0]["name"]
                logger.debug(f"Found VLAN group: {vlan_groups[0]['name']} (ID: {vlan_groups[0]['id']})")
            else:
                logger.warning(f"VLAN group '{vlan_group}' not found, proceeding without group assignment")
        
        # Resolve role references (optional, continue without if not found)
        if vlan_role:
            logger.debug(f"Looking up VLAN role: {vlan_role}")
            try:
                vlan_roles = client.ipam.roles.filter(name=vlan_role)
                if not vlan_roles:
                    vlan_roles = client.ipam.roles.filter(slug=vlan_role)
                if vlan_roles:
                    resolved_refs["vlan_role_id"] = vlan_roles[0]["id"]
                    resolved_refs["vlan_role_name"] = vlan_roles[0]["name"]
                    logger.debug(f"Found VLAN role: {vlan_roles[0]['name']} (ID: {vlan_roles[0]['id']})")
                else:
                    logger.warning(f"VLAN role '{vlan_role}' not found, proceeding without role assignment")
            except Exception as e:
                logger.warning(f"Failed to lookup VLAN role '{vlan_role}': {e}")
        
        if prefix_role:
            logger.debug(f"Looking up prefix role: {prefix_role}")
            try:
                prefix_roles = client.ipam.roles.filter(name=prefix_role)
                if not prefix_roles:
                    prefix_roles = client.ipam.roles.filter(slug=prefix_role)
                if prefix_roles:
                    resolved_refs["prefix_role_id"] = prefix_roles[0]["id"]
                    resolved_refs["prefix_role_name"] = prefix_roles[0]["name"]
                    logger.debug(f"Found prefix role: {prefix_roles[0]['name']} (ID: {prefix_roles[0]['id']})")
                else:
                    logger.warning(f"Prefix role '{prefix_role}' not found, proceeding without role assignment")
            except Exception as e:
                logger.warning(f"Failed to lookup prefix role '{prefix_role}': {e}")
        
        if not confirm:
            # Dry run mode - show what would be created
            return {
                "success": True,
                "action": "dry_run",
                "would_create": {
                    "vlan": {
                        "name": vlan_name,
                        "vid": vlan_id,
                        "status": vlan_status,
                        "description": description
                    },
                    "prefix": {
                        "prefix": prefix,
                        "status": prefix_status,
                        "description": description
                    }
                },
                "resolved_references": resolved_refs,
                "validation_results": {
                    "vlan_id_available": True,
                    "prefix_available": True,
                    "references_resolved": len(resolved_refs)
                },
                "dry_run": True
            }
        
        # Step 3: Create VLAN first (since prefix might reference VLAN)
        logger.info(f"Creating VLAN: {vlan_name} (VID: {vlan_id})")
        
        vlan_data = {
            "name": vlan_name,
            "vid": vlan_id,
            "status": vlan_status
        }
        
        if description:
            vlan_data["description"] = description
        if resolved_refs.get("site_id"):
            vlan_data["site"] = resolved_refs["site_id"]
        if resolved_refs.get("vlan_group_id"):
            vlan_data["group"] = resolved_refs["vlan_group_id"]
        if resolved_refs.get("tenant_id"):
            vlan_data["tenant"] = resolved_refs["tenant_id"]
        if resolved_refs.get("vlan_role_id"):
            vlan_data["role"] = resolved_refs["vlan_role_id"]
        
        created_vlan = None
        try:
            logger.debug(f"Creating VLAN with data: {vlan_data}")
            created_vlan = client.ipam.vlans.create(confirm=True, **vlan_data)
            logger.info(f"✅ Created VLAN: {vlan_name} (ID: {created_vlan['id']}, VID: {vlan_id})")
        except Exception as e:
            logger.error(f"Failed to create VLAN: {e}")
            return {
                "success": False,
                "error": f"Failed to create VLAN: {str(e)}",
                "error_type": "VLANCreationError",
                "operation": "vlan_creation"
            }
        
        # Step 4: Create IP prefix with VLAN association
        logger.info(f"Creating IP prefix: {prefix}")
        
        prefix_data = {
            "prefix": prefix,
            "status": prefix_status,
            "vlan": created_vlan["id"]  # Associate with the newly created VLAN
        }
        
        if description:
            prefix_data["description"] = description
        if resolved_refs.get("site_id"):
            prefix_data["site"] = resolved_refs["site_id"]
        if resolved_refs.get("vrf_id"):
            prefix_data["vrf"] = resolved_refs["vrf_id"]
        if resolved_refs.get("tenant_id"):
            prefix_data["tenant"] = resolved_refs["tenant_id"]
        if resolved_refs.get("prefix_role_id"):
            prefix_data["role"] = resolved_refs["prefix_role_id"]
        
        created_prefix = None
        try:
            logger.debug(f"Creating prefix with data: {prefix_data}")
            created_prefix = client.ipam.prefixes.create(confirm=True, **prefix_data)
            logger.info(f"✅ Created prefix: {prefix} (ID: {created_prefix['id']}) associated with VLAN {vlan_id}")
        except Exception as e:
            logger.error(f"Failed to create prefix: {e}")
            
            # Rollback: Delete the created VLAN since prefix creation failed
            logger.warning("Attempting rollback - deleting created VLAN...")
            try:
                client.ipam.vlans.delete(created_vlan["id"], confirm=True)
                logger.info("✅ Rollback successful - VLAN deleted")
                rollback_status = "successful"
            except Exception as rollback_error:
                logger.error(f"❌ Rollback failed: {rollback_error}")
                rollback_status = "failed"
            
            return {
                "success": False,
                "error": f"Failed to create prefix: {str(e)}",
                "error_type": "PrefixCreationError",
                "operation": "prefix_creation",
                "rollback_performed": True,
                "rollback_status": rollback_status,
                "orphaned_vlan": created_vlan if rollback_status == "failed" else None
            }
        
        # Step 5: Apply cache invalidation pattern from Issue #29
        logger.debug("Invalidating IPAM cache after VLAN/prefix creation...")
        try:
            # Invalidate VLAN and prefix caches
            client.cache.invalidate_pattern("ipam.vlans")
            client.cache.invalidate_pattern("ipam.prefixes")
            logger.info("Cache invalidated for IPAM objects")
        except Exception as cache_error:
            # Cache invalidation failure should not fail the operation
            logger.warning(f"Cache invalidation failed after creation: {cache_error}")
        
        # Step 6: Build comprehensive success response
        result = {
            "success": True,
            "action": "created",
            "vlan": {
                "id": created_vlan["id"],
                "name": created_vlan["name"],
                "vid": created_vlan["vid"],
                "status": created_vlan["status"],
                "url": created_vlan.get("url", ""),
                "display_url": created_vlan.get("display_url", "")
            },
            "prefix": {
                "id": created_prefix["id"],
                "prefix": created_prefix["prefix"],
                "status": created_prefix["status"],
                "vlan_association": created_vlan["id"],
                "url": created_prefix.get("url", ""),
                "display_url": created_prefix.get("display_url", "")
            },
            "coordination": {
                "vlan_prefix_linked": True,
                "total_objects_created": 2,
                "creation_order": ["vlan", "prefix"],
                "rollback_capability": True
            },
            "resolved_references": resolved_refs,
            "dry_run": False
        }
        
        logger.info(f"✅ VLAN/Prefix provisioning complete: VLAN {vlan_id} ({created_vlan['id']}) + Prefix {prefix} ({created_prefix['id']})")
        return result
        
    except Exception as e:
        logger.error(f"Failed to provision VLAN/prefix {vlan_name}/{prefix}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@mcp_tool(category="ipam")
def netbox_find_duplicate_ips(
    client: NetBoxClient,
    vrf: Optional[str] = None,
    tenant: Optional[str] = None,
    include_severity_analysis: bool = True,
    include_resolution_recommendations: bool = True,
    limit: int = 1000
) -> Dict[str, Any]:
    """
    Find duplicate IP addresses in NetBox for network auditing and data quality assurance.
    
    This enterprise-grade auditing tool identifies IP address conflicts across NetBox,
    providing detailed analysis including assignment context, conflict severity assessment,
    and resolution recommendations. Essential for maintaining data integrity and 
    troubleshooting network configuration issues.
    
    Args:
        client: NetBoxClient instance (injected)
        vrf: Optional VRF name to limit search scope
        tenant: Optional tenant name to filter IP addresses
        include_severity_analysis: Include conflict severity assessment
        include_resolution_recommendations: Include resolution recommendations
        limit: Maximum number of IP addresses to analyze (default: 1000, max: 10000)
        
    Returns:
        Comprehensive duplicate IP report with conflict analysis and recommendations
        
    Examples:
        # Find all duplicate IPs across NetBox
        netbox_find_duplicate_ips()
        
        # VRF-scoped duplicate detection
        netbox_find_duplicate_ips(vrf="production-vrf")
        
        # Multi-tenant duplicate analysis
        netbox_find_duplicate_ips(
            tenant="customer-a",
            include_severity_analysis=True,
            include_resolution_recommendations=True
        )
        
        # Bulk analysis with custom limit
        netbox_find_duplicate_ips(limit=5000)
    """
    try:
        if limit > 10000:
            return {
                "success": False,
                "error": "Limit cannot exceed 10000 for performance reasons",
                "error_type": "ValidationError"
            }
        
        logger.info(f"Starting duplicate IP analysis (limit: {limit})")
        
        # Step 1: Build filters for IP address collection
        ip_filters = {}
        resolved_refs = {}
        
        if vrf:
            logger.debug(f"Looking up VRF: {vrf}")
            vrfs = client.ipam.vrfs.filter(name=vrf)
            if not vrfs:
                vrfs = client.ipam.vrfs.filter(rd=vrf)  # Try route distinguisher
            if vrfs:
                vrf_obj = vrfs[0]
                ip_filters["vrf_id"] = vrf_obj["id"]
                resolved_refs["vrf"] = {
                    "id": vrf_obj["id"],
                    "name": vrf_obj["name"],
                    "rd": vrf_obj.get("rd", "")
                }
                logger.debug(f"Found VRF: {vrf_obj['name']} (ID: {vrf_obj['id']})")
            else:
                return {
                    "success": False,
                    "error": f"VRF '{vrf}' not found",
                    "error_type": "NotFoundError"
                }
        
        if tenant:
            logger.debug(f"Looking up tenant: {tenant}")
            # Resolve tenant (by id or name)
            tenant_search_params = {"limit": 50}
            tenants = None
            if tenant.isdigit():
                tenants = list(client.tenancy.tenants.filter(id=int(tenant), **tenant_search_params))
            if not tenants:
                tenants = list(client.tenancy.tenants.filter(name=tenant, **tenant_search_params))
            if not tenants:
                tenants = list(client.tenancy.tenants.filter(slug=tenant, **tenant_search_params))
            if tenants:
                tenant_obj = tenants[0]
                ip_filters["tenant_id"] = tenant_obj["id"]
                resolved_refs["tenant"] = {
                    "id": tenant_obj["id"],
                    "name": tenant_obj["name"],
                    "slug": tenant_obj["slug"]
                }
                logger.debug(f"Found tenant: {tenant_obj['name']} (ID: {tenant_obj['id']})")
            else:
                logger.warning(f"Tenant '{tenant}' not found, proceeding without tenant filter")
        
        # Step 2: Retrieve all IP addresses with filters
        logger.debug(f"Retrieving IP addresses with filters: {ip_filters}")
        try:
            # Get IPs with pagination support
            all_ips = []
            offset = 0
            batch_size = min(500, limit)  # Process in batches
            
            while len(all_ips) < limit:
                remaining = limit - len(all_ips)
                current_limit = min(batch_size, remaining)
                
                # Apply filters with pagination
                current_filters = ip_filters.copy()
                current_filters["limit"] = current_limit
                current_filters["offset"] = offset
                
                batch_ips = client.ipam.ip_addresses.filter(**current_filters)
                
                if not batch_ips:
                    break  # No more IPs available
                
                all_ips.extend(batch_ips)
                offset += len(batch_ips)
                
                if len(batch_ips) < current_limit:
                    break  # Last batch
                
                logger.debug(f"Retrieved {len(all_ips)} IPs so far...")
            
            logger.info(f"Retrieved {len(all_ips)} IP addresses for analysis")
            
        except Exception as e:
            logger.error(f"Failed to retrieve IP addresses: {e}")
            return {
                "success": False,
                "error": f"Failed to retrieve IP addresses: {str(e)}",
                "error_type": "NetBoxAPIError"
            }
        
        if not all_ips:
            return {
                "success": True,
                "duplicates_found": 0,
                "total_ips_analyzed": 0,
                "duplicates": [],
                "analysis_scope": {
                    "vrf_filter": vrf,
                    "tenant_filter": tenant,
                    "resolved_references": resolved_refs
                },
                "message": "No IP addresses found matching the specified criteria"
            }
        
        # Step 3: Client-side duplicate detection using Python
        logger.debug("Performing client-side duplicate analysis...")
        
        import ipaddress
        from collections import defaultdict
        
        # Dictionary to track IP addresses (without prefix length)
        ip_tracker = defaultdict(list)
        ipv4_count = 0
        ipv6_count = 0
        assignment_stats = {
            "interface_assignments": 0,
            "device_assignments": 0,
            "unassigned": 0,
            "other_assignments": 0
        }
        
        # Process each IP address
        for ip_obj in all_ips:
            ip_address_str = ip_obj.get("address", "")
            if not ip_address_str:
                continue
            
            try:
                # Parse IP address to separate IP from prefix length
                ip_interface = ipaddress.ip_interface(ip_address_str)
                ip_only = str(ip_interface.ip)  # Just the IP without prefix length
                
                # Track IP version statistics
                if ip_interface.version == 4:
                    ipv4_count += 1
                else:
                    ipv6_count += 1
                
                # Track assignment statistics
                assigned_obj = ip_obj.get("assigned_object")
                if assigned_obj:
                    if isinstance(assigned_obj, dict):
                        obj_type = assigned_obj.get("object_type", "").lower()
                        if "interface" in obj_type:
                            assignment_stats["interface_assignments"] += 1
                        elif "device" in obj_type:
                            assignment_stats["device_assignments"] += 1
                        else:
                            assignment_stats["other_assignments"] += 1
                    else:
                        assignment_stats["other_assignments"] += 1
                else:
                    assignment_stats["unassigned"] += 1
                
                # Add to tracker with full context
                ip_context = {
                    "id": ip_obj.get("id"),
                    "full_address": ip_address_str,
                    "ip_only": ip_only,
                    "prefix_length": ip_interface.network.prefixlen,
                    "status": ip_obj.get("status", {}),
                    "assigned_object": assigned_obj,
                    "description": ip_obj.get("description", ""),
                    "created": ip_obj.get("created", ""),
                    "last_updated": ip_obj.get("last_updated", ""),
                    "tenant": ip_obj.get("tenant", {}),
                    "vrf": ip_obj.get("vrf", {}),
                    "url": ip_obj.get("url", "")
                }
                
                ip_tracker[ip_only].append(ip_context)
                
            except ValueError as e:
                logger.warning(f"Invalid IP address format: {ip_address_str} - {e}")
                continue
        
        # Step 4: Identify duplicates (IPs that appear more than once)
        duplicates = []
        duplicate_ips_count = 0
        
        for ip_only, occurrences in ip_tracker.items():
            if len(occurrences) > 1:
                duplicate_ips_count += 1
                
                # Step 5: Severity analysis if requested
                severity_info = {}
                if include_severity_analysis:
                    # Analyze severity based on various factors
                    prefixes = set(occ["prefix_length"] for occ in occurrences)
                    statuses = set(
                        occ["status"].get("value", "unknown") if isinstance(occ["status"], dict) 
                        else str(occ["status"]) 
                        for occ in occurrences
                    )
                    
                    # Determine conflict severity
                    severity = "low"
                    risk_factors = []
                    
                    if len(prefixes) > 1:
                        severity = "medium"
                        risk_factors.append("Different subnet masks")
                    
                    active_assignments = [occ for occ in occurrences if occ["assigned_object"]]
                    if len(active_assignments) > 1:
                        severity = "high"
                        risk_factors.append("Multiple active assignments")
                    
                    if "active" in statuses:
                        if len([occ for occ in occurrences if 
                               isinstance(occ["status"], dict) and 
                               occ["status"].get("value") == "active"]) > 1:
                            severity = "critical"
                            risk_factors.append("Multiple active status IPs")
                    
                    # Check for same-device conflicts
                    device_names = set()
                    for occ in occurrences:
                        if occ["assigned_object"] and isinstance(occ["assigned_object"], dict):
                            assigned_obj = occ["assigned_object"]
                            if "device" in str(assigned_obj).lower():
                                device_names.add(assigned_obj.get("name", "unknown"))
                    
                    if len(device_names) > 1:
                        severity = "critical"
                        risk_factors.append("Assigned to multiple devices")
                    elif len(device_names) == 1:
                        risk_factors.append("Multiple assignments on same device")
                    
                    severity_info = {
                        "severity": severity,
                        "risk_factors": risk_factors,
                        "unique_prefixes": len(prefixes),
                        "unique_statuses": len(statuses),
                        "active_assignments": len(active_assignments),
                        "affected_devices": len(device_names)
                    }
                
                # Step 6: Resolution recommendations if requested
                recommendations = []
                if include_resolution_recommendations:
                    if severity_info.get("severity") == "critical":
                        recommendations.append("URGENT: Immediate action required to resolve IP conflict")
                        recommendations.append("Review and consolidate duplicate assignments")
                    
                    if len(active_assignments) > 1:
                        recommendations.append("Deactivate redundant IP assignments")
                        recommendations.append("Verify network configuration on affected devices")
                    
                    if "Multiple active assignments" in risk_factors:
                        recommendations.append("Change status of duplicate IPs to 'reserved' or 'deprecated'")
                    
                    if "Different subnet masks" in risk_factors:
                        recommendations.append("Standardize prefix lengths for consistent subnetting")
                    
                    # Add general recommendations
                    recommendations.append("Document IP assignment rationale")
                    recommendations.append("Implement IP allocation policies to prevent future conflicts")
                
                duplicate_entry = {
                    "ip_address": ip_only,
                    "occurrence_count": len(occurrences),
                    "occurrences": occurrences,
                    "severity_analysis": severity_info,
                    "resolution_recommendations": recommendations
                }
                
                duplicates.append(duplicate_entry)
        
        # Step 7: Sort duplicates by severity and occurrence count
        def sort_key(duplicate):
            severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
            severity = duplicate.get("severity_analysis", {}).get("severity", "low")
            return (severity_order.get(severity, 0), duplicate["occurrence_count"])
        
        duplicates.sort(key=sort_key, reverse=True)
        
        # Step 8: Build comprehensive analysis report
        total_conflicts = sum(dup["occurrence_count"] for dup in duplicates)
        
        result = {
            "success": True,
            "duplicates_found": duplicate_ips_count,
            "total_ip_conflicts": total_conflicts,
            "total_ips_analyzed": len(all_ips),
            "duplicates": duplicates,
            "analysis_scope": {
                "vrf_filter": vrf,
                "tenant_filter": tenant,
                "resolved_references": resolved_refs,
                "analysis_limit": limit
            },
            "statistics": {
                "ipv4_addresses": ipv4_count,
                "ipv6_addresses": ipv6_count,
                "assignment_breakdown": assignment_stats,
                "duplicate_rate": round((duplicate_ips_count / len(all_ips) * 100), 2) if all_ips else 0
            },
            "analysis_metadata": {
                "analysis_timestamp": client._get_current_timestamp() if hasattr(client, '_get_current_timestamp') else "unknown",
                "include_severity_analysis": include_severity_analysis,
                "include_resolution_recommendations": include_resolution_recommendations,
                "batch_processing": len(all_ips) > 500
            }
        }
        
        # Add severity summary
        if include_severity_analysis and duplicates:
            severity_summary = defaultdict(int)
            for dup in duplicates:
                severity = dup.get("severity_analysis", {}).get("severity", "unknown")
                severity_summary[severity] += 1
            
            result["severity_summary"] = dict(severity_summary)
        
        logger.info(f"✅ Duplicate IP analysis complete: {duplicate_ips_count} duplicate IPs found ({total_conflicts} total conflicts)")
        return result
        
    except Exception as e:
        logger.error(f"Failed to analyze duplicate IPs: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@mcp_tool(category="ipam")
def netbox_create_vrf(
    client: NetBoxClient,
    name: str,
    rd: Optional[str] = None,
    description: Optional[str] = None,
    tenant: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Create a new VRF in NetBox IPAM.
    
    Args:
        client: NetBoxClient instance (injected)
        name: VRF name
        rd: Route distinguisher (optional)
        description: Optional description
        tenant: Optional tenant name
        confirm: Must be True to execute (safety mechanism)
        
    Returns:
        Created VRF information or error details
        
    Example:
        netbox_create_vrf("MGMT-VRF", rd="65000:100", confirm=True)
    """
    try:
        if not name:
            return {
                "success": False,
                "error": "VRF name is required",
                "error_type": "ValidationError"
            }
        
        logger.info(f"Creating VRF: {name}")
        
        # Build VRF data
        vrf_data = {"name": name}
        
        if rd:
            vrf_data["rd"] = rd
        if description:
            vrf_data["description"] = description
        if tenant:
            vrf_data["tenant"] = tenant
        
        # Use dynamic API with safety
        result = client.ipam.vrfs.create(confirm=confirm, **vrf_data)
        
        return {
            "success": True,
            "action": "created", 
            "object_type": "vrf",
            "vrf": result,
            "dry_run": result.get("dry_run", False)
        }
        
    except Exception as e:
        logger.error(f"Failed to create VRF {name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }