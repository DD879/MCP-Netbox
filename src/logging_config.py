#!/usr/bin/env python3
"""
Enterprise Structured Logging Configuration for NetBox MCP

Provides JSON-structured logging for enterprise deployment with:
- Structured JSON output for log aggregation systems
- Correlation IDs for request tracing
- Performance metrics integration
- Security-focused log filtering
- Multi-environment configuration support

Features:
- ELK Stack / Splunk / Datadog compatible JSON format
- Request correlation tracking
- Performance timing integration
- Secrets masking for security
- Configurable log levels per component
"""

import json
import logging
import logging.config
import time
import uuid
from typing import Dict, Any, Optional, Union
from datetime import datetime, timezone
from pathlib import Path
import inspect
import threading

from .secrets import get_secrets_manager


class CorrelationContextManager:
    """Thread-local correlation ID management for request tracing."""
    
    def __init__(self):
        self._local = threading.local()
    
    def set_correlation_id(self, correlation_id: str):
        """Set correlation ID for current thread."""
        self._local.correlation_id = correlation_id
    
    def get_correlation_id(self) -> Optional[str]:
        """Get correlation ID for current thread."""
        return getattr(self._local, 'correlation_id', None)
    
    def generate_correlation_id(self) -> str:
        """Generate new correlation ID and set it for current thread."""
        correlation_id = str(uuid.uuid4())[:8]
        self.set_correlation_id(correlation_id)
        return correlation_id
    
    def clear_correlation_id(self):
        """Clear correlation ID for current thread."""
        if hasattr(self._local, 'correlation_id'):
            delattr(self._local, 'correlation_id')


# Global correlation context manager
correlation_context = CorrelationContextManager()


class StructuredFormatter(logging.Formatter):
    """
    JSON structured log formatter for enterprise log aggregation.
    
    Produces logs in structured JSON format compatible with:
    - ELK Stack (Elasticsearch, Logstash, Kibana)
    - Splunk Enterprise
    - Datadog Logs
    - AWS CloudWatch Logs
    - Azure Monitor Logs
    """
    
    def __init__(self, service_name: str = "netbox-mcp", service_version: str = None):
        super().__init__()
        self.service_name = service_name
        if service_version is None:
            try:
                from ._version import get_cached_version
                self.service_version = get_cached_version()
            except ImportError:
                self.service_version = "1.0.0"
        else:
            self.service_version = service_version
        self.secrets_manager = get_secrets_manager()
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        
        # Base log structure
        log_entry = {
            # Standard fields
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            
            # Service identification
            "service": {
                "name": self.service_name,
                "version": self.service_version
            },
            
            # Source location
            "source": {
                "file": record.filename,
                "line": record.lineno,
                "function": record.funcName,
                "module": record.module
            },
            
            # Process/thread information
            "process": {
                "pid": record.process,
                "thread_name": record.threadName,
                "thread_id": record.thread
            }
        }
        
        # Add correlation ID if available
        correlation_id = correlation_context.get_correlation_id()
        if correlation_id:
            log_entry["correlation_id"] = correlation_id
        
        # Add exception information if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info) if record.exc_info else None
            }
        
        # Add custom fields from log record
        custom_fields = {}
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 
                          'msecs', 'relativeCreated', 'thread', 'threadName', 
                          'processName', 'process', 'getMessage', 'exc_info', 
                          'exc_text', 'stack_info']:
                # Mask secrets in custom fields
                if isinstance(value, str) and self._looks_like_secret(key, value):
                    custom_fields[key] = self._mask_secret_value(value)
                else:
                    custom_fields[key] = value
        
        if custom_fields:
            log_entry["custom"] = custom_fields
        
        # Add performance timing if available
        if hasattr(record, 'duration_ms'):
            log_entry["performance"] = {
                "duration_ms": record.duration_ms
            }
        
        # Add NetBox operation context if available
        if hasattr(record, 'netbox_operation'):
            log_entry["netbox"] = {
                "operation": record.netbox_operation,
                "endpoint": getattr(record, 'netbox_endpoint', None),
                "object_type": getattr(record, 'netbox_object_type', None),
                "object_id": getattr(record, 'netbox_object_id', None),
                "dry_run": getattr(record, 'netbox_dry_run', None)
            }
        
        # Add HTTP request context if available
        if hasattr(record, 'http_method'):
            log_entry["http"] = {
                "method": record.http_method,
                "path": getattr(record, 'http_path', None),
                "status_code": getattr(record, 'http_status_code', None),
                "user_agent": getattr(record, 'http_user_agent', None),
                "remote_addr": getattr(record, 'http_remote_addr', None)
            }
        
        return json.dumps(log_entry, default=str)
    
    def _looks_like_secret(self, key: str, value: str) -> bool:
        """Heuristic to detect if a field might contain secrets."""
        secret_indicators = [
            'token', 'password', 'secret', 'key', 'credential', 
            'auth', 'api_key', 'api_token', 'bearer'
        ]
        key_lower = key.lower()
        return any(indicator in key_lower for indicator in secret_indicators)
    
    def _mask_secret_value(self, value: str) -> str:
        """Mask secret values for safe logging."""
        if len(value) <= 4:
            return "***"
        return "***" + value[-4:]


class PerformanceLoggerMixin:
    """Mixin to add performance timing to log records."""
    
    def log_with_timing(self, level: int, msg: str, start_time: float, **kwargs):
        """Log message with performance timing."""
        duration_ms = (time.time() - start_time) * 1000
        extra = kwargs.get('extra', {})
        extra['duration_ms'] = round(duration_ms, 3)
        kwargs['extra'] = extra
        self.log(level, msg, **kwargs)


class NetBoxOperationLogger(logging.Logger, PerformanceLoggerMixin):
    """Specialized logger for NetBox operations."""
    
    def netbox_operation(self, level: int, msg: str, operation: str, 
                        endpoint: str = None, object_type: str = None, 
                        object_id: Union[int, str] = None, dry_run: bool = None, 
                        start_time: float = None, **kwargs):
        """Log NetBox operation with structured context."""
        extra = kwargs.get('extra', {})
        extra.update({
            'netbox_operation': operation,
            'netbox_endpoint': endpoint,
            'netbox_object_type': object_type,
            'netbox_object_id': object_id,
            'netbox_dry_run': dry_run
        })
        
        if start_time is not None:
            duration_ms = (time.time() - start_time) * 1000
            extra['duration_ms'] = round(duration_ms, 3)
        
        kwargs['extra'] = extra
        self.log(level, msg, **kwargs)
    
    def netbox_read(self, msg: str, endpoint: str, start_time: float = None, **kwargs):
        """Log NetBox read operation."""
        self.netbox_operation(logging.INFO, msg, "read", endpoint=endpoint, 
                            start_time=start_time, **kwargs)
    
    def netbox_write(self, msg: str, operation: str, object_type: str, 
                    object_id: Union[int, str] = None, dry_run: bool = None, 
                    start_time: float = None, **kwargs):
        """Log NetBox write operation."""
        self.netbox_operation(logging.WARNING if not dry_run else logging.INFO, 
                            msg, operation, object_type=object_type, 
                            object_id=object_id, dry_run=dry_run, 
                            start_time=start_time, **kwargs)
    
    def netbox_error(self, msg: str, operation: str, error: Exception, 
                    endpoint: str = None, start_time: float = None, **kwargs):
        """Log NetBox operation error."""
        extra = kwargs.get('extra', {})
        extra.update({
            'netbox_operation': operation,
            'netbox_endpoint': endpoint,
            'error_type': type(error).__name__,
            'error_message': str(error)
        })
        
        if start_time is not None:
            duration_ms = (time.time() - start_time) * 1000
            extra['duration_ms'] = round(duration_ms, 3)
        
        kwargs['extra'] = extra
        self.error(msg, exc_info=True, **kwargs)


# Register custom logger class
logging.setLoggerClass(NetBoxOperationLogger)


def setup_structured_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    log_file: Optional[str] = None,
    service_name: str = "netbox-mcp",
    service_version: str = None,
    enable_console: bool = True,
    enable_file: bool = False,
) -> Dict[str, Any]:
    """
    Setup structured logging configuration.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Format type ("json" for structured, "text" for human-readable)
        log_file: Optional log file path
        service_name: Service name for log identification
        service_version: Service version for log identification
        enable_console: Enable console logging
        enable_file: Enable file logging

    Returns:
        dict logging configuration suitable for logging.config.dictConfig()
    """

    # Determine formatters
    formatters: Dict[str, Any] = {}

    if log_format == "json":
        formatters["structured"] = {
            "()": StructuredFormatter,
            "service_name": service_name,
            "service_version": service_version,
        }
        default_formatter = "structured"
    else:
        formatters["standard"] = {
            "format": "%(asctime)s [%(levelname)8s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
        default_formatter = "standard"

    # Setup handlers
    handlers: Dict[str, Any] = {}
    root_handlers = []

    if enable_console:
        handlers["console"] = {
            "class": "logging.StreamHandler",
            "formatter": default_formatter,
            "level": log_level,
            "stream": "ext://sys.stdout",
        }
        root_handlers.append("console")

    if enable_file and log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": log_file,
            "formatter": default_formatter,
            "level": log_level,
            "maxBytes": 10 * 1024 * 1024,  # 10MB
            "backupCount": 5,
            "encoding": "utf-8",
        }
        root_handlers.append("file")

    loggers: Dict[str, Any] = {
        "netbox_mcp": {"level": log_level, "handlers": root_handlers, "propagate": False},
        "netbox_mcp.secrets": {"level": "WARNING"},  # Reduce secrets manager verbosity
        "urllib3": {"level": "WARNING"},
        "requests": {"level": "WARNING"},
        "pynetbox": {"level": "INFO"},
    }

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": formatters,
        "handlers": handlers,
        "loggers": loggers,
        "root": {"level": log_level, "handlers": root_handlers},
    }


def configure_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    log_file: Optional[str] = None,
    service_name: str = "netbox-mcp",
    service_version: str = None,
):
    """
    Configure and apply structured logging settings.

    Args:
        log_level: Logging level
        log_format: Format type ("json" or "text")
        log_file: Optional log file path
        service_name: Service name
        service_version: Service version
    """
    # Get dynamic version if not provided
    if service_version is None:
        try:
            import importlib.metadata

            service_version = importlib.metadata.version(service_name)
        except Exception:
            service_version = "unknown"

    # Determine if we're in a container/production environment
    is_production = Path("/app").exists() or Path("/run/secrets").exists()

    config = setup_structured_logging(
        log_level=log_level,
        # Prefer structured logs in production environments
        log_format="json" if is_production else log_format,
        log_file=log_file,
        service_name=service_name,
        service_version=service_version,
        enable_console=True,
        enable_file=bool(log_file),
    )

    logging.config.dictConfig(config)

    # Initialize correlation ID for this process/thread
    try:
        correlation_context.generate_correlation_id()
    except Exception:
        pass


def get_logger(name: str) -> NetBoxOperationLogger:
    """Get a NetBoxOperationLogger instance."""
    return logging.getLogger(name)  # type: ignore[return-value]


class correlation_id:
    """Context manager to set a correlation ID for a block of work."""

    def __init__(self, correlation_id: Optional[str] = None):
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self._previous = None

    def __enter__(self):
        self._previous = correlation_context.get_correlation_id()
        correlation_context.set_correlation_id(self.correlation_id)
        return self.correlation_id

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._previous:
            correlation_context.set_correlation_id(self._previous)


class operation_timing:
    """Context manager that measures elapsed time and logs it."""

    def __init__(self, logger: logging.Logger, operation: str, **context):
        self.logger = logger
        self.operation = operation
        self.context = context
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        self.logger.info(f"Starting operation: {self.operation}", extra=self.context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is None:
            return
        duration_ms = (time.time() - self.start_time) * 1000

        if exc_type:
            self.logger.error(
                f"Operation failed: {self.operation}",
                extra={**self.context, "duration_ms": round(duration_ms, 2), "error": str(exc_val)},
                exc_info=True,
            )
        else:
            self.logger.info(
                f"Operation completed: {self.operation}",
                extra={**self.context, "duration_ms": round(duration_ms, 2)},
            )


__all__ = [
    "StructuredFormatter",
    "CorrelationContext",
    "correlation_context",
    "NetBoxOperationLogger",
    "setup_structured_logging",
    "configure_logging",
    "get_logger",
    "correlation_id",
    "operation_timing",
]
