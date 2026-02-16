#!/usr/bin/env python3
"""
Dependency Injection Module for NetBox MCP

Provides centralized dependency management for shared resources like
NetBoxClient and configuration. This module breaks circular imports by
serving as the single source of truth for dependency injection.

Following Gemini's architectural guidance for clean separation of concerns.
"""

from functools import lru_cache
import logging
from .config import NetBoxConfig, load_config
from .client import NetBoxClient
from .secrets import get_secrets_manager

logger = logging.getLogger(__name__)

# Global client instance for singleton pattern
_netbox_client_instance = None
_client_lock = None

def _get_client_lock():
    """Get or create threading lock for client initialization."""
    global _client_lock
    if _client_lock is None:
        import threading
        _client_lock = threading.Lock()
    return _client_lock


@lru_cache()
def get_netbox_config() -> NetBoxConfig:
    """
    Creates and caches the NetBoxConfig to prevent repeated reading
    of environment variables.
    
    Returns:
        NetBoxConfig: Cached configuration instance
    """
    try:
        config = load_config()
        logger.info("NetBoxConfig loaded and cached successfully")
        return config
    except Exception as e:
        logger.error(f"Failed to load NetBox configuration: {e}")
        raise


def get_netbox_client() -> NetBoxClient:
    """
    Dependency provider for NetBoxClient.
    
    This function instantiates the client and ensures the entire application
    uses the same, single client instance (Singleton pattern).
    
    The function is designed to be used with FastAPI's Depends() system,
    but can also be called directly for non-FastAPI usage.
    
    Returns:
        NetBoxClient: Singleton client instance
        
    Raises:
        Exception: If client initialization fails
    """
    global _netbox_client_instance
    
    # Thread-safe singleton initialization
    lock = _get_client_lock()
    with lock:
        if _netbox_client_instance is None:
            try:
                config = get_netbox_config()
                _netbox_client_instance = NetBoxClient(config)
                logger.info(f"NetBoxClient singleton initialized (ID: {id(_netbox_client_instance)})")
            except Exception as e:
                logger.error(f"Failed to initialize NetBoxClient: {e}")
                raise
        else:
            logger.debug(f"Returning existing NetBoxClient singleton (ID: {id(_netbox_client_instance)})")
    
    return _netbox_client_instance


def reset_client_instance():
    """
    Reset the client instance - primarily for testing purposes.
    
    WARNING: This should only be used in testing environments.
    """
    global _netbox_client_instance
    lock = _get_client_lock()
    with lock:
        if _netbox_client_instance is not None:
            logger.warning("NetBoxClient singleton reset - this should only happen in tests")
            _netbox_client_instance = None


def get_client_status() -> dict:
    """
    Get status information about the current client instance.
    
    Returns:
        dict: Status information including instance ID and initialization state
    """
    global _netbox_client_instance
    
    # Get secrets manager status
    secrets_manager = get_secrets_manager()
    connection_info = secrets_manager.get_connection_info()
    
    return {
        "initialized": _netbox_client_instance is not None,
        "instance_id": id(_netbox_client_instance) if _netbox_client_instance else None,
        "config_cached": get_netbox_config.cache_info().hits > 0,
        "secrets_status": {
            "url_configured": connection_info['url'] != "Not Set",
            "token_configured": connection_info['token'] != "Not Set",
            "ssl_cert_available": connection_info['has_ssl_cert'],
            "ssl_key_available": connection_info['has_ssl_key'],
            "ca_cert_available": connection_info['has_ca_cert']
        }
    }


# For backward compatibility with existing code
# These functions maintain the NetBoxClientManager interface
class NetBoxClientManager:
    """
    Backward compatibility wrapper around the new dependency injection system.
    
    This maintains the existing NetBoxClientManager interface while delegating
    to the new dependency injection functions.
    """
    
    @classmethod
    def initialize(cls, config: NetBoxConfig = None) -> None:
        """
        Initialize the shared client instance.
        
        Args:
            config: Optional config override (for testing)
        """
        if config:
            # For testing - temporarily override the cached config
            get_netbox_config.cache_clear()
            # This is a bit of a hack, but maintains backward compatibility
            import os
            original_url = os.environ.get('NETBOX_URL')
            original_token = os.environ.get('NETBOX_TOKEN')
            
            os.environ['NETBOX_URL'] = config.url
            os.environ['NETBOX_TOKEN'] = config.token
            
            try:
                # Force re-initialization with new config
                reset_client_instance()
                get_netbox_client()
            finally:
                # Restore original environment
                if original_url:
                    os.environ['NETBOX_URL'] = original_url
                if original_token:
                    os.environ['NETBOX_TOKEN'] = original_token
        else:
            # Normal initialization
            get_netbox_client()
    
    @classmethod
    def get_client(cls) -> NetBoxClient:
        """Get the shared client instance."""
        return get_netbox_client()
    
    @classmethod
    def reset(cls) -> None:
        """Reset client (for testing purposes only)."""
        reset_client_instance()
        get_netbox_config.cache_clear()


# Export the main functions for dependency injection
__all__ = [
    'get_netbox_config',
    'get_netbox_client', 
    'reset_client_instance',
    'get_client_status',
    'NetBoxClientManager'  # For backward compatibility
]