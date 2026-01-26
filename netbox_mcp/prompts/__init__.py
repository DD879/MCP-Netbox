"""
NetBox MCP Prompts Module

This module contains MCP prompts that provide structured workflows and guidance
for complex NetBox operations. Prompts complement our 108+ tools by providing
intelligent orchestration and user guidance.

Includes auto-context detection and environment-specific safety guidance.
"""

from .workflows import *
from .context_prompts import *

__all__ = [
    'install_device_in_rack_prompt',
    'activate_bridget_prompt',
    'bridget_welcome_and_initialize_prompt',
    'bridget_environment_detected_prompt',
    'bridget_safety_guidance_prompt'
]