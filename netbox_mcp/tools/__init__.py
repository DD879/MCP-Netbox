#!/usr/bin/env python3
"""
NetBox MCP Tools Package

This package contains all MCP tool implementations organized by category.
Tools are automatically discovered and registered using the @mcp_tool decorator.

The package structure follows NetBox's application organization:
- system_tools.py - System health and monitoring tools  
- ipam_tools.py - IP Address Management tools
- dcim_tools.py - Data Center Infrastructure Management tools
- bulk_tools.py - Bulk operations and orchestration tools

Tools are loaded automatically when this package is imported.
"""

import importlib
import logging
from typing import List

logger = logging.getLogger(__name__)

def load_all_tools() -> List[str]:
    """
    Load all tools from the hierarchical domain structure.
    
    This function directly imports all domain packages, which in turn import
    their tool modules via their __init__.py files. This approach is more
    reliable than automatic discovery and ensures all tools are loaded.
    
    Returns:
        List[str]: Names of successfully loaded domain packages
    """
    loaded_domains = []
    
    # Define the domain packages to load
    domain_packages = [
        'system',
        'dcim', 
        'ipam',
        'tenancy',
        'extras',
        'virtualization',
    ]
    
    for domain in domain_packages:
        try:
            # Import the domain package - this triggers all __init__.py imports
            module_name = f"{__name__}.{domain}"
            importlib.import_module(module_name)
            loaded_domains.append(domain)
            logger.info(f"Successfully loaded domain package: {domain}")
        except Exception as e:
            logger.error(f"Failed to load domain package {domain}: {e}")
            # Continue loading other domains even if one fails
    
    logger.info(f"Tool loading complete: {len(loaded_domains)} domain packages loaded")
    return loaded_domains

# Automatically load all tools when this package is imported
_loaded_tools = load_all_tools()

# Export the load function for explicit use if needed
__all__ = ['load_all_tools']