"""
System Management Tools

This module contains enterprise-grade tools for system monitoring, health checks,
and NetBox MCP server management functionality.

Includes profile management meta-tools that are always available regardless
of the active profile.
"""

# Import all system tools to make them discoverable by the registry
from . import health
from . import profiles  # Profile management meta-tools (always available)
