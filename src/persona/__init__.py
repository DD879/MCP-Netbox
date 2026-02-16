"""
NetBox MCP Persona Module

Provides personality and context for interactive workflows through our mascotte Bridget.
Creates clear branding and user guidance for NetBox MCP prompt interactions.
Includes auto-context detection and safety level management.
"""

from .bridget import (
    BridgetPersona,
    get_bridget_introduction,
    get_bridget_workflow_header,
    get_bridget_step_transition,
    get_bridget_completion_message,
)
from .bridget_context import (
    BridgetContextManager,
    ContextState,
    get_context_manager,
    auto_initialize_bridget_context,
    merge_context_with_result
)

__all__ = [
    'get_bridget_introduction',
    'get_bridget_workflow_header', 
    'get_bridget_step_transition',
    'get_bridget_completion_message',
    'BridgetPersona',
    'BridgetContextManager',
    'ContextState',
    'get_context_manager',
    'auto_initialize_bridget_context',
    'merge_context_with_result'
]