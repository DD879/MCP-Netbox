#!/usr/bin/env python3
"""
Configuration management for NetBox MCP Server

Supports YAML and TOML configuration files with environment variable overrides.
Configuration hierarchy (highest priority first):
1. Environment variables (via secrets management)
2. Configuration file
3. Default values

Safety-focused configuration with write operation controls and enterprise secrets management.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from .secrets import get_secrets_manager, validate_secrets

try:
    import yaml
except ImportError:
    yaml = None

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # Fallback for older Python versions
    except ImportError:
        tomllib = None

logger = logging.getLogger(__name__)


@dataclass
class SafetyConfig:
    """Safety configuration for write operations."""
    
    # Global safety controls
    dry_run_mode: bool = False              # Global dry-run mode
    require_confirmation: bool = True       # Require confirm=True for write ops
    enable_write_operations: bool = True    # Master switch for all write ops
    
    # Operation timeouts and limits
    write_timeout: int = 60                 # Timeout for write operations
    max_batch_size: int = 100              # Maximum objects per batch operation
    
    # Audit and logging
    audit_all_operations: bool = True       # Log all operations (read/write)
    audit_write_details: bool = True        # Detailed logging for write operations
    
    # Rollback and recovery
    enable_transaction_mode: bool = True    # Enable transaction-like operations
    auto_rollback_on_error: bool = True     # Auto-rollback on partial failures


@dataclass
class CacheTTLConfig:
    """
    TTL configuration following Gemini's caching strategy.
    
    TTLs range from static (long TTL) to dynamic (short TTL) based on 
    how frequently the data changes in typical NetBox deployments.
    """
    
    # Priority 1: Static objects (high cache value, low risk)
    manufacturers: int = 86400              # 1 day - manufacturers rarely change
    device_types: int = 86400               # 1 day - device types rarely change  
    sites: int = 3600                       # 1 hour - sites change occasionally
    device_roles: int = 86400               # 1 day - device roles rarely change
    
    # Priority 2: Semi-static objects
    devices: int = 300                      # 5 minutes - devices change more frequently
    
    # Priority 3: Dynamic objects (conservative TTL)
    ip_addresses: int = 60                  # 1 minute - IP addresses very dynamic
    device_interfaces: int = 60             # 1 minute - interfaces change frequently
    vlans: int = 300                        # 5 minutes - VLANs moderately dynamic
    
    # System status (always fresh)
    status: int = 30                        # 30 seconds - status should be fresh
    health: int = 30                        # 30 seconds - health should be fresh
    
    # Default for unlisted operations (conservative)
    default: int = 300                      # 5 minutes default


@dataclass
class CacheConfig:
    """Configuration for response caching."""
    
    # Basic settings
    enabled: bool = True
    backend: str = "memory"                 # 'memory' or 'disk'
    
    # Size limits
    size_limit_mb: int = 200               # Cache size limit in megabytes
    max_items: int = 2000                  # Maximum number of cached items
    
    # File-based cache settings (disk backend only)
    path: Optional[str] = "/tmp/netbox_mcp_cache"
    
    # TTL configuration
    ttl: CacheTTLConfig = field(default_factory=CacheTTLConfig)
    
    # Advanced features
    warm_on_startup: bool = False          # Whether to warm cache on startup
    compression: bool = False              # Whether to compress cached data
    
    # Statistics
    enable_stats: bool = True              # Whether to track cache statistics


@dataclass  
class LoggingConfig:
    """Structured logging configuration for enterprise deployment."""
    
    # Basic logging settings
    level: str = "INFO"
    format: str = "json"                      # "json" for structured, "text" for human-readable
    
    # File logging settings
    enable_file_logging: bool = False
    log_file_path: Optional[str] = None
    max_file_size_mb: int = 10
    backup_count: int = 5
    
    # Service identification
    service_name: str = "netbox-mcp"
    service_version: str = "0.6.0"
    
    # Component-specific log levels
    component_levels: Dict[str, str] = field(default_factory=lambda: {
        "netbox_mcp.client": "INFO",
        "netbox_mcp.server": "INFO", 
        "netbox_mcp.tools": "INFO",
        "netbox_mcp.secrets": "WARNING",
        "urllib3": "WARNING",
        "requests": "WARNING",
        "pynetbox": "INFO"
    })
    
    # Performance and correlation
    enable_correlation_ids: bool = True
    enable_performance_logging: bool = True
    
    # Production detection
    auto_detect_production: bool = True        # Auto-switch to JSON in container environments


@dataclass
class NetBoxConfig:
    """Configuration settings for NetBox MCP Server"""
    
    # Required NetBox connection settings
    url: str = ""
    token: str = ""
    
    # Optional connection settings
    timeout: int = 30
    verify_ssl: bool = True
    
    # Server settings
    log_level: str = "INFO"                   # Legacy field, use logging.level instead
    health_check_port: int = 8080

    # MCP transport settings
    # - "stdio": default (Claude Desktop style, client spawns server)
    # - "streamable-http": recommended for running as a network service
    # - "http": alias for streamable-http (supported by some clients/tools)
    # - "sse": legacy HTTP transport (avoid for new deployments)
    mcp_transport: str = "stdio"
    mcp_host: str = "0.0.0.0"  # Use 0.0.0.0 to bind to all interfaces (required for Docker)
    mcp_port: int = 8000
    mcp_path: str = "/mcp"

    # Streamable HTTP behavior (passed to FastMCP)
    # Recommended for scalable deployments: stateless_http=True and json_response=True
    mcp_stateless_http: bool = False
    mcp_json_response: bool = False
    # Safety configuration (CRITICAL)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    
    # Performance settings
    default_page_size: int = 50            # Smaller default for NetBox
    max_results: int = 1000
    
    # Feature flags
    enable_health_server: bool = True
    enable_degraded_mode: bool = True
    enable_read_operations: bool = True
    
    # Advanced settings
    custom_headers: Dict[str, str] = field(default_factory=dict)
    
    # Cache configuration
    cache: CacheConfig = field(default_factory=CacheConfig)
    
    # Logging configuration
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        if not self.url:
            raise ValueError("NetBox URL must be specified (NETBOX_URL)")
        if not self.token:
            raise ValueError("NetBox API token must be specified (NETBOX_TOKEN)")
        
        # Normalize URL
        self.url = self.url.rstrip('/')
        
        # Validate URL format
        if not (self.url.startswith('http://') or self.url.startswith('https://')):
            raise ValueError("NetBox URL must start with http:// or https://")
        
        # Validate log level
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {self.log_level}. Must be one of {valid_levels}")
        
        # Validate numeric values
        if self.timeout <= 0:
            raise ValueError("Timeout must be positive")
        if self.health_check_port <= 0 or self.health_check_port > 65535:
            raise ValueError("Health check port must be between 1 and 65535")
        # Validate MCP transport settings
        valid_mcp_transports = {"stdio", "streamable-http", "http", "sse"}
        if self.mcp_transport not in valid_mcp_transports:
            raise ValueError(f"Invalid MCP transport: {self.mcp_transport}. Must be one of {sorted(valid_mcp_transports)}")

        if self.mcp_port <= 0 or self.mcp_port > 65535:
            raise ValueError("MCP port must be between 1 and 65535")

        if not self.mcp_host:
            raise ValueError("MCP host must not be empty")

        if not self.mcp_path.startswith("/"):
            raise ValueError("MCP path must start with '/' (e.g., /mcp)")
        if self.default_page_size <= 0:
            raise ValueError("Default page size must be positive")
        if self.max_results <= 0:
            raise ValueError("Max results must be positive")
        
        # Safety validations
        if self.safety.write_timeout <= 0:
            raise ValueError("Write timeout must be positive")
        if self.safety.max_batch_size <= 0:
            raise ValueError("Max batch size must be positive")
        
        # Log safety configuration warnings
        if self.safety.dry_run_mode:
            logger.warning("NetBox MCP running in DRY-RUN mode - no actual writes will be performed")
        
        if not self.safety.require_confirmation:
            logger.warning("Confirmation requirement DISABLED - write operations can execute without confirm=True")
        
        if not self.safety.enable_write_operations:
            logger.info("Write operations DISABLED - server will be read-only")
            
        # Log secure connection information
        secrets_manager = get_secrets_manager()
        connection_info = secrets_manager.get_connection_info()
        logger.info(f"NetBox connection configured: {connection_info['url']}")
        logger.debug(f"Connection security: SSL cert={connection_info['has_ssl_cert']}, "
                    f"SSL key={connection_info['has_ssl_key']}, CA cert={connection_info['has_ca_cert']}")
        
        # Validate that required secrets are available
        secret_validation = validate_secrets()
        missing_secrets = [key for key, available in secret_validation.items() if not available]
        if missing_secrets:
            logger.warning(f"Missing required secrets: {missing_secrets}")
        else:
            logger.info("All required secrets validated successfully")


class ConfigurationManager:
    """Manages configuration loading from multiple sources"""
    
    DEFAULT_CONFIG_PATHS = [
        "netbox-mcp.yaml",
        "netbox-mcp.yml", 
        "netbox-mcp.toml",
        "config/netbox-mcp.yaml",
        "config/netbox-mcp.yml",
        "config/netbox-mcp.toml",
        ".netbox-mcp.yaml",
        ".netbox-mcp.yml",
        ".netbox-mcp.toml",
        "/etc/netbox-mcp/config.yaml",
        "/etc/netbox-mcp/config.yml",
        "/etc/netbox-mcp/config.toml",
    ]
    
    ENV_PREFIX = "NETBOX_"
    
    @classmethod
    def load_config(cls, config_path: Optional[str] = None) -> NetBoxConfig:
        """
        Load configuration from environment variables and optional config file.
        
        Args:
            config_path: Optional path to configuration file
            
        Returns:
            NetBoxConfig: Loaded and validated configuration
        """
        # Start with default configuration
        config_data = {}
        
        # Load from configuration file if found
        if config_path or cls._find_config_file():
            file_path = config_path or cls._find_config_file()
            config_data = cls._load_config_file(file_path)
            logger.info(f"Loaded configuration from {file_path}")
        
        # Override with environment variables and secrets
        env_config = cls._load_from_environment_and_secrets()
        config_data.update(env_config)
        
        # Create and validate configuration
        try:
            # Handle nested dataclass creation
            config_data = cls._process_nested_config(config_data)
            config = NetBoxConfig(**config_data)
            logger.info("Configuration loaded and validated successfully")
            return config
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            raise
    
    @classmethod
    def _find_config_file(cls) -> Optional[str]:
        """Find the first existing configuration file from default paths."""
        for path in cls.DEFAULT_CONFIG_PATHS:
            if Path(path).exists():
                return path
        return None
    
    @classmethod
    def _load_config_file(cls, file_path: str) -> Dict[str, Any]:
        """Load configuration from YAML or TOML file."""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                if path.suffix.lower() in ['.yaml', '.yml']:
                    if yaml is None:
                        raise ImportError("PyYAML is required for YAML configuration files")
                    return yaml.safe_load(f) or {}
                elif path.suffix.lower() == '.toml':
                    if tomllib is None:
                        raise ImportError("tomli/tomllib is required for TOML configuration files")
                    content = f.read()
                    return tomllib.loads(content)
                else:
                    raise ValueError(f"Unsupported configuration file format: {path.suffix}")
        except Exception as e:
            logger.error(f"Failed to load configuration file {file_path}: {e}")
            raise
    
    @classmethod
    def _load_from_environment_and_secrets(cls) -> Dict[str, Any]:
        """Load configuration from environment variables and secrets management."""
        config = {}
        secrets_manager = get_secrets_manager()
        
        # Direct mappings for main config with secrets management
        env_mappings = {
            'NETBOX_URL': 'url',
            'NETBOX_TOKEN': 'token',
            'NETBOX_TIMEOUT': ('timeout', int),
            'NETBOX_VERIFY_SSL': ('verify_ssl', cls._parse_bool),
            'NETBOX_LOG_LEVEL': 'log_level',
            'NETBOX_HEALTH_CHECK_PORT': ('health_check_port', int),
            'NETBOX_MCP_TRANSPORT': 'mcp_transport',
            'NETBOX_MCP_HOST': 'mcp_host',
            'NETBOX_MCP_PORT': ('mcp_port', int),
            'NETBOX_MCP_PATH': ('mcp_path', str),
            'NETBOX_MCP_STATELESS_HTTP': ('mcp_stateless_http', cls._parse_bool),
            'NETBOX_MCP_JSON_RESPONSE': ('mcp_json_response', cls._parse_bool),
            'NETBOX_DEFAULT_PAGE_SIZE': ('default_page_size', int),
            'NETBOX_MAX_RESULTS': ('max_results', int),
            'NETBOX_ENABLE_HEALTH_SERVER': ('enable_health_server', cls._parse_bool),
            'NETBOX_ENABLE_DEGRADED_MODE': ('enable_degraded_mode', cls._parse_bool),
            'NETBOX_ENABLE_READ_OPERATIONS': ('enable_read_operations', cls._parse_bool),
        }
        
        # Safety configuration mappings
        safety_mappings = {
            'NETBOX_DRY_RUN': ('safety.dry_run_mode', cls._parse_bool),
            'NETBOX_REQUIRE_CONFIRMATION': ('safety.require_confirmation', cls._parse_bool),
            'NETBOX_ENABLE_WRITE_OPERATIONS': ('safety.enable_write_operations', cls._parse_bool),
            'NETBOX_WRITE_TIMEOUT': ('safety.write_timeout', int),
            'NETBOX_MAX_BATCH_SIZE': ('safety.max_batch_size', int),
            'NETBOX_AUDIT_ALL_OPERATIONS': ('safety.audit_all_operations', cls._parse_bool),
            'NETBOX_AUDIT_WRITE_DETAILS': ('safety.audit_write_details', cls._parse_bool),
            'NETBOX_ENABLE_TRANSACTION_MODE': ('safety.enable_transaction_mode', cls._parse_bool),
            'NETBOX_AUTO_ROLLBACK_ON_ERROR': ('safety.auto_rollback_on_error', cls._parse_bool),
        }
        
        # Cache configuration mappings
        cache_mappings = {
            'NETBOX_CACHE_ENABLED': ('cache.enabled', cls._parse_bool),
            'NETBOX_CACHE_BACKEND': ('cache.backend', str),
            'NETBOX_CACHE_SIZE_LIMIT_MB': ('cache.size_limit_mb', int),
            'NETBOX_CACHE_MAX_ITEMS': ('cache.max_items', int),
            'NETBOX_CACHE_PATH': ('cache.path', str),
            'NETBOX_CACHE_ENABLE_STATS': ('cache.enable_stats', cls._parse_bool),
        }
        
        # Logging configuration mappings
        logging_mappings = {
            'NETBOX_LOG_LEVEL': ('logging.level', str),
            'NETBOX_LOG_FORMAT': ('logging.format', str),
            'NETBOX_LOG_FILE_ENABLED': ('logging.enable_file_logging', cls._parse_bool),
            'NETBOX_LOG_FILE_PATH': ('logging.log_file_path', str),
            'NETBOX_LOG_FILE_MAX_SIZE_MB': ('logging.max_file_size_mb', int),
            'NETBOX_LOG_FILE_BACKUP_COUNT': ('logging.backup_count', int),
            'NETBOX_LOG_SERVICE_NAME': ('logging.service_name', str),
            'NETBOX_LOG_SERVICE_VERSION': ('logging.service_version', str),
            'NETBOX_LOG_ENABLE_CORRELATION_IDS': ('logging.enable_correlation_ids', cls._parse_bool),
            'NETBOX_LOG_ENABLE_PERFORMANCE': ('logging.enable_performance_logging', cls._parse_bool),
        }
        
        # Combine all mappings
        all_mappings = {**env_mappings, **safety_mappings, **cache_mappings, **logging_mappings}
        
        for env_var, config_key in all_mappings.items():
            # Use secrets manager to get values (handles all sources)
            value = secrets_manager.get_secret(env_var)
            if value is not None:
                if isinstance(config_key, tuple):
                    key, converter = config_key
                    try:
                        value = converter(value)
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Invalid value for {env_var}: {secrets_manager.mask_for_logging(env_var)} ({e})")
                        continue
                else:
                    key = config_key
                
                # Handle nested configuration
                cls._set_nested_value(config, key, value)
        
        return config
    
    @classmethod
    def _load_from_environment(cls) -> Dict[str, Any]:
        """Legacy method - redirects to secrets management."""
        return cls._load_from_environment_and_secrets()
    
    @staticmethod
    def _parse_bool(value: str) -> bool:
        """Parse boolean value from string."""
        if isinstance(value, bool):
            return value
        return value.lower() in ('true', '1', 'yes', 'on', 'enabled')
    
    @staticmethod
    def _set_nested_value(config: Dict[str, Any], key: str, value: Any):
        """Set nested configuration value using dot notation."""
        keys = key.split('.')
        current = config
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        current[keys[-1]] = value
    
    @classmethod
    def _process_nested_config(cls, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process nested configuration to create proper dataclass instances."""
        processed = config_data.copy()
        
        # Handle safety configuration
        if 'safety' in processed and isinstance(processed['safety'], dict):
            processed['safety'] = SafetyConfig(**processed['safety'])
        
        # Handle cache configuration
        if 'cache' in processed and isinstance(processed['cache'], dict):
            cache_config = processed['cache'].copy()
            
            # Handle cache TTL configuration
            if 'ttl' in cache_config and isinstance(cache_config['ttl'], dict):
                cache_config['ttl'] = CacheTTLConfig(**cache_config['ttl'])
            
            processed['cache'] = CacheConfig(**cache_config)
        
        # Handle logging configuration
        if 'logging' in processed and isinstance(processed['logging'], dict):
            processed['logging'] = LoggingConfig(**processed['logging'])
        
        return processed


def load_config(config_path: Optional[str] = None) -> NetBoxConfig:
    """
    Convenience function to load configuration.
    
    Args:
        config_path: Optional path to configuration file
        
    Returns:
        NetBoxConfig: Loaded and validated configuration
    """
    return ConfigurationManager.load_config(config_path)