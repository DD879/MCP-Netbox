"""
Version management for NetBox MCP Server.

Reads version information from pyproject.toml to ensure consistency
across the application.
"""

import sys
from pathlib import Path
from typing import Tuple, Optional

def get_version() -> str:
    """
    Get version from pyproject.toml.
    
    Returns:
        Version string (e.g., "1.0.0")
        
    Raises:
        RuntimeError: If version cannot be determined
    """
    try:
        # Try importlib.metadata first (Python 3.8+)
        if sys.version_info >= (3, 8):
            try:
                from importlib.metadata import version, PackageNotFoundError
                return version("netbox-mcp")
            except (PackageNotFoundError, ImportError):
                pass
        
        # Fallback: read pyproject.toml directly
        project_root = Path(__file__).parent.parent
        pyproject_path = project_root / "pyproject.toml"
        
        if pyproject_path.exists():
            with open(pyproject_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("version"):
                        # Extract version from: version = "1.0.0"
                        version_line = line.strip()
                        if "=" in version_line:
                            version_part = version_line.split("=", 1)[1].strip()
                            # Remove quotes
                            version_str = version_part.strip('"\'')
                            return version_str
        
        # Final fallback - should not reach here in production
        raise RuntimeError("Could not determine version from pyproject.toml")
        
    except Exception as e:
        raise RuntimeError(f"Could not determine version: {e}")

def get_version_tuple() -> Tuple[int, ...]:
    """
    Get version as tuple of integers.
    
    Returns:
        Version tuple (e.g., (1, 0, 0))
    """
    version_str = get_version()
    try:
        return tuple(int(x) for x in version_str.split("."))
    except ValueError as e:
        raise RuntimeError(f"Invalid version string format: '{version_str}'") from e

# Cache version for performance
_cached_version: Optional[str] = None

def get_cached_version() -> str:
    """Get cached version string for performance."""
    global _cached_version
    if _cached_version is None:
        _cached_version = get_version()
    return _cached_version