"""
OpenAPI Specification Generator for NetBox MCP Tools.

This module automatically generates comprehensive OpenAPI 3.0 specifications
from the NetBox MCP tool registry, providing standardized API documentation
for all 142+ tools.
"""

import json
import yaml
import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Union, get_type_hints, get_origin, get_args
from dataclasses import dataclass, field
import inspect
import re

from netbox_mcp.registry import TOOL_REGISTRY, list_tools
from netbox_mcp.exceptions import NetBoxError
from netbox_mcp._version import get_cached_version

logger = logging.getLogger(__name__)


@dataclass
class OpenAPIConfig:
    """Configuration for OpenAPI spec generation."""
    
    title: str = "NetBox MCP Server API"
    description: str = "Model Context Protocol server for NetBox automation with 142+ tools"
    version: str = field(default_factory=get_cached_version)
    server_url: str = "http://localhost:8000"
    contact_name: str = "Deployment Team"
    contact_email: str = "info@deployment-team.nl"
    license_name: str = "MIT"
    license_url: str = "https://opensource.org/licenses/MIT"
    include_examples: bool = True
    include_security: bool = True


class TypeConverter:
    """Convert Python types to OpenAPI schema types."""
    
    @staticmethod
    def python_type_to_openapi(python_type: Any, include_examples: bool = True) -> Dict[str, Any]:
        """
        Convert Python type annotation to OpenAPI schema.
        
        Args:
            python_type: Python type annotation
            include_examples: Whether to include example values
        
        Returns:
            OpenAPI schema dictionary
        """
        # Handle basic types
        if python_type == str:
            schema = {"type": "string"}
            if include_examples:
                schema["example"] = "example_string"
                
        elif python_type == int:
            schema = {"type": "integer", "format": "int32"}
            if include_examples:
                schema["example"] = 42
                
        elif python_type == float:
            schema = {"type": "number", "format": "float"}
            if include_examples:
                schema["example"] = 3.14
                
        elif python_type == bool:
            schema = {"type": "boolean"}
            if include_examples:
                schema["example"] = True
                
        # Handle Optional types
        elif get_origin(python_type) is Union:
            args = get_args(python_type)
            if len(args) == 2 and type(None) in args:
                # This is Optional[T]
                non_none_type = args[0] if args[1] is type(None) else args[1]
                schema = TypeConverter.python_type_to_openapi(non_none_type, include_examples)
                schema["nullable"] = True
            else:
                # Union of multiple types
                schema = {
                    "oneOf": [
                        TypeConverter.python_type_to_openapi(arg, include_examples)
                        for arg in args if arg is not type(None)
                    ]
                }
                
        # Handle List types
        elif get_origin(python_type) is list:
            args = get_args(python_type)
            if args:
                item_schema = TypeConverter.python_type_to_openapi(args[0], include_examples)
            else:
                item_schema = {"type": "string"}
            
            schema = {
                "type": "array",
                "items": item_schema
            }
            if include_examples:
                schema["example"] = ["item1", "item2"]
                
        # Handle Dict types
        elif get_origin(python_type) is dict:
            args = get_args(python_type)
            if len(args) >= 2:
                value_schema = TypeConverter.python_type_to_openapi(args[1], include_examples)
            else:
                value_schema = {"type": "string"}
            
            schema = {
                "type": "object",
                "additionalProperties": value_schema
            }
            if include_examples:
                schema["example"] = {"key": "value"}
                
        # Handle specific NetBox types
        elif hasattr(python_type, '__name__'):
            type_name = python_type.__name__
            
            if type_name == "NetBoxClient":
                # Skip client parameters in API docs
                return None
            elif "Dict" in str(python_type):
                schema = {
                    "type": "object",
                    "additionalProperties": True
                }
                if include_examples:
                    schema["example"] = {"result": "success"}
            else:
                # Unknown type, treat as string
                schema = {"type": "string"}
                if include_examples:
                    schema["example"] = f"<{type_name}>"
        else:
            # Fallback to string
            schema = {"type": "string"}
            if include_examples:
                schema["example"] = "unknown_type"
        
        return schema
    
    @staticmethod
    def extract_enum_values(param_description: str) -> Optional[List[str]]:
        """
        Extract enum values from parameter description.
        
        Args:
            param_description: Parameter description text
        
        Returns:
            List of enum values if found, None otherwise
        """
        # Look for patterns like "Valid options: active, planned, offline"
        enum_patterns = [
            r"Valid options?:\s*([^.]+)",
            r"Choices?:\s*([^.]+)",
            r"Must be one of:\s*([^.]+)",
            r"\(e\.g\.?,?\s*([^)]+)\)",  # More specific pattern for examples in parentheses
            r"Options:\s*([^.]+)",
            r"Available:\s*([^.]+)"
        ]
        
        for pattern in enum_patterns:
            match = re.search(pattern, param_description, re.IGNORECASE)
            if match:
                values_str = match.group(1)
                # Split by comma and clean up
                values = [v.strip().strip('"\'') for v in values_str.split(',')]
                # Filter out empty strings and common non-enum words
                values = [v for v in values if v and len(v) > 1 and v.lower() not in ['etc', 'and', 'or', 'optional', 'required', 'watts', 'in']]
                # Reasonable limit to avoid false positives
                if values and len(values) <= 20:
                    return values
        
        return None


class OpenAPIGenerator:
    """Generate OpenAPI specifications from NetBox MCP tools."""
    
    def __init__(self, config: Optional[OpenAPIConfig] = None):
        """
        Initialize OpenAPI generator.
        
        Args:
            config: OpenAPI configuration
        """
        self.config = config or OpenAPIConfig()
        self._schemas = {}
        self._paths = {}
        self._cached_spec = None
        self._cache_timestamp = None
        self._cache_ttl = 300  # 5 minutes cache TTL
        
        logger.info(f"OpenAPI generator initialized for {self.config.title}")
    
    def generate_spec(self) -> Dict[str, Any]:
        """
        Generate complete OpenAPI specification with caching.
        
        Returns:
            OpenAPI 3.0 specification dictionary
        """
        current_time = time.time()
        
        # Check if we have a valid cached spec
        if (self._cached_spec is not None and 
            self._cache_timestamp is not None and 
            current_time - self._cache_timestamp < self._cache_ttl):
            logger.debug("Returning cached OpenAPI specification")
            return self._cached_spec
        
        logger.info("Generating OpenAPI specification...")
        
        # Get all tools from registry
        tools = list_tools()
        
        # Generate OpenAPI spec structure
        spec = {
            "openapi": "3.0.3",
            "info": self._generate_info(),
            "servers": self._generate_servers(),
            "paths": self._generate_paths(tools),
            "components": {
                "schemas": self._generate_schemas(tools),
                "securitySchemes": self._generate_security_schemes() if self.config.include_security else {}
            }
        }
        
        if self.config.include_security:
            spec["security"] = [{"bearerAuth": []}]
        
        # Cache the generated spec
        self._cached_spec = spec
        self._cache_timestamp = current_time
        
        logger.info(f"Generated and cached OpenAPI spec with {len(spec['paths'])} paths and {len(spec['components']['schemas'])} schemas")
        
        return spec
    
    def invalidate_cache(self):
        """Invalidate the cached OpenAPI specification."""
        self._cached_spec = None
        self._cache_timestamp = None
        logger.debug("OpenAPI specification cache invalidated")
    
    def _parse_type_string(self, type_str: str) -> Any:
        """
        Parse a type string into a Python type with enhanced robustness.
        
        Args:
            type_str: String representation of the type
            
        Returns:
            Corresponding Python type
        """
        if not isinstance(type_str, str):
            return str
            
        # Clean the type string
        type_str = type_str.strip()
        
        # Handle basic types
        basic_types = {
            "str": str,
            "string": str,
            "int": int,
            "integer": int,
            "bool": bool,
            "boolean": bool,
            "float": float,
            "number": float,
            "dict": dict,
            "list": list,
            "List": list,
            "Dict": dict,
        }
        
        if type_str in basic_types:
            return basic_types[type_str]
        
        # Handle Optional types with improved parsing
        if type_str.startswith("Optional[") and type_str.endswith("]"):
            inner_type_str = type_str[9:-1]  # Remove "Optional[" and "]"
            inner_type = self._parse_type_string(inner_type_str)
            return Optional[inner_type]
        
        # Handle Union types
        if type_str.startswith("Union[") and type_str.endswith("]"):
            # For simplicity, return the first type in Union
            inner_types_str = type_str[6:-1]  # Remove "Union[" and "]"
            first_type = inner_types_str.split(",")[0].strip()
            return self._parse_type_string(first_type)
        
        # Handle List types
        if type_str.startswith("List[") and type_str.endswith("]"):
            inner_type_str = type_str[5:-1]  # Remove "List[" and "]"
            inner_type = self._parse_type_string(inner_type_str)
            return List[inner_type]
        
        # Handle Dict types
        if type_str.startswith("Dict[") and type_str.endswith("]"):
            return dict
        
        # Handle complex types that we don't recognize
        logger.debug(f"Unrecognized type string: '{type_str}', defaulting to str")
        return str
    
    def _generate_info(self) -> Dict[str, Any]:
        """Generate OpenAPI info section."""
        info = {
            "title": self.config.title,
            "description": self.config.description,
            "version": self.config.version,
            "contact": {
                "name": self.config.contact_name,
                "email": self.config.contact_email
            },
            "license": {
                "name": self.config.license_name,
                "url": self.config.license_url
            }
        }
        
        return info
    
    def _generate_servers(self) -> List[Dict[str, Any]]:
        """Generate OpenAPI servers section."""
        return [
            {
                "url": self.config.server_url,
                "description": "NetBox MCP Server"
            }
        ]
    
    def _generate_security_schemes(self) -> Dict[str, Any]:
        """Generate OpenAPI security schemes."""
        return {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "NetBox API token authentication"
            }
        }
    
    def _generate_paths(self, tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate OpenAPI paths from tools."""
        paths = {}
        
        # Group tools by category for better organization
        tools_by_category = {}
        for tool in tools:
            category = tool.get("category", "general")
            if category not in tools_by_category:
                tools_by_category[category] = []
            tools_by_category[category].append(tool)
        
        # Generate paths for each tool
        for category, category_tools in tools_by_category.items():
            for tool in category_tools:
                path = f"/api/v1/tools/{tool['name']}"
                paths[path] = self._generate_path_item(tool, category)
        
        # Add utility endpoints
        paths.update(self._generate_utility_paths())
        
        return paths
    
    def _generate_path_item(self, tool: Dict[str, Any], category: str) -> Dict[str, Any]:
        """Generate OpenAPI path item for a tool."""
        tool_name = tool["name"]
        description = tool.get("description", "")
        parameters = tool.get("parameters", [])
        
        # Determine if this is a write operation
        is_write_operation = any(keyword in tool_name.lower() 
                               for keyword in ["create", "update", "delete", "provision", "assign"])
        
        # Generate operation
        operation = {
            "summary": f"Execute {tool_name}",
            "description": description,
            "tags": [category.upper()],
            "operationId": tool_name,
            "requestBody": self._generate_request_body(parameters, tool_name),
            "responses": self._generate_responses(tool, is_write_operation),
        }
        
        # Add security for write operations
        if is_write_operation and self.config.include_security:
            operation["security"] = [{"bearerAuth": []}]
        
        return {"post": operation}
    
    def _generate_request_body(self, parameters: List[Dict[str, Any]], tool_name: str) -> Dict[str, Any]:
        """Generate request body schema for tool parameters."""
        properties = {}
        required = []
        
        for param in parameters:
            param_name = param["name"]
            
            # Skip client parameter
            if param_name == "client":
                continue
            
            param_type = param.get("type", "string")
            param_required = param.get("required", False)
            param_default = param.get("default")
            param_description = param.get("description", "")
            
            # Convert Python type to OpenAPI schema with robust parsing
            try:
                python_type = self._parse_type_string(param_type)
                schema = TypeConverter.python_type_to_openapi(python_type, self.config.include_examples)
                
                if schema is None:
                    continue  # Skip client parameters
                
            except Exception as e:
                # Enhanced error logging for debugging
                logger.warning(f"Failed to parse type '{param_type}' for parameter '{param_name}': {e}")
                # Fallback schema
                schema = {"type": "string"}
            
            # Add description
            if param_description:
                schema["description"] = param_description
            
            # Add default value
            if param_default is not None:
                schema["default"] = param_default
            
            # Check for enum values in description
            enum_values = TypeConverter.extract_enum_values(param_description)
            if enum_values:
                schema["enum"] = enum_values
            
            # Special handling for confirm parameter
            if param_name == "confirm":
                schema.update({
                    "type": "boolean",
                    "default": False,
                    "description": "Must be true to execute write operations (safety mechanism)"
                })
            
            properties[param_name] = schema
            
            if param_required:
                required.append(param_name)
        
        schema = {
            "type": "object",
            "properties": properties
        }
        
        if required:
            schema["required"] = required
        
        # Add example request body
        if self.config.include_examples:
            example = {}
            for param_name, param_schema in properties.items():
                if "example" in param_schema:
                    example[param_name] = param_schema["example"]
                elif "default" in param_schema:
                    example[param_name] = param_schema["default"]
            
            if example:
                schema["example"] = example
        
        return {
            "required": True,
            "content": {
                "application/json": {
                    "schema": schema
                }
            }
        }
    
    def _generate_responses(self, tool: Dict[str, Any], is_write_operation: bool) -> Dict[str, Any]:
        """Generate response schemas for a tool."""
        tool_name = tool["name"]
        
        # Success response schema
        success_schema = {
            "type": "object",
            "properties": {
                "success": {
                    "type": "boolean",
                    "example": True
                },
                "message": {
                    "type": "string",
                    "example": f"Operation {tool_name} completed successfully"
                },
                "data": {
                    "type": "object",
                    "additionalProperties": True,
                    "description": "Operation result data"
                }
            },
            "required": ["success"]
        }
        
        # Dry-run response for write operations
        if is_write_operation:
            dry_run_schema = {
                "type": "object",
                "properties": {
                    "success": {
                        "type": "boolean",
                        "example": True
                    },
                    "dry_run": {
                        "type": "boolean",
                        "example": True
                    },
                    "message": {
                        "type": "string",
                        "example": f"DRY RUN: {tool_name} would be executed. Set confirm=True to execute."
                    },
                    "would_create": {
                        "type": "object",
                        "additionalProperties": True,
                        "description": "Preview of what would be created/modified"
                    }
                },
                "required": ["success", "dry_run"]
            }
        
        # Error response schema
        error_schema = {
            "type": "object",
            "properties": {
                "error": {
                    "type": "string",
                    "example": "NetBoxValidationError"
                },
                "message": {
                    "type": "string",
                    "example": "Validation failed for required parameter"
                },
                "details": {
                    "type": "object",
                    "additionalProperties": True,
                    "description": "Additional error details"
                }
            },
            "required": ["error", "message"]
        }
        
        responses = {
            "200": {
                "description": "Successful operation",
                "content": {
                    "application/json": {
                        "schema": success_schema
                    }
                }
            },
            "400": {
                "description": "Validation error",
                "content": {
                    "application/json": {
                        "schema": error_schema
                    }
                }
            },
            "404": {
                "description": "Resource not found",
                "content": {
                    "application/json": {
                        "schema": error_schema
                    }
                }
            },
            "500": {
                "description": "Internal server error",
                "content": {
                    "application/json": {
                        "schema": error_schema
                    }
                }
            }
        }
        
        # Add dry-run response for write operations
        if is_write_operation:
            responses["202"] = {
                "description": "Dry-run mode (confirm=False)",
                "content": {
                    "application/json": {
                        "schema": dry_run_schema
                    }
                }
            }
        
        return responses
    
    def _generate_utility_paths(self) -> Dict[str, Any]:
        """Generate utility endpoint paths."""
        return {
            "/api/v1/health": {
                "get": {
                    "summary": "Health check",
                    "description": "Check server health status",
                    "tags": ["System"],
                    "operationId": "health_check",
                    "responses": {
                        "200": {
                            "description": "Health status",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string", "example": "healthy"},
                                            "version": {"type": "string", "example": f"{get_cached_version()}"},
                                            "uptime": {"type": "string", "example": "2h 30m"},
                                            "checks": {
                                                "type": "object",
                                                "additionalProperties": True
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/api/v1/tools": {
                "get": {
                    "summary": "List all tools",
                    "description": "Get list of all available NetBox MCP tools",
                    "tags": ["Tools"],
                    "operationId": "list_tools",
                    "parameters": [
                        {
                            "name": "category",
                            "in": "query",
                            "description": "Filter tools by category",
                            "required": False,
                            "schema": {
                                "type": "string",
                                "enum": ["dcim", "ipam", "tenancy", "virtualization", "system"]
                            }
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "List of tools",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "name": {"type": "string"},
                                                "description": {"type": "string"},
                                                "category": {"type": "string"},
                                                "parameters": {"type": "array"}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/api/v1/metrics": {
                "get": {
                    "summary": "Get performance metrics",
                    "description": "Get server performance metrics and statistics",
                    "tags": ["Monitoring"],
                    "operationId": "get_metrics",
                    "responses": {
                        "200": {
                            "description": "Performance metrics",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "success": {
                                                "type": "boolean",
                                                "example": True
                                            },
                                            "message": {
                                                "type": "string",
                                                "example": "Performance metrics retrieved successfully"
                                            },
                                            "data": {
                                                "type": "object",
                                                "properties": {
                                                    "timestamp": {"type": "string", "example": "2025-07-05T10:30:00Z"},
                                                    "system_metrics": {
                                                        "type": "object",
                                                        "properties": {
                                                            "cpu_usage": {"type": "number", "example": 15.2},
                                                            "memory_usage": {"type": "number", "example": 2048.5},
                                                            "active_connections": {"type": "integer", "example": 25}
                                                        }
                                                    },
                                                    "operation_metrics": {
                                                        "type": "array",
                                                        "items": {
                                                            "type": "object",
                                                            "properties": {
                                                                "operation_name": {"type": "string"},
                                                                "total_executions": {"type": "integer"},
                                                                "success_rate": {"type": "number"},
                                                                "average_duration": {"type": "number"}
                                                            }
                                                        }
                                                    },
                                                    "cache_metrics": {
                                                        "type": "object",
                                                        "properties": {
                                                            "hit_ratio": {"type": "number", "example": 0.85},
                                                            "cache_size_mb": {"type": "number", "example": 128.5},
                                                            "total_requests": {"type": "integer", "example": 1500}
                                                        }
                                                    }
                                                }
                                            }
                                        },
                                        "required": ["success", "data"]
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    
    def _generate_schemas(self, tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate reusable component schemas."""
        schemas = {
            "NetBoxError": {
                "type": "object",
                "properties": {
                    "error": {
                        "type": "string",
                        "description": "Error type"
                    },
                    "message": {
                        "type": "string",
                        "description": "Error message"
                    },
                    "details": {
                        "type": "object",
                        "additionalProperties": True,
                        "description": "Additional error details"
                    }
                },
                "required": ["error", "message"]
            },
            "SuccessResponse": {
                "type": "object",
                "properties": {
                    "success": {
                        "type": "boolean",
                        "description": "Operation success status"
                    },
                    "message": {
                        "type": "string",
                        "description": "Success message"
                    },
                    "data": {
                        "type": "object",
                        "additionalProperties": True,
                        "description": "Operation result data"
                    }
                },
                "required": ["success"]
            },
            "DryRunResponse": {
                "type": "object",
                "properties": {
                    "success": {
                        "type": "boolean",
                        "description": "Operation success status"
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Indicates this was a dry run"
                    },
                    "message": {
                        "type": "string",
                        "description": "Dry run message"
                    },
                    "would_create": {
                        "type": "object",
                        "additionalProperties": True,
                        "description": "Preview of what would be created"
                    }
                },
                "required": ["success", "dry_run"]
            }
        }
        
        return schemas
    
    def export_spec(self, format: str = "json", output_file: Optional[str] = None) -> str:
        """
        Export OpenAPI specification to file or string.
        
        Args:
            format: Export format ("json" or "yaml")
            output_file: Optional output file path
        
        Returns:
            Specification as string
        """
        spec = self.generate_spec()
        
        if format.lower() == "yaml":
            content = yaml.dump(spec, default_flow_style=False, sort_keys=False)
        else:
            content = json.dumps(spec, indent=2)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(content)
            logger.info(f"OpenAPI spec exported to {output_file}")
        
        return content
    
    def generate_postman_collection(self) -> Dict[str, Any]:
        """
        Generate Postman collection from OpenAPI spec.
        
        Returns:
            Postman collection dictionary
        """
        spec = self.generate_spec()
        
        collection = {
            "info": {
                "name": spec["info"]["title"],
                "description": spec["info"]["description"],
                "version": spec["info"]["version"],
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
            },
            "auth": {
                "type": "bearer",
                "bearer": [
                    {
                        "key": "token",
                        "value": "{{netbox_token}}",
                        "type": "string"
                    }
                ]
            },
            "variable": [
                {
                    "key": "base_url",
                    "value": self.config.server_url,
                    "type": "string"
                },
                {
                    "key": "netbox_token",
                    "value": "your_netbox_token_here",
                    "type": "string"
                }
            ],
            "item": []
        }
        
        # Group requests by category
        categories = {}
        for path, path_item in spec["paths"].items():
            for method, operation in path_item.items():
                category = operation.get("tags", ["General"])[0]
                
                if category not in categories:
                    categories[category] = {
                        "name": category,
                        "item": []
                    }
                
                # Create Postman request
                request = {
                    "name": operation["summary"],
                    "request": {
                        "method": method.upper(),
                        "header": [
                            {
                                "key": "Content-Type",
                                "value": "application/json",
                                "type": "text"
                            }
                        ],
                        "url": {
                            "raw": f"{{{{base_url}}}}{path}",
                            "host": ["{{base_url}}"],
                            "path": path.strip("/").split("/")
                        },
                        "description": operation.get("description", "")
                    }
                }
                
                # Add request body for POST requests
                if method.lower() == "post" and "requestBody" in operation:
                    request_body = operation["requestBody"]
                    schema = request_body["content"]["application/json"]["schema"]
                    
                    if "example" in schema:
                        request["request"]["body"] = {
                            "mode": "raw",
                            "raw": json.dumps(schema["example"], indent=2)
                        }
                
                categories[category]["item"].append(request)
        
        # Add categories to collection
        collection["item"] = list(categories.values())
        
        return collection


def generate_api_documentation(
    output_dir: str = "docs/api",
    formats: List[str] = ["json", "yaml"],
    include_postman: bool = True,
    config: Optional[OpenAPIConfig] = None
) -> Dict[str, str]:
    """
    Generate complete API documentation.
    
    Args:
        output_dir: Output directory for generated files
        formats: List of formats to generate ("json", "yaml")
        include_postman: Whether to generate Postman collection
        config: OpenAPI configuration
    
    Returns:
        Dictionary mapping format to output file path
    """
    import os
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    generator = OpenAPIGenerator(config)
    generated_files = {}
    
    # Generate OpenAPI specs
    for format in formats:
        filename = f"netbox-mcp-api.{format}"
        filepath = os.path.join(output_dir, filename)
        
        generator.export_spec(format=format, output_file=filepath)
        generated_files[format] = filepath
        
        logger.info(f"Generated {format.upper()} specification: {filepath}")
    
    # Generate Postman collection
    if include_postman:
        postman_collection = generator.generate_postman_collection()
        postman_file = os.path.join(output_dir, "NetBox-MCP.postman_collection.json")
        
        with open(postman_file, 'w') as f:
            json.dump(postman_collection, f, indent=2)
        
        generated_files["postman"] = postman_file
        logger.info(f"Generated Postman collection: {postman_file}")
    
    logger.info(f"API documentation generated in {output_dir}")
    return generated_files


if __name__ == "__main__":
    # Generate API documentation when run directly
    logging.basicConfig(level=logging.INFO)
    
    config = OpenAPIConfig(
        title="NetBox MCP Server API",
        description="Production-ready Model Context Protocol server for NetBox automation with 142+ enterprise-grade tools covering DCIM, IPAM, Virtualization, and Tenancy management.",
        version=get_cached_version()
    )
    
    files = generate_api_documentation(config=config)
    
    print("Generated API documentation:")
    for format, filepath in files.items():
        print(f"  {format.upper()}: {filepath}")