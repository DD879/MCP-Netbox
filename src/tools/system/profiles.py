#!/usr/bin/env python3
"""
Profile Management Meta-Tools

These tools are ALWAYS available regardless of the active profile.
They allow the AI model to discover and activate tool profiles dynamically.
"""

from typing import Dict, List, Any, Optional
import logging
from ..registry import mcp_tool
from ..client import NetBoxClient
from ..tool_profiles import get_profile_manager, TOOL_PROFILES

logger = logging.getLogger(__name__)


@mcp_tool(name="netbox_profile_list", category="meta")
def netbox_profile_list(client: NetBoxClient) -> Dict[str, Any]:
    """
    List all available tool profiles.
    
    Use this tool to discover which profiles are available and choose
    the right one for your task. Start with 'essential' for basic operations
    or activate a specific profile like 'ipam' or 'dcim' for specialized tasks.
    
    Args:
        client: NetBoxClient instance (injected automatically)
        
    Returns:
        List of available profiles with descriptions
        
    Example:
        netbox_profile_list()
        # Returns: [{name: "essential", description: "...", is_active: false}, ...]
    """
    manager = get_profile_manager()
    profiles = manager.list_profiles()
    
    return {
        "success": True,
        "current_profile": manager.get_active_profile(),
        "active_tools_count": len(manager.get_active_tools()),
        "profiles": profiles,
        "hint": "Use netbox_profile_activate to switch profiles"
    }


@mcp_tool(name="netbox_profile_activate", category="meta")
def netbox_profile_activate(
    client: NetBoxClient,
    profile: str
) -> Dict[str, Any]:
    """
    Activate a tool profile to access its tools.
    
    This changes which tools are available for use. Choose a profile
    based on the task:
    - 'essential': Basic operations (list sites, devices, IPs)
    - 'ipam': IP address management (IPs, prefixes, VLANs, VRFs)
    - 'dcim': Data center infrastructure (devices, racks, cables)
    - 'readonly': All read operations (safe exploration)
    - 'write': Create/update/delete operations
    - 'full': All tools (use only with large models)
    
    Args:
        client: NetBoxClient instance (injected automatically)
        profile: Profile name to activate (essential, ipam, dcim, readonly, write, full)
        
    Returns:
        Activation result with list of newly available tools
        
    Example:
        netbox_profile_activate(profile="ipam")
        # Activates IPAM tools: netbox_list_ip_addresses, netbox_create_prefix, etc.
    """
    manager = get_profile_manager()
    result = manager.activate_profile(profile)
    
    if result["success"]:
        logger.info(f"Profile '{profile}' activated by AI model")
    
    return result


@mcp_tool(name="netbox_profile_current", category="meta")
def netbox_profile_current(client: NetBoxClient) -> Dict[str, Any]:
    """
    Get the currently active profile and its available tools.
    
    Use this to check which profile is active and what tools you can use.
    
    Args:
        client: NetBoxClient instance (injected automatically)
        
    Returns:
        Current profile information and available tools
        
    Example:
        netbox_profile_current()
        # Returns: {profile: "ipam", tools: ["netbox_list_ip_addresses", ...]}
    """
    manager = get_profile_manager()
    active_tools = sorted(list(manager.get_active_tools()))
    
    return {
        "success": True,
        "profile": manager.get_active_profile(),
        "profile_description": TOOL_PROFILES.get(
            manager.get_active_profile(), 
            TOOL_PROFILES["minimal"]
        ).description,
        "tools_count": len(active_tools),
        "tools": active_tools[:30],  # First 30 for brevity
        "has_more": len(active_tools) > 30
    }


@mcp_tool(name="netbox_tool_search", category="meta")
def netbox_tool_search(
    client: NetBoxClient,
    query: str
) -> Dict[str, Any]:
    """
    Search for tools by name or description.
    
    Use this to find specific tools without activating the full profile.
    The search will tell you which profile contains the tool you need.
    
    Args:
        client: NetBoxClient instance (injected automatically)
        query: Search query (e.g., "ip address", "cable", "rack")
        
    Returns:
        Matching tools with their profiles
        
    Example:
        netbox_tool_search(query="vlan")
        # Returns tools related to VLANs and which profiles contain them
    """
    manager = get_profile_manager()
    results = manager.search_tools(query)
    
    return {
        "success": True,
        "query": query,
        "matches": len(results),
        "tools": results,
        "hint": "Activate a profile containing the tool you need with netbox_profile_activate"
    }


@mcp_tool(name="netbox_tool_help", category="meta")
def netbox_tool_help(client: NetBoxClient) -> Dict[str, Any]:
    """
    Get help on using the NetBox MCP tool system.
    
    This explains how to use profiles and find the right tools for your task.
    
    Args:
        client: NetBoxClient instance (injected automatically)
        
    Returns:
        Help information and usage guide
        
    Example:
        netbox_tool_help()
    """
    return {
        "success": True,
        "guide": """
# NetBox MCP Tool Profiles

This system uses profiles to manage which tools are available. This helps 
smaller AI models work efficiently without being overwhelmed by 142+ tools.

## Quick Start

1. **Check available profiles**: `netbox_profile_list()`
2. **Activate a profile**: `netbox_profile_activate(profile="ipam")`
3. **See active tools**: `netbox_profile_current()`
4. **Search for tools**: `netbox_tool_search(query="cable")`

## Available Profiles

- **minimal**: Only profile management (start here)
- **essential**: Basic operations (~20 tools)
- **ipam**: IP management - IPs, prefixes, VLANs (~30 tools)
- **dcim**: Infrastructure - devices, racks, cables (~40 tools)
- **readonly**: All read operations (~60 tools)
- **write**: Create/update/delete operations
- **full**: All tools (use with large models only)

## Common Workflows

**List IPs in NetBox:**
1. `netbox_profile_activate(profile="ipam")`
2. `netbox_list_ip_addresses()`

**Manage devices:**
1. `netbox_profile_activate(profile="dcim")`
2. `netbox_list_devices(site="my-site")`

**Explore safely:**
1. `netbox_profile_activate(profile="readonly")`
2. Use any list/get/search tool
        """,
        "current_profile": get_profile_manager().get_active_profile(),
        "tip": "Start with 'essential' profile for most tasks"
    }
