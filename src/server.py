#!/usr/bin/env python3
"""
NetBox MCP Server

A Model Context Protocol server for safe read/write access to NetBox instances.
Provides tools for querying and managing NetBox data with comprehensive safety controls.

Version: 0.9.7 - Hierarchical Architecture with Registry Bridge
"""

from mcp.server.fastmcp import FastMCP
from .client import NetBoxClient
from .config import load_config
from .registry import (
    TOOL_REGISTRY, PROMPT_REGISTRY, 
    load_tools, load_prompts
)
from .dependencies import NetBoxClientManager  # Singleton pattern for client management
from .monitoring import get_performance_monitor
from .tool_profiles import get_profile_manager, TOOL_PROFILES  # Dynamic tool profiles
# OpenAPI generation available via MCP tools
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
from typing import Dict, List, Optional, Any, Union, get_origin, get_args

# Configure logging (will be updated from config)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def simplify_type_annotation(annotation) -> type:
    """
    Simplify complex type annotations to basic types for Google Gemini compatibility.
    
    Google Gemini's function calling API doesn't support JSON Schema with:
    - Type arrays like ["string", "null"] 
    - anyOf/oneOf constructs
    - Complex nested types
    
    This function converts:
    - Optional[X] -> X
    - Union[X, None] -> X
    - List[X] -> list
    - Dict[X, Y] -> dict
    
    Args:
        annotation: The type annotation to simplify
        
    Returns:
        A simplified basic Python type
    """
    if annotation is None or annotation is type(None):
        return str  # Default to string for None types
    
    origin = get_origin(annotation)
    
    # Handle Optional[X] which is Union[X, None]
    if origin is Union:
        args = get_args(annotation)
        # Filter out NoneType
        non_none_args = [arg for arg in args if arg is not type(None)]
        if non_none_args:
            # Recursively simplify the first non-None type
            return simplify_type_annotation(non_none_args[0])
        return str  # Fallback
    
    # Handle List[X] -> list
    if origin is list:
        return list
    
    # Handle Dict[X, Y] -> dict  
    if origin is dict:
        return dict
    
    # Handle basic types
    if annotation in (str, int, float, bool, list, dict):
        return annotation
    
    # Handle string representations
    if isinstance(annotation, str):
        type_map = {
            'str': str,
            'int': int,
            'float': float,
            'bool': bool,
            'list': list,
            'dict': dict,
            'List': list,
            'Dict': dict,
        }
        return type_map.get(annotation, str)
    
    # Default: return the annotation as-is if it's a basic type
    try:
        if isinstance(annotation, type):
            return annotation
    except TypeError:
        pass
    
    return str  # Ultimate fallback


def create_simplified_signature(func):
    """
    Create a new function signature with simplified type annotations.
    
    This ensures that when FastMCP generates JSON schemas for Google Gemini,
    the schemas use simple types like "string" instead of ["string", "null"].
    
    Args:
        func: The original function
        
    Returns:
        A new Parameter list with simplified annotations
    """
    sig = inspect.signature(func)
    new_params = []
    
    for param_name, param in sig.parameters.items():
        if param_name == 'client':
            continue  # Skip client parameter (injected)
        
        # Simplify the annotation
        new_annotation = simplify_type_annotation(param.annotation)
        
        # Create new parameter with simplified type
        new_param = param.replace(annotation=new_annotation)
        new_params.append(new_param)
    
    return new_params


class HostOverrideMiddleware:
    """ASGI Middleware to override Host header for DNS rebinding protection bypass.
    
    This middleware modifies the Host header to a value that matches the
    server's allowed hosts list, effectively bypassing DNS rebinding protection
    when running behind proxies or in Docker with custom hostnames.
    """
    
    def __init__(self, app, target_host: str = "127.0.0.1:8000"):
        self.app = app
        self.target_host = target_host
        
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Get the original host for logging
            headers = dict(scope.get("headers", []))
            original_host = headers.get(b"host", b"unknown").decode("utf-8", errors="replace")
            
            # Override Host header to bypass DNS rebinding protection
            new_headers = []
            for name, value in scope.get("headers", []):
                if name == b"host":
                    new_headers.append((b"host", self.target_host.encode("utf-8")))
                else:
                    new_headers.append((name, value))
            
            # Create new scope with modified headers
            scope = dict(scope)
            scope["headers"] = new_headers
            
            logger.debug(f"Host header override: {original_host} -> {self.target_host}")
        
        await self.app(scope, receive, send)


class DebugMiddleware:
    """ASGI Middleware to log all incoming requests for debugging 404 issues."""
    
    def __init__(self, app):
        self.app = app
        
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            method = scope.get("method", "?")
            path = scope.get("path", "?")
            logger.info(f"🔍 DEBUG: Incoming {method} {path}")
            
            # Log headers for debugging
            headers = dict(scope.get("headers", []))
            content_type = headers.get(b"content-type", b"none").decode("utf-8", errors="replace")
            accept = headers.get(b"accept", b"none").decode("utf-8", errors="replace")
            logger.debug(f"🔍 Headers: Content-Type={content_type}, Accept={accept}")
            
            # If it's a GET request to /mcp, return helpful info instead of 404
            if method == "GET" and path in ("/mcp", "/mcp/"):
                # Return helpful response for GET requests (not proper MCP protocol)
                response_body = json.dumps({
                    "error": "MCP Streamable HTTP requires POST requests",
                    "help": {
                        "protocol": "MCP Streamable HTTP",
                        "method": "POST",
                        "content_type": "application/json",
                        "accept": "application/json, text/event-stream",
                        "body": "JSON-RPC 2.0 message",
                        "docs": "https://modelcontextprotocol.io/docs/concepts/transports"
                    }
                }, indent=2).encode("utf-8")
                
                await send({
                    "type": "http.response.start",
                    "status": 405,  # Method Not Allowed
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(response_body)).encode()),
                        (b"allow", b"POST"),
                    ]
                })
                await send({
                    "type": "http.response.body",
                    "body": response_body,
                })
                return
        
        await self.app(scope, receive, send)

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
def bridge_tools_to_fastmcp(mcp_instance: FastMCP, use_profiles: bool = True):
    """
    Dynamically registers tools from our internal TOOL_REGISTRY
    with the FastMCP instance, creating wrappers for dependency injection.
    
    IMPORTANT: This function:
    1. Simplifies type annotations for Google Gemini/Ollama compatibility
    2. Filters tools based on active profile (for smaller LLMs)
    3. Always includes meta-tools for profile management
    
    Args:
        mcp_instance: The FastMCP server instance
        use_profiles: If True, filter tools based on active profile (default: True)
    """
    # Initialize profile manager with full registry
    profile_manager = get_profile_manager()
    profile_manager.set_tool_registry(TOOL_REGISTRY)
    
    # Get initial profile from environment or config
    initial_profile = os.getenv("NETBOX_TOOL_PROFILE", "essential")
    if initial_profile not in TOOL_PROFILES:
        logger.warning(f"Unknown profile '{initial_profile}', using 'essential'")
        initial_profile = "essential"
    
    # Activate initial profile
    profile_manager.activate_profile(initial_profile)
    
    # Get filtered registry based on profile
    if use_profiles:
        tools_to_bridge = profile_manager.get_filtered_registry()
        logger.info(f"Using profile '{initial_profile}': {len(tools_to_bridge)}/{len(TOOL_REGISTRY)} tools")
    else:
        tools_to_bridge = TOOL_REGISTRY
        logger.info(f"Profiles disabled: bridging all {len(TOOL_REGISTRY)} tools")
    
    bridged_count = 0
    for tool_name, tool_metadata in tools_to_bridge.items():
        try:
            original_func = tool_metadata["function"]
            description = tool_metadata.get("description", f"Executes the {tool_name} tool.")
            category = tool_metadata.get("category", "General")

            # Create a 'wrapper' that injects the client with SIMPLIFIED type annotations
            def create_tool_wrapper(original_func):
                """
                Creates a tool wrapper that:
                1. Mimics the exact signature of the original function
                2. Automatically injects the NetBox client
                3. Prevents argument duplicates
                4. Uses SIMPLIFIED type annotations for Google Gemini compatibility
                """
                sig = inspect.signature(original_func)
                
                # Create simplified parameters (excluding 'client', with simplified types)
                wrapper_params = []
                for p in sig.parameters.values():
                    if p.name == 'client':
                        continue
                    # Simplify the type annotation for Gemini compatibility
                    simplified_type = simplify_type_annotation(p.annotation)
                    new_param = p.replace(annotation=simplified_type)
                    wrapper_params.append(new_param)

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

                            client = NetBoxClientManager.get_client()

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

    # Log summary with profile info
    active_profile = profile_manager.get_active_profile()
    logger.info(f"Successfully bridged {bridged_count}/{len(tools_to_bridge)} tools (profile: {active_profile})")
    log_startup(f"Tools bridged to FastMCP: {bridged_count} tools, profile: {active_profile}")
    
    # Log hint about profile management
    if use_profiles and active_profile != "full":
        logger.info(f"💡 Tip: Use netbox_profile_activate() to switch profiles or netbox_profile_list() to see all profiles")

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
    # Use profile filtering if enabled in config
    use_profiles = getattr(config, 'enable_tool_profiles', True)
    log_startup(f"Bridging tools to FastMCP interface (profiles: {'enabled' if use_profiles else 'disabled'})")
    bridge_tools_to_fastmcp(mcp_instance, use_profiles=use_profiles)

    log_startup("Bridging prompts to FastMCP interface")
    bridge_prompts_to_fastmcp(mcp_instance)

    log_startup("FastMCP server instance created successfully")
    return mcp_instance


# === HTTP HEALTH CHECK SERVER ===
# Note: FastAPI REST endpoints were removed - all functionality is exposed via MCP protocol
# n8n and other MCP clients should use tools/list, tools/call, prompts/list, etc.

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
                # Try with streamable_http_path (correct parameter name)
                try:
                    asgi_app = mcp.streamable_http_app(streamable_http_path=mcp_path)
                    logger.info(f"Streamable HTTP app created with streamable_http_path: {mcp_path}")
                except TypeError:
                    # Fallback: try with path (older API)
                    try:
                        asgi_app = mcp.streamable_http_app(path=mcp_path)
                        logger.info(f"Streamable HTTP app created with path: {mcp_path}")
                    except TypeError:
                        # Last resort: no arguments
                        asgi_app = mcp.streamable_http_app()
                        logger.info("Streamable HTTP app created (no arguments) - endpoint will be at /mcp")
            except Exception as e:
                logger.warning(f"streamable_http_app() failed: {e}")
        
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
            # Apply DebugMiddleware to log all incoming requests
            logger.info("Applying DebugMiddleware for request logging")
            asgi_app = DebugMiddleware(asgi_app)
            
            # Apply HostOverrideMiddleware if we're binding to 0.0.0.0 (Docker/remote scenario)
            # This bypasses DNS rebinding protection by rewriting Host header to localhost
            if mcp_host == "0.0.0.0":
                target_host = f"127.0.0.1:{mcp_port}"
                logger.info(f"Applying HostOverrideMiddleware: rewriting Host headers to {target_host}")
                asgi_app = HostOverrideMiddleware(asgi_app, target_host=target_host)
            
            # Log helpful debugging info about MCP paths
            logger.info("=" * 60)
            logger.info("MCP SERVER CONFIGURATION:")
            logger.info(f"  Host: {mcp_host}")
            logger.info(f"  Port: {mcp_port}")
            logger.info(f"  Path: {mcp_path}")
            logger.info(f"  Full URL: {mcp_url}")
            logger.info("MCP PROTOCOL INFO:")
            logger.info("  - POST /mcp → Send JSON-RPC messages")
            logger.info("  - GET /mcp → SSE stream (requires Accept: text/event-stream)")
            logger.info("  - GET /mcp is NOT supported for simple HTTP clients")
            logger.info("=" * 60)
            
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
