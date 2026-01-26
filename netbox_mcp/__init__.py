"""
NetBox Read/Write MCP Server

A Model Context Protocol server that provides safe, intelligent read/write access
to NetBox instances. Designed with safety-first principles and idempotent operations.

Features:
- Read-only MCP tools for NetBox data exploration
- Write operations with mandatory confirmation and dry-run mode
- Idempotent ensure operations for robust automation
- Integration-ready as an agnostic NetBox specialist for automation platforms
"""

from ._version import get_cached_version, get_version_tuple

__version__ = get_cached_version()
__author__ = "Deployment Team"
__email__ = "info@deployment-team.nl"

# Version information
VERSION = get_version_tuple()
VERSION_STRING = __version__

# Package exports
from .exceptions import NetBoxError, NetBoxConnectionError, NetBoxAuthError
from .config import NetBoxConfig, SafetyConfig, CacheConfig, load_config
from .client import NetBoxClient, ConnectionStatus

__all__ = [
    "__version__",
    "VERSION", 
    "VERSION_STRING",
    "NetBoxError",
    "NetBoxConnectionError", 
    "NetBoxAuthError",
    "NetBoxConfig",
    "SafetyConfig", 
    "CacheConfig",
    "load_config",
    "NetBoxClient",
    "ConnectionStatus",
]