#!/usr/bin/env python3
"""
Entry point for NetBox MCP Server

This script serves as the main entry point for the NetBox MCP server,
handling proper module imports and initialization.
"""

import sys
import os

# Add the package directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from netbox_mcp.server import main

if __name__ == "__main__":
    main()