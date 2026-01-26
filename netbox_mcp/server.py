#!/usr/bin/env python3
"""
NetBox MCP Server

A Model Context Protocol server for safe read/write access to NetBox instances.
Provides tools for querying and managing NetBox data with comprehensive safety controls.

Version: 0.9.7 - Hierarchical Architecture with Registry Bridge
"""

from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from .client import NetBoxClient
from .config import load_config
from .registry import (
    TOOL_REGISTRY, PROMPT_REGISTRY, 
    load_tools, load_prompts, 
    serialize_registry_for_api, serialize_prompts_for_api,
    execute_tool, execute_prompt
)
from .dependencies import NetBoxClientManager, get_netbox_client  # Use new dependency system
from .monitoring import get_performance_monitor, MetricsCollector, HealthCheck, MetricsDashboard
from .openapi_generator import OpenAPIGenerator, generate_api_documentation
from .debug_monitor import get_monitor, log_startup, log_protocol_message, log_connection_event, log_error, log_performance, log_tool_call
from ._version import get_cached_version
import logging
import os
import threading
import time
import signal
import sys
import inspect
from functools import wraps
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from typing import Dict, List, Optional, Any

# Configure logging (will be updated from config)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 🧠 ULTRATHINK DEBUG: Initialize monitoring
log_startup("Debug monitor initialized - starting server diagnostics")

# === REGISTRY BRIDGE IMPLEMENTATION ===

# Step 1: Load all tools and prompts into our internal registries
log_startup("Loading tools and prompts into registry")
load_tools()
load_prompts()
logger.info(f"Internal tool registry initialized with {len(TOOL_REGISTRY)} tools")
logger.info(f"Internal prompt registry initialized with {len(PROMPT_REGISTRY)} prompts")
log_startup(f"Registry loaded: {len(TOOL_REGISTRY)} tools, {len(PROMPT_REGISTRY)} prompts")

# Step 2: FastMCP server instance is created during initialize_server() once configuration is loaded
mcp: Optional[FastMCP] = None

# 🧠 ULTRATHINK DEBUG: Add MCP protocol message interceptor
def add_mcp_protocol_logging(mcp_instance: FastMCP):
    """Add protocol-level logging to FastMCP to monitor Claude Desktop communication."""
    original_handle_request = None

    try:
        # Try to find and wrap the request handler
        if hasattr(mcp_instance, '_server') and hasattr(mcp_instance._server, 'request_handlers'):
            handlers = mcp_instance._server.request_handlers
            log_startup("Found FastMCP request handlers - adding protocol logging")

            # Wrap each handler to log messages
            for method, handler in handlers.items():
                original_handler = handler

                def create_logged_handler(method_name, orig_handler):
                    async def logged_handler(request):
                        log_protocol_message("RECEIVED", {
                            "method": method_name,
                            "params": getattr(request, 'params', None),
                            "id": getattr(request, 'id', None)
                        })
                        result = await orig_handler(request)
                        log_protocol_message("SENT", {
                            "method": method_name,
                            "result": "response_sent",
                            "id": getattr(request, 'id', None)
                        })
                        return result
                    return logged_handler

                handlers[method] = create_logged_handler(method, original_handler)
        else:
            log_startup("FastMCP request handlers not found - protocol logging unavailable")

    except Exception as e:
        log_error(f"Failed to add MCP protocol logging: {e}", e)

# Step 3: The Registry Bridge function
def bridge_tools_to_fastmcp(mcp_instance: FastMCP):
    """
    Dynamically registers all tools from our internal TOOL_REGISTRY
    with the FastMCP instance, creating wrappers for dependency injection.
    """
    bridged_count = 0
    for tool_name, tool_metadata in TOOL_REGISTRY.items():
        try:
            original_func = tool_metadata["function"]
            description = tool_metadata.get("description", f"Executes the {tool_name} tool.")
            category = tool_metadata.get("category", "General")

            # Create a 'wrapper' that injects the client with EXACT function signature (Gemini's Fix)
            def create_tool_wrapper(original_func):
                """
                Creates a tool wrapper that mimics the exact signature of the original function,
                while automatically injecting the NetBox client and preventing argument duplicates.
                """
                sig = inspect.signature(original_func)
                wrapper_params = [p for p in sig.parameters.values() if p.name != 'client']

                @wraps(original_func)
                def tool_wrapper(*args, **kwargs):
                    # 🧠 ULTRATHINK DEBUG: Log tool calls from Claude Desktop
                    from .debug_monitor import log_tool_call
                    log_tool_call(tool_name, kwargs)

                    # Get performance monitor for timing
                    monitor = get_performance_monitor()

                    with monitor.time_operation(tool_name, kwargs):
                        try:
                            # ----- SAFE ARGUMENT HANDLING -----
                            # 1. Create a list of expected parameter names (excluding 'client')
                            param_names = [p.name for p in wrapper_params]

                            # 2. Create a dictionary from positional arguments (*args)
                            final_kwargs = dict(zip(param_names, args))

                            # 3. Update with keyword arguments (**kwargs).
                            #    This overwrites any duplicates and is the core of the fix.
                            final_kwargs.update(kwargs)
                            # ----------------------------------------

                            client = get_netbox_client()

                            # Call the original function with clean, deduplicated arguments.
                            return original_func(client, **final_kwargs)

                        except Exception as e:
                            logger.error(f"Execution of tool '{tool_name}' failed: {e}", exc_info=True)
                            return {"success": False, "error": str(e), "error_type": type(e).__name__}

                new_sig = sig.replace(parameters=wrapper_params)
                # Use setattr to avoid type checker issues with __signature__
                setattr(tool_wrapper, '__signature__', new_sig)
                return tool_wrapper

            # Register the 'wrapper' with FastMCP with the correct metadata
            wrapped_tool = create_tool_wrapper(original_func)
            mcp_instance.tool(name=tool_name, description=description)(wrapped_tool)

            bridged_count += 1
            logger.debug(f"Bridged tool: {tool_name} (category: {category})")

        except Exception as e:
            logger.error(f"Failed to bridge tool '{tool_name}' to FastMCP: {e}", exc_info=True)

    logger.info(f"Successfully bridged {bridged_count}/{len(TOOL_REGISTRY)} tools to the FastMCP interface")
    log_startup(f"Tools bridged to FastMCP: {bridged_count}/{len(TOOL_REGISTRY)} successful")

# Step 5: Bridge prompts to FastMCP
def bridge_prompts_to_fastmcp(mcp_instance: FastMCP):
    """
    Bridge internal prompt registry to FastMCP interface.
    
    This function creates FastMCP-compatible prompt handlers for each
    prompt in our internal PROMPT_REGISTRY and registers them with the FastMCP server.
    """
    bridged_count = 0
    
    for prompt_name, prompt_metadata in PROMPT_REGISTRY.items():
        try:
            original_func = prompt_metadata["function"]
            description = prompt_metadata["description"]
            
            logger.debug(f"Bridging prompt: {prompt_name}")
            
            def create_prompt_wrapper(func, name):
                """Create a wrapper function that FastMCP can call"""
                async def prompt_wrapper(**kwargs):
                    try:
                        logger.debug(f"Executing prompt '{name}' with args: {kwargs}")
                        
                        # Execute the prompt function
                        if inspect.iscoroutinefunction(func):
                            result = await func(**kwargs)
                        else:
                            result = func(**kwargs)
                        
                        logger.debug(f"Prompt '{name}' executed successfully")
                        return result
                    
                    except Exception as e:
                        logger.error(f"Execution of prompt '{name}' failed: {e}", exc_info=True)
                        return {"success": False, "error": str(e), "error_type": type(e).__name__}
                
                return prompt_wrapper
            
            # Register the wrapper with FastMCP
            wrapped_prompt = create_prompt_wrapper(original_func, prompt_name)
            mcp_instance.prompt(name=prompt_name, description=description)(wrapped_prompt)
            
            bridged_count += 1
            logger.debug(f"Bridged prompt: {prompt_name}")
            
        except Exception as e:
            logger.error(f"Failed to bridge prompt '{prompt_name}' to FastMCP: {e}", exc_info=True)
    
    logger.info(f"Successfully bridged {bridged_count}/{len(PROMPT_REGISTRY)} prompts to the FastMCP interface")
    log_startup(f"Prompts bridged to FastMCP: {bridged_count}/{len(PROMPT_REGISTRY)} successful")


def create_mcp_server(config) -> FastMCP:
    """Create and configure the FastMCP server instance.

    Tools and prompts are dynamically bridged from the internal registries
    (TOOL_REGISTRY / PROMPT_REGISTRY).

    Args:
        config: NetBoxConfig instance (or compatible object) containing MCP settings.

    Returns:
        FastMCP: Configured MCP server instance.
    """
    log_startup("Initializing FastMCP server instance")

    # Create FastMCP instance - only pass name as positional argument
    # Note: Some FastMCP versions don't support description/stateless_http/json_response kwargs
    mcp_instance = FastMCP("NetBox Model-Context Protocol")

    # Add protocol logging after FastMCP initialization
    log_startup("Adding MCP protocol logging interceptor")
    add_mcp_protocol_logging(mcp_instance)

    # Bridge tools and prompts into FastMCP
    log_startup("Bridging tools to FastMCP interface")
    bridge_tools_to_fastmcp(mcp_instance)

    log_startup("Bridging prompts to FastMCP interface")
    bridge_prompts_to_fastmcp(mcp_instance)

    log_startup("FastMCP server instance created successfully")
    return mcp_instance

# === FASTAPI SELF-DESCRIBING ENDPOINTS ===

# Initialize FastAPI server for self-describing endpoints
api_app = FastAPI(
    title="NetBox MCP API",
    description="Self-describing REST API for NetBox Management & Control Plane",
    version="0.9.7"
)

# Pydantic models for API requests
class ExecutionRequest(BaseModel):
    tool_name: str
    parameters: Dict[str, Any] = {}

class ToolFilter(BaseModel):
    category: Optional[str] = None
    name_pattern: Optional[str] = None

@api_app.get("/api/v1/tools", response_model=List[Dict[str, Any]])
async def get_tools(
    category: Optional[str] = None,
    name_pattern: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Discovery endpoint: List all available MCP tools.

    Query Parameters:
        category: Filter tools by category (system, ipam, dcim, etc.)
        name_pattern: Filter tools by name pattern (partial match)

    Returns:
        List of tool metadata with parameters, descriptions, and categories
    """
    try:
        tools = serialize_registry_for_api()

        # Apply filters
        if category:
            tools = [tool for tool in tools if tool.get("category") == category]

        if name_pattern:
            tools = [tool for tool in tools if name_pattern.lower() in tool.get("name", "").lower()]

        logger.info(f"Tools discovery request: {len(tools)} tools returned (category={category}, pattern={name_pattern})")
        return tools

    except Exception as e:
        logger.error(f"Error in tools discovery: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@api_app.post("/api/v1/execute")
async def execute_mcp_tool(
    request: ExecutionRequest,
    client: NetBoxClient = Depends(get_netbox_client)
) -> Dict[str, Any]:
    """
    Generic execution endpoint: Execute any registered MCP tool.

    Request Body:
        tool_name: Name of the tool to execute
        parameters: Dictionary of tool parameters

    Returns:
        Tool execution result
    """
    try:
        logger.info(f"Executing tool: {request.tool_name} with parameters: {request.parameters}")

        # Execute tool with dependency injection
        result = execute_tool(request.tool_name, client, **request.parameters)

        return {
            "success": True,
            "tool_name": request.tool_name,
            "result": result
        }

    except ValueError as e:
        # Tool not found
        logger.warning(f"Tool not found: {request.tool_name}")
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        logger.error(f"Tool execution failed for {request.tool_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {str(e)}")


# === PROMPT ENDPOINTS ===

class PromptRequest(BaseModel):
    prompt_name: str
    arguments: Dict[str, Any] = {}

@api_app.get("/api/v1/prompts", response_model=List[Dict[str, Any]])
async def get_prompts() -> List[Dict[str, Any]]:
    """
    Discovery endpoint: List all available MCP prompts.

    Returns:
        List of prompt metadata with descriptions and usage information
    """
    try:
        prompts = serialize_prompts_for_api()
        logger.info(f"Prompts discovery request: {len(prompts)} prompts returned")
        return prompts

    except Exception as e:
        logger.error(f"Error in prompts discovery: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@api_app.post("/api/v1/prompts/execute")
async def execute_mcp_prompt(request: PromptRequest) -> Dict[str, Any]:
    """
    Generic prompt execution endpoint: Execute any registered MCP prompt.

    Request Body:
        prompt_name: Name of the prompt to execute
        arguments: Dictionary of prompt arguments (optional)

    Returns:
        Prompt execution result
    """
    try:
        logger.info(f"Executing prompt: {request.prompt_name} with arguments: {request.arguments}")

        # Execute prompt
        result = await execute_prompt(request.prompt_name, **request.arguments)

        return {
            "success": True,
            "prompt_name": request.prompt_name,
            "result": result
        }

    except ValueError as e:
        # Prompt not found
        logger.warning(f"Prompt not found: {request.prompt_name}")
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        logger.error(f"Prompt execution failed for {request.prompt_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Prompt execution failed: {str(e)}")


# === MONITORING ENDPOINTS ===

# Initialize monitoring components
performance_monitor = get_performance_monitor()
metrics_collector = MetricsCollector(performance_monitor)
health_check = HealthCheck(performance_monitor)
metrics_dashboard = MetricsDashboard(metrics_collector)

@api_app.get("/api/v1/metrics")
async def get_performance_metrics() -> Dict[str, Any]:
    """
    Get performance metrics and dashboard data.
    
    Returns:
        Complete performance metrics including operations, cache, and system stats
    """
    try:
        dashboard_data = metrics_dashboard.get_dashboard_data()
        return dashboard_data
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Metrics error: {str(e)}")


@api_app.get("/api/v1/health/detailed")
async def get_detailed_health() -> Dict[str, Any]:
    """
    Get detailed health status including performance metrics.
    
    Returns:
        Comprehensive health status with all checks and metrics
    """
    try:
        # Set NetBox client for health check
        health_check.netbox_client = get_netbox_client()
        
        # Get health status
        health_status = health_check.get_health_status()
        
        # Add active alerts
        alerts = metrics_dashboard.get_active_alerts()
        health_status["active_alerts"] = alerts
        
        return health_status
    except Exception as e:
        logger.error(f"Error getting detailed health: {e}")
        raise HTTPException(status_code=500, detail=f"Health check error: {str(e)}")


@api_app.get("/api/v1/metrics/operations/{operation_name}")
async def get_operation_metrics(operation_name: str) -> Dict[str, Any]:
    """
    Get metrics for a specific operation.
    
    Args:
        operation_name: Name of the operation to get metrics for
    
    Returns:
        Operation-specific metrics and statistics
    """
    try:
        # Get operation statistics
        stats = performance_monitor.get_operation_statistics(operation_name)
        
        if not stats or stats.get("total_operations", 0) == 0:
            raise HTTPException(status_code=404, detail=f"No metrics found for operation '{operation_name}'")
        
        # Get operation history
        history = performance_monitor.get_operation_history(operation_name)
        recent_history = history[-10:]  # Last 10 executions
        
        return {
            "operation_name": operation_name,
            "statistics": stats,
            "recent_history": [
                {
                    "timestamp": metric.timestamp.isoformat(),
                    "duration": metric.duration,
                    "success": metric.success,
                    "error_details": metric.error_details
                }
                for metric in recent_history
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting operation metrics for {operation_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Operation metrics error: {str(e)}")


@api_app.get("/api/v1/metrics/export")
async def export_metrics(format: str = "json") -> Dict[str, Any]:
    """
    Export all metrics data.
    
    Args:
        format: Export format (json or csv)
    
    Returns:
        Exported metrics data
    """
    try:
        if format.lower() == "csv":
            csv_data = metrics_dashboard.export_data(format="csv")
            return {
                "format": "csv",
                "data": csv_data,
                "content_type": "text/csv"
            }
        else:
            json_data = metrics_dashboard.export_data(format="json")
            return {
                "format": "json",
                "data": json_data,
                "content_type": "application/json"
            }
    except Exception as e:
        logger.error(f"Error exporting metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Metrics export error: {str(e)}")


# === API DOCUMENTATION ENDPOINTS ===

@api_app.get("/api/v1/openapi.json")
async def get_openapi_spec() -> Dict[str, Any]:
    """
    Get OpenAPI 3.0 specification for all NetBox MCP tools.
    
    Returns:
        OpenAPI specification as JSON
    """
    try:
        from .openapi_generator import OpenAPIConfig
        
        config = OpenAPIConfig(
            title="NetBox MCP Server API",
            description="Production-ready Model Context Protocol server for NetBox automation with 142+ enterprise-grade tools",
            version=get_cached_version(),
            server_url="http://localhost:8000"
        )
        
        generator = OpenAPIGenerator(config)
        spec = generator.generate_spec()
        
        return spec
    except Exception as e:
        logger.error(f"Error generating OpenAPI spec: {e}")
        raise HTTPException(status_code=500, detail=f"OpenAPI generation error: {str(e)}")


@api_app.get("/api/v1/openapi.yaml")
async def get_openapi_spec_yaml() -> str:
    """
    Get OpenAPI 3.0 specification as YAML.
    
    Returns:
        OpenAPI specification as YAML string
    """
    try:
        from .openapi_generator import OpenAPIConfig
        import yaml
        
        config = OpenAPIConfig(
            title="NetBox MCP Server API",
            description="Production-ready Model Context Protocol server for NetBox automation with 142+ enterprise-grade tools",
            version=get_cached_version(),
            server_url="http://localhost:8000"
        )
        
        generator = OpenAPIGenerator(config)
        spec = generator.generate_spec()
        
        yaml_content = yaml.dump(spec, default_flow_style=False, sort_keys=False)
        
        # Return as plain text with correct content type
        from fastapi import Response
        return Response(content=yaml_content, media_type="application/x-yaml")
    except Exception as e:
        logger.error(f"Error generating OpenAPI YAML: {e}")
        raise HTTPException(status_code=500, detail=f"OpenAPI YAML generation error: {str(e)}")


@api_app.get("/api/v1/postman")
async def get_postman_collection() -> Dict[str, Any]:
    """
    Get Postman collection for all NetBox MCP tools.
    
    Returns:
        Postman collection JSON
    """
    try:
        from .openapi_generator import OpenAPIConfig
        
        config = OpenAPIConfig(
            title="NetBox MCP Server API",
            version=get_cached_version(),
            server_url="http://localhost:8000"
        )
        
        generator = OpenAPIGenerator(config)
        collection = generator.generate_postman_collection()
        
        return collection
    except Exception as e:
        logger.error(f"Error generating Postman collection: {e}")
        raise HTTPException(status_code=500, detail=f"Postman collection error: {str(e)}")


# === CONTEXT MANAGEMENT ENDPOINTS ===

@api_app.get("/api/v1/context/status")
async def get_context_status(
    _client: NetBoxClient = Depends(get_netbox_client)
) -> Dict[str, Any]:
    """
    Get current auto-context status and configuration.
    
    Returns:
        Context status including environment detection and safety level
    """
    # Client parameter required by FastAPI dependency injection but not used in this endpoint
    _ = _client  # Suppress unused parameter warning
    
    try:
        from .persona import get_context_manager
        
        context_manager = get_context_manager()
        context_state = context_manager.get_context_state()
        
        if context_state:
            return {
                "context_initialized": True,
                "environment": context_state.environment,
                "safety_level": context_state.safety_level,
                "instance_type": context_state.instance_type,
                "initialization_time": context_state.initialization_time.isoformat(),
                "netbox_url": context_state.netbox_url,
                "netbox_version": context_state.netbox_version,
                "auto_context_enabled": context_state.auto_context_enabled,
                "user_preferences": context_state.user_preferences
            }
        else:
            return {
                "context_initialized": False,
                "auto_context_enabled": os.getenv('NETBOX_AUTO_CONTEXT', 'true').lower() == 'true',
                "environment_override": os.getenv('NETBOX_ENVIRONMENT'),
                "safety_level_override": os.getenv('NETBOX_SAFETY_LEVEL')
            }
            
    except Exception as e:
        logger.error(f"Error getting context status: {e}")
        raise HTTPException(status_code=500, detail=f"Context status error: {str(e)}")


@api_app.post("/api/v1/context/initialize")
async def initialize_context(
    client: NetBoxClient = Depends(get_netbox_client)
) -> Dict[str, Any]:
    """
    Manually initialize Bridget auto-context system.
    
    Returns:
        Context initialization result
    """
    try:
        from .persona import get_context_manager
        
        context_manager = get_context_manager()
        
        # Reset context if already initialized
        if context_manager.is_context_initialized():
            context_manager.reset_context()
        
        # Initialize context
        context_state = context_manager.initialize_context(client)
        context_message = context_manager.generate_context_message(context_state)
        
        return {
            "success": True,
            "message": "Context initialized successfully",
            "context": {
                "environment": context_state.environment,
                "safety_level": context_state.safety_level,
                "instance_type": context_state.instance_type,
                "initialization_time": context_state.initialization_time.isoformat()
            },
            "bridget_message": context_message
        }
        
    except Exception as e:
        logger.error(f"Error initializing context: {e}")
        raise HTTPException(status_code=500, detail=f"Context initialization failed: {str(e)}")


@api_app.post("/api/v1/context/reset")
async def reset_context() -> Dict[str, Any]:
    """
    Reset the auto-context system state.
    
    Returns:
        Reset operation result
    """
    try:
        from .registry import reset_context_state
        
        reset_context_state()
        
        return {
            "success": True,
            "message": "Context state reset successfully"
        }
        
    except Exception as e:
        logger.error(f"Error resetting context: {e}")
        raise HTTPException(status_code=500, detail=f"Context reset failed: {str(e)}")


@api_app.get("/api/v1/status")
async def get_system_status(
    client: NetBoxClient = Depends(get_netbox_client)
) -> Dict[str, Any]:
    """
    Health/Status endpoint: Get MCP system status and NetBox connectivity.

    Returns:
        System status including NetBox connection, tool registry stats, and performance metrics
    """
    try:
        # Get NetBox health status
        netbox_status = client.health_check()

        # Get tool registry statistics
        from .registry import get_registry_stats
        registry_stats = get_registry_stats()

        # Get client status
        from .dependencies import get_client_status
        client_status = get_client_status()

        return {
            "service": "NetBox MCP",
            "version": "0.9.7",
            "status": "healthy" if netbox_status.connected else "degraded",
            "netbox": {
                "connected": netbox_status.connected,
                "version": netbox_status.version,
                "python_version": netbox_status.python_version,
                "django_version": netbox_status.django_version,
                "response_time_ms": netbox_status.response_time_ms,
                "plugins": netbox_status.plugins
            },
            "tool_registry": registry_stats,
            "client": client_status,
            "cache_stats": netbox_status.cache_stats if hasattr(netbox_status, 'cache_stats') else None
        }

    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return {
            "service": "NetBox MCP",
            "version": "0.9.7",
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }

# === HTTP HEALTH CHECK SERVER ===

class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP handler for health check endpoints."""

    def do_GET(self):
        """Handle GET requests for health check endpoints."""
        try:
            if self.path in ['/health', '/healthz']:
                # Basic liveness check
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()

                response = {
                    "status": "OK",
                    "service": "netbox-mcp",
                    "version": "0.9.7"
                }
                self.wfile.write(json.dumps(response).encode())

            elif self.path == '/readyz':
                # Readiness check - test NetBox connection
                try:
                    status = NetBoxClientManager.get_client().health_check()
                    if status.connected:
                        self.send_response(200)
                        response = {
                            "status": "OK",
                            "netbox_connected": True,
                            "netbox_version": status.version,
                            "response_time_ms": status.response_time_ms
                        }
                    else:
                        self.send_response(503)
                        response = {
                            "status": "Service Unavailable",
                            "netbox_connected": False,
                            "error": status.error
                        }
                except Exception as e:
                    self.send_response(503)
                    response = {
                        "status": "Service Unavailable",
                        "netbox_connected": False,
                        "error": str(e)
                    }

                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())

            else:
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()

                response = {"error": "Not Found"}
                self.wfile.write(json.dumps(response).encode())

        except Exception as e:
            logger.error(f"Health check handler error: {e}")
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()

            response = {"error": "Internal Server Error", "details": str(e)}
            self.wfile.write(json.dumps(response).encode())

    def log_message(self, format, *args):
        """Override to use our logger."""
        logger.debug(f"Health check: {format % args}")


def start_health_server(port: int):
    """Start the HTTP health check server in a separate thread."""
    def run_server():
        try:
            server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
            logger.info(f"Health check server started on port {port}")
            logger.info(f"Health endpoints: /health, /healthz (liveness), /readyz (readiness)")
            server.serve_forever()
        except Exception as e:
            logger.error(f"Health check server failed: {e}")

    health_thread = threading.Thread(target=run_server, daemon=True)
    health_thread.start()


def initialize_server():
    """Initialize the NetBox MCP server with configuration and client."""
    try:
        # Load configuration
        config = load_config()
        logger.info(f"Configuration loaded successfully")

        # Update logging level
        logging.getLogger().setLevel(getattr(logging, config.log_level.upper()))
        logger.info(f"Log level set to {config.log_level}")

        # Log safety configuration
        if config.safety.dry_run_mode:
            logger.warning("🚨 NetBox MCP running in DRY-RUN mode - no actual writes will be performed")

        if not config.safety.enable_write_operations:
            logger.info("🔒 Write operations are DISABLED - server is read-only")

        # Initialize NetBox client using Gemini's singleton pattern
        NetBoxClientManager.initialize(config)
        logger.info("NetBox client initialized successfully via singleton manager")

        # Test connection (graceful degradation if NetBox is unavailable)
        client = NetBoxClientManager.get_client()
        try:
            status = client.health_check()
            if status.connected:
                logger.info(f"✅ Connected to NetBox {status.version} (response time: {status.response_time_ms:.1f}ms)")
            else:
                logger.warning(f"⚠️ NetBox connection degraded: {status.error}")
        except Exception as e:
            logger.warning(f"⚠️ NetBox connection failed during startup, running in degraded mode: {e}")
            # Continue startup - health server should still start for liveness probes

        # Async task system removed - using synchronous operations only
        logger.info("NetBox MCP server using synchronous operations")

        # Start health check server if enabled
        if config.enable_health_server:
            start_health_server(config.health_check_port)

        

        # Create MCP server instance (stdio or HTTP transport will be chosen in main())
        global mcp
        if mcp is None:
            mcp = create_mcp_server(config)
        else:
            logger.debug("FastMCP server instance already exists - skipping re-initialization")

        logger.info("NetBox MCP server initialization complete")


        return config
    except Exception as e:
        logger.error(f"Failed to initialize NetBox MCP server: {e}")
        raise



def main():
    """Main entry point for the NetBox MCP server."""
    try:
        log_startup("🚀 NetBox MCP Server MAIN() - Starting initialization")

        # Initialize server (loads config, initializes NetBox client, starts health server,
        # and creates the FastMCP instance)
        log_startup("Calling initialize_server()")
        config = initialize_server()
        log_startup("Server initialization completed successfully")

        # Ensure MCP instance was created
        if mcp is None:
            raise RuntimeError("FastMCP server instance was not initialized")

        # Normalize transport naming
        transport = (getattr(config, "mcp_transport", "stdio") or "stdio").strip().lower()
        if transport in {"streamable_http", "streamablehttp"}:
            transport = "streamable-http"
        if transport == "http":
            # Common alias used in some docs/clients
            transport = "streamable-http"

        # === STDIO transport (Claude Desktop / local subprocess model) ===
        if transport == "stdio":
            # Create shutdown event for graceful termination
            shutdown_event = threading.Event()

            # Signal handler for graceful shutdown
            def signal_handler(signum, frame):
                logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
                shutdown_event.set()

            # Register signal handlers for graceful shutdown
            signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
            signal.signal(signal.SIGTERM, signal_handler)  # Termination signal
            if hasattr(signal, 'SIGHUP'):
                signal.signal(signal.SIGHUP, signal_handler)   # Hangup signal (Unix)

            # Define the MCP server task to run in a thread
            def run_mcp_server():
                try:
                    log_startup("🔌 Starting MCP server thread with stdio transport")
                    logger.info("Starting NetBox MCP server on stdio transport...")
                    log_connection_event("MCP_THREAD_START", "stdio transport")

                    # 🛡️ ULTRATHINK FIX: Wrap in TaskGroup error protection
                    try:
                        mcp.run(transport="stdio")
                    except Exception as e:
                        # Handle TaskGroup and other MCP exceptions gracefully
                        if "TaskGroup" in str(e) or "unhandled errors" in str(e):
                            log_error(f"TaskGroup error captured and handled: {e}", e)
                            logger.warning(f"TaskGroup error handled gracefully - server continues: {e}")
                            # Don't crash on TaskGroup errors - let server restart naturally
                            time.sleep(2)  # Brief pause then exit gracefully for restart
                        else:
                            # Re-raise other exceptions
                            raise

                    log_connection_event("MCP_THREAD_EXIT", "stdio transport finished")
                except Exception as e:
                    log_error(f"MCP server thread error: {e}", e)
                    logger.error(f"MCP server thread encountered an error: {e}", exc_info=True)
                    shutdown_event.set()  # Trigger shutdown on MCP server error

            # Start the MCP server in a daemon thread
            log_startup("Creating MCP server daemon thread")
            mcp_thread = threading.Thread(target=run_mcp_server, daemon=True)
            mcp_thread.start()
            log_startup("MCP daemon thread started successfully")

            # Log startup information
            logger.info("NetBox MCP server is ready and listening (stdio transport)")
            if getattr(config, "enable_health_server", False):
                logger.info(f"Health endpoints: http://0.0.0.0:{config.health_check_port}/healthz")
            logger.info("Press Ctrl+C or send SIGTERM to gracefully shutdown")
            log_startup("🎯 SERVER READY - Waiting for MCP client connections")
            log_connection_event("SERVER_LISTENING", "Ready for MCP protocol connections")

            # Wait for shutdown signal
            try:
                while not shutdown_event.is_set():
                    if not mcp_thread.is_alive():
                        logger.warning("MCP server thread has stopped unexpectedly")
                        break
                    shutdown_event.wait(timeout=1.0)
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt...")
                shutdown_event.set()

            # Graceful shutdown
            logger.info("Shutting down NetBox MCP server gracefully...")

            # Give threads time to cleanup (max 5 seconds)
            mcp_thread.join(timeout=5.0)
            if mcp_thread.is_alive():
                logger.warning("MCP thread did not terminate within timeout")

            logger.info("NetBox MCP server shutdown complete")
            sys.exit(0)

        # === HTTP transports (Streamable HTTP / SSE) ===
        logger.info(f"Starting NetBox MCP server on {transport} transport...")
        mcp_host = getattr(config, "mcp_host", "0.0.0.0")
        mcp_port = getattr(config, "mcp_port", 8000)
        mcp_path = getattr(config, "mcp_path", "/mcp")
        
        mcp_url = f"http://{mcp_host}:{mcp_port}{mcp_path}"
        logger.info(f"MCP endpoint: {mcp_url}")
        if getattr(config, "enable_health_server", False):
            logger.info(f"Health endpoints: http://0.0.0.0:{config.health_check_port}/healthz")

        # Log MCP library version for debugging
        try:
            import mcp as mcp_module
            mcp_version = getattr(mcp_module, '__version__', 'unknown')
            logger.info(f"MCP library version: {mcp_version}")
        except Exception:
            logger.warning("Could not determine MCP library version")

        # For streamable-http transport, use the appropriate method based on MCP version
        import uvicorn
        
        asgi_app = None
        
        # Method 1: Try streamable_http_app() (MCP >= 1.9.0)
        if hasattr(mcp, 'streamable_http_app'):
            try:
                logger.info("Creating ASGI app with FastMCP.streamable_http_app()")
                asgi_app = mcp.streamable_http_app(path=mcp_path)
                logger.info(f"Streamable HTTP app created successfully at path: {mcp_path}")
            except TypeError:
                # Try without path argument
                asgi_app = mcp.streamable_http_app()
                logger.info("Streamable HTTP app created (without path argument)")
        
        # Method 2: Try http_app() (some MCP versions)
        if asgi_app is None and hasattr(mcp, 'http_app'):
            try:
                logger.info("Creating ASGI app with FastMCP.http_app()")
                asgi_app = mcp.http_app(path=mcp_path)
            except TypeError:
                asgi_app = mcp.http_app()
            logger.info("HTTP app created successfully")
        
        # Method 3: Try sse_app() as fallback
        if asgi_app is None and hasattr(mcp, 'sse_app'):
            try:
                logger.info("Creating ASGI app with FastMCP.sse_app() (fallback)")
                asgi_app = mcp.sse_app(path=mcp_path)
            except TypeError:
                asgi_app = mcp.sse_app()
            logger.info("SSE app created as fallback")
        
        # Method 4: Check for direct app attributes
        if asgi_app is None:
            for attr in ['asgi_app', 'app', '_app', '_asgi_app']:
                if hasattr(mcp, attr):
                    asgi_app = getattr(mcp, attr)
                    if callable(asgi_app) and not hasattr(asgi_app, '__call__'):
                        asgi_app = asgi_app()
                    logger.info(f"Using FastMCP.{attr} as ASGI app")
                    break
        
        # Start the server
        if asgi_app is not None:
            logger.info(f"🚀 Starting uvicorn server on {mcp_host}:{mcp_port}")
            logger.info(f"📡 MCP Streamable HTTP endpoint ready at: {mcp_url}")
            
            uvicorn.run(
                asgi_app,
                host=mcp_host,
                port=mcp_port,
                log_level="info",
                access_log=True
            )
        else:
            # Last resort: try mcp.run() with transport argument
            logger.warning("Could not create ASGI app, trying mcp.run() directly...")
            try:
                # Try with all parameters
                mcp.run(transport="streamable-http", host=mcp_host, port=mcp_port)
            except TypeError:
                try:
                    # Try with just transport
                    mcp.run(transport="streamable-http")
                except TypeError:
                    # Try without any arguments (stdio fallback)
                    logger.error("Failed to start HTTP transport, falling back to stdio")
                    mcp.run()

    except Exception as e:
        logger.error(f"NetBox MCP server error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
