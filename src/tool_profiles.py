#!/usr/bin/env python3
"""
Tool Profiles Management System

Provides dynamic tool filtering based on profiles to optimize
context usage for smaller LLMs like Ollama models.

The system allows:
- Predefined profiles (essential, ipam, dcim, readonly, full)
- Dynamic profile activation during conversation
- Meta-tools for profile management (always available)
"""

import logging
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ProfileType(Enum):
    """Available tool profile types."""
    MINIMAL = "minimal"      # Only meta-tools for profile management
    ESSENTIAL = "essential"  # Core operations (~20 tools)
    IPAM = "ipam"           # IP Address Management (~30 tools)
    DCIM = "dcim"           # Data Center Infrastructure (~40 tools)
    READONLY = "readonly"    # All read operations (~60 tools)
    WRITE = "write"         # Write operations only
    FULL = "full"           # All tools (142+)


@dataclass
class ToolProfile:
    """Definition of a tool profile."""
    name: str
    description: str
    tool_patterns: List[str]  # Patterns to match tool names
    categories: List[str]     # Categories to include
    exclude_patterns: List[str] = field(default_factory=list)
    max_tools: Optional[int] = None  # Optional limit


# Profile definitions
TOOL_PROFILES: Dict[str, ToolProfile] = {
    "minimal": ToolProfile(
        name="minimal",
        description="Only profile management tools. Use this to start light and activate specific profiles as needed.",
        tool_patterns=["netbox_profile_*", "netbox_tool_*"],
        categories=["meta"],
        max_tools=10
    ),
    
    "essential": ToolProfile(
        name="essential",
        description="Essential NetBox operations: health check, list sites/devices/IPs, basic searches. Good starting point for most tasks.",
        tool_patterns=[
            "netbox_health_check",
            "netbox_list_sites",
            "netbox_list_devices", 
            "netbox_list_ip_addresses",
            "netbox_list_prefixes",
            "netbox_list_vlans",
            "netbox_get_device",
            "netbox_get_site",
            "netbox_get_ip_address",
            "netbox_search_*",
        ],
        categories=["system", "meta"],
        max_tools=25
    ),
    
    "ipam": ToolProfile(
        name="ipam",
        description="IP Address Management: manage IPs, prefixes, VLANs, VRFs, aggregates. Use for network addressing tasks.",
        tool_patterns=[
            "netbox_*_ip_address*",
            "netbox_*_prefix*",
            "netbox_*_vlan*",
            "netbox_*_vrf*",
            "netbox_*_aggregate*",
            "netbox_*_rir*",
            "netbox_health_check",
            "netbox_list_sites",
        ],
        categories=["ipam", "system", "meta"],
        max_tools=35
    ),
    
    "dcim": ToolProfile(
        name="dcim",
        description="Data Center Infrastructure: devices, racks, cables, interfaces, power. Use for hardware management.",
        tool_patterns=[
            "netbox_*_device*",
            "netbox_*_rack*",
            "netbox_*_cable*",
            "netbox_*_interface*",
            "netbox_*_site*",
            "netbox_*_manufacturer*",
            "netbox_*_device_type*",
            "netbox_*_device_role*",
            "netbox_*_power*",
            "netbox_*_module*",
            "netbox_health_check",
        ],
        categories=["dcim", "system", "meta"],
        max_tools=50
    ),
    
    "readonly": ToolProfile(
        name="readonly",
        description="All read-only operations: list, get, search. Safe for exploration without modifications.",
        tool_patterns=[
            "netbox_list_*",
            "netbox_get_*",
            "netbox_search_*",
            "netbox_health_check",
            "netbox_find_*",
        ],
        categories=["system", "meta"],
        exclude_patterns=[
            "netbox_create_*",
            "netbox_update_*",
            "netbox_delete_*",
            "netbox_bulk_*",
        ],
        max_tools=70
    ),
    
    "write": ToolProfile(
        name="write",
        description="Write operations: create, update, delete. Use when you need to modify NetBox data.",
        tool_patterns=[
            "netbox_create_*",
            "netbox_update_*",
            "netbox_delete_*",
            "netbox_bulk_*",
            "netbox_health_check",
        ],
        categories=["meta"],
        max_tools=60
    ),
    
    "full": ToolProfile(
        name="full",
        description="All available tools (142+). Only use with large models (14B+ parameters) or when you need complete functionality.",
        tool_patterns=["*"],
        categories=["*"],
        max_tools=None  # No limit
    ),
}


class ToolProfileManager:
    """
    Manages active tool profiles and filtering.
    
    This is a singleton that tracks which profile is active
    and provides methods for filtering tools accordingly.
    """
    
    _instance: Optional['ToolProfileManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._active_profile: str = "minimal"  # Start with minimal
        self._active_tools: Set[str] = set()
        self._all_tools: Dict[str, Dict[str, Any]] = {}
        self._meta_tools: Set[str] = set()  # Always-available tools
        self._initialized = True
        
        logger.info("ToolProfileManager initialized with 'minimal' profile")
    
    def set_tool_registry(self, registry: Dict[str, Dict[str, Any]]):
        """
        Set the complete tool registry for filtering.
        
        Args:
            registry: The TOOL_REGISTRY from registry.py
        """
        self._all_tools = registry
        
        # Identify meta-tools (profile management) - always available
        self._meta_tools = {
            name for name in registry.keys()
            if name.startswith("netbox_profile_") or 
               name.startswith("netbox_tool_") or
               name == "netbox_health_check"
        }
        
        # Apply initial profile
        self._apply_profile(self._active_profile)
        
        logger.info(f"Tool registry set: {len(registry)} total tools, {len(self._meta_tools)} meta-tools")
    
    def _match_pattern(self, tool_name: str, pattern: str) -> bool:
        """Check if tool name matches a glob-like pattern."""
        import fnmatch
        return fnmatch.fnmatch(tool_name, pattern)
    
    def _apply_profile(self, profile_name: str) -> Set[str]:
        """
        Apply a profile and return the set of active tools.
        
        Args:
            profile_name: Name of the profile to apply
            
        Returns:
            Set of tool names that are now active
        """
        if profile_name not in TOOL_PROFILES:
            logger.warning(f"Unknown profile '{profile_name}', defaulting to 'minimal'")
            profile_name = "minimal"
        
        profile = TOOL_PROFILES[profile_name]
        matched_tools: Set[str] = set()
        
        for tool_name, tool_meta in self._all_tools.items():
            # Always include meta-tools
            if tool_name in self._meta_tools:
                matched_tools.add(tool_name)
                continue
            
            # Check category match
            tool_category = tool_meta.get("category", "general")
            category_match = (
                "*" in profile.categories or 
                tool_category in profile.categories
            )
            
            # Check pattern match
            pattern_match = any(
                self._match_pattern(tool_name, pattern)
                for pattern in profile.tool_patterns
            )
            
            # Check exclusion patterns
            excluded = any(
                self._match_pattern(tool_name, pattern)
                for pattern in profile.exclude_patterns
            )
            
            if (category_match or pattern_match) and not excluded:
                matched_tools.add(tool_name)
        
        # Apply max_tools limit if specified
        if profile.max_tools and len(matched_tools) > profile.max_tools:
            # Keep meta-tools and trim the rest
            non_meta = matched_tools - self._meta_tools
            trimmed = set(list(non_meta)[:profile.max_tools - len(self._meta_tools)])
            matched_tools = self._meta_tools | trimmed
        
        self._active_tools = matched_tools
        self._active_profile = profile_name
        
        logger.info(f"Profile '{profile_name}' activated: {len(matched_tools)} tools available")
        return matched_tools
    
    def activate_profile(self, profile_name: str) -> Dict[str, Any]:
        """
        Activate a tool profile.
        
        Args:
            profile_name: Name of the profile to activate
            
        Returns:
            Result dictionary with activation status
        """
        if profile_name not in TOOL_PROFILES:
            available = list(TOOL_PROFILES.keys())
            return {
                "success": False,
                "error": f"Unknown profile '{profile_name}'",
                "available_profiles": available
            }
        
        active_tools = self._apply_profile(profile_name)
        profile = TOOL_PROFILES[profile_name]
        
        return {
            "success": True,
            "profile": profile_name,
            "description": profile.description,
            "tools_activated": len(active_tools),
            "tool_names": sorted(list(active_tools))[:20],  # First 20 for brevity
            "has_more": len(active_tools) > 20
        }
    
    def get_active_profile(self) -> str:
        """Get the name of the currently active profile."""
        return self._active_profile
    
    def get_active_tools(self) -> Set[str]:
        """Get the set of currently active tool names."""
        return self._active_tools
    
    def is_tool_active(self, tool_name: str) -> bool:
        """Check if a specific tool is currently active."""
        return tool_name in self._active_tools or tool_name in self._meta_tools
    
    def list_profiles(self) -> List[Dict[str, Any]]:
        """
        List all available profiles with descriptions.
        
        Returns:
            List of profile information dictionaries
        """
        profiles = []
        for name, profile in TOOL_PROFILES.items():
            profiles.append({
                "name": name,
                "description": profile.description,
                "is_active": name == self._active_profile,
                "estimated_tools": profile.max_tools or "unlimited"
            })
        return profiles
    
    def search_tools(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for tools by name or description.
        
        Args:
            query: Search query string
            
        Returns:
            List of matching tools with their profiles
        """
        query_lower = query.lower()
        results = []
        
        for tool_name, tool_meta in self._all_tools.items():
            name_match = query_lower in tool_name.lower()
            desc_match = query_lower in tool_meta.get("description", "").lower()
            
            if name_match or desc_match:
                # Find which profiles include this tool
                containing_profiles = []
                for profile_name, profile in TOOL_PROFILES.items():
                    for pattern in profile.tool_patterns:
                        if self._match_pattern(tool_name, pattern):
                            containing_profiles.append(profile_name)
                            break
                
                results.append({
                    "name": tool_name,
                    "description": tool_meta.get("description", "")[:100],
                    "category": tool_meta.get("category", "general"),
                    "is_active": tool_name in self._active_tools,
                    "available_in_profiles": containing_profiles[:3]  # First 3
                })
        
        return results[:15]  # Limit results
    
    def get_filtered_registry(self) -> Dict[str, Dict[str, Any]]:
        """
        Get a filtered registry containing only active tools.
        
        Returns:
            Dictionary with only the active tools
        """
        return {
            name: meta 
            for name, meta in self._all_tools.items()
            if name in self._active_tools or name in self._meta_tools
        }


# Singleton instance
_profile_manager: Optional[ToolProfileManager] = None


def get_profile_manager() -> ToolProfileManager:
    """Get the singleton ToolProfileManager instance."""
    global _profile_manager
    if _profile_manager is None:
        _profile_manager = ToolProfileManager()
    return _profile_manager
