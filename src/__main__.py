#!/usr/bin/env python3
"""
NetBox MCP Server Entry Point

Allows running the server with: python -m netbox_mcp
"""

from .server import main

if __name__ == "__main__":
    main()