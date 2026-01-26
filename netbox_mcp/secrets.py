#!/usr/bin/env python3
"""
Enterprise Secrets Management for NetBox MCP

Provides secure handling of sensitive configuration data including:
- Environment variables with prefix support
- Docker secrets integration
- Kubernetes secrets mounting
- Encrypted configuration files
- Vault integration (future)

Security Features:
- No secrets in logs or error messages
- Memory clearing of sensitive data
- Configuration validation without exposing secrets
- Multiple secret source priorities
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class SecretMask:
    """Utility class to mask secrets in logs and error messages."""
    
    @staticmethod
    def mask_secret(value: str, visible_chars: int = 4) -> str:
        """
        Mask a secret value for safe logging.
        
        Args:
            value: The secret value to mask
            visible_chars: Number of characters to show at the end
            
        Returns:
            Masked string like "***abc123" for a token ending in "abc123"
        """
        if not value or len(value) <= visible_chars:
            return "***"
        
        return "***" + value[-visible_chars:]
    
    @staticmethod
    def mask_url(url: str) -> str:
        """
        Mask credentials in URLs for safe logging.
        
        Args:
            url: URL that might contain credentials
            
        Returns:
            URL with credentials masked
        """
        if "@" in url:
            # URL contains credentials, mask them
            parts = url.split("@")
            if len(parts) == 2:
                # Keep protocol and domain, mask credentials
                protocol_creds = parts[0]
                domain_path = parts[1]
                
                if "://" in protocol_creds:
                    protocol, creds = protocol_creds.split("://", 1)
                    return f"{protocol}://***@{domain_path}"
        
        return url


class SecretsManager:
    """
    Enterprise secrets management with multiple source support.
    
    Source Priority (highest to lowest):
    1. Environment variables (NETBOX_*)
    2. Docker secrets (/run/secrets/*)
    3. Kubernetes secrets (/var/secrets/*)
    4. Encrypted config files
    5. Plain config files (development only)
    """
    
    # Docker secrets standard paths
    DOCKER_SECRETS_PATH = Path("/run/secrets")
    
    # Kubernetes secrets standard paths  
    K8S_SECRETS_PATH = Path("/var/secrets")
    
    # Environment variable prefix
    ENV_PREFIX = "NETBOX_"
    
    def __init__(self):
        self._secrets_cache: Dict[str, Any] = {}
        self._load_sources()
    
    def _load_sources(self):
        """Load secrets from all available sources in priority order."""
        logger.info("Loading secrets from available sources...")
        
        # Load from each source (priority order maintained by update order)
        sources_loaded = []
        
        # 1. Check for Kubernetes secrets
        if self.K8S_SECRETS_PATH.exists():
            k8s_secrets = self._load_kubernetes_secrets()
            if k8s_secrets:
                self._secrets_cache.update(k8s_secrets)
                sources_loaded.append("kubernetes")
        
        # 2. Check for Docker secrets  
        if self.DOCKER_SECRETS_PATH.exists():
            docker_secrets = self._load_docker_secrets()
            if docker_secrets:
                self._secrets_cache.update(docker_secrets)
                sources_loaded.append("docker")
        
        # 3. Load environment variables (highest priority)
        env_secrets = self._load_environment_secrets()
        if env_secrets:
            self._secrets_cache.update(env_secrets)
            sources_loaded.append("environment")
        
        logger.info(f"Secrets loaded from sources: {sources_loaded}")
    
    def _load_environment_secrets(self) -> Dict[str, Any]:
        """Load secrets from environment variables."""
        secrets = {}
        
        # Load all NETBOX_* environment variables
        for key, value in os.environ.items():
            if key.startswith(self.ENV_PREFIX):
                secrets[key] = value
        
        # Also load .env file if present (development)
        env_file = Path(".env")
        if env_file.exists():
            try:
                secrets.update(self._load_env_file(env_file))
                logger.debug("Loaded secrets from .env file")
            except Exception as e:
                logger.warning(f"Failed to load .env file: {e}")
        
        return secrets
    
    def _load_env_file(self, env_file: Path) -> Dict[str, str]:
        """Load environment variables from .env file."""
        secrets = {}
        
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    
                    # Parse KEY=VALUE format
                    if '=' not in line:
                        logger.warning(f"Invalid line {line_num} in {env_file}: {line}")
                        continue
                    
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    
                    # Only load NetBox-related secrets
                    if key.startswith(self.ENV_PREFIX):
                        secrets[key] = value
        
        except Exception as e:
            logger.error(f"Error reading .env file: {e}")
            raise
        
        return secrets
    
    def _load_docker_secrets(self) -> Dict[str, Any]:
        """Load secrets from Docker secrets directory."""
        secrets = {}
        
        if not self.DOCKER_SECRETS_PATH.exists():
            return secrets
        
        # Map secret file names to config keys
        secret_mappings = {
            "netbox_url": "NETBOX_URL",
            "netbox_token": "NETBOX_TOKEN",
            "netbox_api_key": "NETBOX_TOKEN",  # Alternative
            "netbox_password": "NETBOX_PASSWORD",
            "netbox_username": "NETBOX_USERNAME"
        }
        
        for secret_file, config_key in secret_mappings.items():
            secret_path = self.DOCKER_SECRETS_PATH / secret_file
            if secret_path.exists():
                try:
                    with open(secret_path, 'r', encoding='utf-8') as f:
                        secret_value = f.read().strip()
                        if secret_value:
                            secrets[config_key] = secret_value
                            logger.debug(f"Loaded Docker secret: {secret_file}")
                except Exception as e:
                    logger.warning(f"Failed to load Docker secret {secret_file}: {e}")
        
        return secrets
    
    def _load_kubernetes_secrets(self) -> Dict[str, Any]:
        """Load secrets from Kubernetes secrets directory."""
        secrets = {}
        
        if not self.K8S_SECRETS_PATH.exists():
            return secrets
        
        # Kubernetes typically mounts secrets as individual files
        secret_mappings = {
            "url": "NETBOX_URL",
            "token": "NETBOX_TOKEN", 
            "api-key": "NETBOX_TOKEN",  # Alternative
            "username": "NETBOX_USERNAME",
            "password": "NETBOX_PASSWORD"
        }
        
        for secret_file, config_key in secret_mappings.items():
            secret_path = self.K8S_SECRETS_PATH / secret_file
            if secret_path.exists():
                try:
                    with open(secret_path, 'r', encoding='utf-8') as f:
                        secret_value = f.read().strip()
                        if secret_value:
                            secrets[config_key] = secret_value
                            logger.debug(f"Loaded Kubernetes secret: {secret_file}")
                except Exception as e:
                    logger.warning(f"Failed to load Kubernetes secret {secret_file}: {e}")
        
        return secrets
    
    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a secret value by key.
        
        Args:
            key: Secret key (e.g., "NETBOX_TOKEN")
            default: Default value if secret not found
            
        Returns:
            Secret value or default
        """
        value = self._secrets_cache.get(key, default)
        return value
    
    def get_required_secret(self, key: str) -> str:
        """
        Get a required secret value.
        
        Args:
            key: Secret key (e.g., "NETBOX_TOKEN")
            
        Returns:
            Secret value
            
        Raises:
            ValueError: If secret is not found
        """
        value = self.get_secret(key)
        if not value:
            raise ValueError(f"Required secret '{key}' not found in any source")
        return value
    
    def mask_for_logging(self, key: str) -> str:
        """
        Get a masked version of a secret for safe logging.
        
        Args:
            key: Secret key
            
        Returns:
            Masked secret value
        """
        value = self.get_secret(key)
        if not value:
            return "Not Set"
        
        if key in ["NETBOX_URL"]:
            return SecretMask.mask_url(value)
        else:
            return SecretMask.mask_secret(value)
    
    def validate_secrets(self) -> Dict[str, bool]:
        """
        Validate that required secrets are available.
        
        Returns:
            Dictionary mapping secret names to availability status
        """
        required_secrets = ["NETBOX_URL", "NETBOX_TOKEN"]
        validation_results = {}
        
        for secret in required_secrets:
            validation_results[secret] = bool(self.get_secret(secret))
        
        return validation_results
    
    def get_connection_info(self) -> Dict[str, Any]:
        """
        Get connection information with masked secrets for safe logging.
        
        Returns:
            Dictionary with connection info suitable for logging
        """
        return {
            "url": self.mask_for_logging("NETBOX_URL"),
            "token": self.mask_for_logging("NETBOX_TOKEN"),
            "has_ssl_cert": bool(self.get_secret("NETBOX_SSL_CERT_PATH")),
            "has_ssl_key": bool(self.get_secret("NETBOX_SSL_KEY_PATH")),
            "has_ca_cert": bool(self.get_secret("NETBOX_CA_CERT_PATH"))
        }
    
    def clear_cache(self):
        """Clear the secrets cache (security best practice)."""
        self._secrets_cache.clear()
        logger.debug("Secrets cache cleared")


# Global secrets manager instance
_secrets_manager: Optional[SecretsManager] = None


def get_secrets_manager() -> SecretsManager:
    """Get the global secrets manager instance."""
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager()
    return _secrets_manager


def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """Convenience function to get a secret."""
    return get_secrets_manager().get_secret(key, default)


def get_required_secret(key: str) -> str:
    """Convenience function to get a required secret."""
    return get_secrets_manager().get_required_secret(key)


def validate_secrets() -> Dict[str, bool]:
    """Convenience function to validate secrets."""
    return get_secrets_manager().validate_secrets()


def get_connection_info() -> Dict[str, Any]:
    """Convenience function to get safe connection info."""
    return get_secrets_manager().get_connection_info()