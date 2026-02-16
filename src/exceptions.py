"""
NetBox MCP Server Exception Classes

Custom exceptions for the NetBox MCP server, providing clear error handling
and consistent error responses for LLM interactions.
"""


class NetBoxError(Exception):
    """Base exception for all NetBox MCP server errors."""
    
    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> dict:
        """Convert exception to dictionary for JSON serialization."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "details": self.details
        }


class NetBoxConnectionError(NetBoxError):
    """Raised when connection to NetBox API fails."""


class NetBoxAuthError(NetBoxError):
    """Raised when NetBox API authentication fails."""


class NetBoxValidationError(NetBoxError):
    """Raised when data validation fails."""


class NetBoxNotFoundError(NetBoxError):
    """Raised when requested NetBox object is not found."""


class NetBoxPermissionError(NetBoxError):
    """Raised when insufficient permissions for operation."""


class NetBoxWriteError(NetBoxError):
    """Raised when write operation fails."""


class NetBoxConfirmationError(NetBoxError):
    """Raised when write operation attempted without proper confirmation."""
    
    def __init__(self, operation: str):
        message = f"Write operation '{operation}' requires confirm=True parameter"
        super().__init__(message, {"operation": operation, "required_parameter": "confirm=True"})


class NetBoxDryRunError(NetBoxError):
    """Raised when actual operation is attempted in dry-run mode."""
    
    def __init__(self, operation: str):
        message = f"Cannot execute '{operation}' in dry-run mode"
        super().__init__(message, {"operation": operation, "mode": "dry-run"})


class NetBoxConflictError(NetBoxError):
    """Raised when a resource conflict is detected (e.g., duplicate names, existing objects)."""
    
    def __init__(self, resource_type: str, identifier: str, existing_id: int = None):
        message = f"Conflict: {resource_type} '{identifier}' already exists"
        details = {"resource_type": resource_type, "identifier": identifier}
        if existing_id:
            details["existing_id"] = existing_id
            message += f" (ID: {existing_id})"
        super().__init__(message, details)