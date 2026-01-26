"""
Bridget Message Template System

This module provides sophisticated message formatting and template management
for Bridget's multi-language persona system, enabling consistent, context-aware
communication across different languages and environments.
"""

import logging
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
from enum import Enum

try:
    from .bridget_i18n import BridgetLocalizer
except ImportError:
    from bridget_i18n import BridgetLocalizer

logger = logging.getLogger(__name__)

class MessageType(Enum):
    """Types of messages that Bridget can generate."""
    WELCOME = "welcome"
    CONTEXT = "context"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    HELP = "help"
    WORKFLOW = "workflow"

class SafetyLevel(Enum):
    """Safety levels for message tone adaptation."""
    STANDARD = "standard"
    HIGH = "high"
    MAXIMUM = "maximum"

@dataclass
class MessageContext:
    """Context information for message generation."""
    environment: str
    safety_level: str
    instance_type: str
    netbox_url: str
    operation_type: Optional[str] = None
    resource_name: Optional[str] = None
    workflow_name: Optional[str] = None
    extra_params: Optional[Dict[str, Any]] = None

class BridgetMessageFormatter:
    """
    Advanced message formatting system for Bridget's persona.
    
    Provides context-aware message generation with environment-specific
    tone adaptation and safety-conscious communication patterns.
    """
    
    def __init__(self, localizer: BridgetLocalizer):
        """
        Initialize the message formatter.
        
        Args:
            localizer: BridgetLocalizer instance for language support
        """
        self.localizer = localizer
        self.message_cache = {}
    
    def format_welcome_message(self, context: MessageContext) -> str:
        """
        Generate complete welcome message with environment detection.
        
        Args:
            context: Message context with environment details
            
        Returns:
            Formatted welcome message
        """
        
        try:
            # Get base message components
            welcome = self.localizer.get_message("welcome")
            intro = self.localizer.get_message("intro")
            
            # Environment detection
            env_detected = self.localizer.get_message(
                f"environment_detected.{context.environment}"
            )
            
            # Environment details with URL and type
            env_details = self.localizer.get_message(
                f"environment_details.{context.environment}",
                netbox_url=context.netbox_url,
                instance_type=context.instance_type
            )
            
            # Safety guidance
            safety_guidance = self.localizer.get_message(
                f"safety_guidance.{context.safety_level}"
            )
            
            # Context completion
            context_complete = self.localizer.get_message("context_complete")
            
            # Build message structure
            message_parts = [
                welcome,
                intro,
                "",  # Spacing
                env_detected,
                env_details,
                "",  # Spacing
                safety_guidance,
                "",  # Spacing
                context_complete,
                "",  # Spacing
                "---",
                self.localizer.get_message("signature")
            ]
            
            return "\n".join(message_parts)
            
        except Exception as e:
            logger.error(f"Failed to format welcome message: {e}")
            return self._get_fallback_welcome(context)
    
    def format_operation_message(self, 
                                operation_type: str, 
                                context: MessageContext,
                                message_type: MessageType = MessageType.SUCCESS) -> str:
        """
        Format operation-specific messages (success, warning, error).
        
        Args:
            operation_type: Type of operation (create, update, delete, etc.)
            context: Message context
            message_type: Type of message to generate
            
        Returns:
            Formatted operation message
        """
        
        try:
            # Get base message based on type
            if message_type == MessageType.SUCCESS:
                base_message = self.localizer.get_message(
                    f"success.resource_{operation_type}",
                    resource_name=context.resource_name or "resource"
                )
            elif message_type == MessageType.WARNING:
                base_message = self._format_warning_message(operation_type, context)
            elif message_type == MessageType.ERROR:
                base_message = self.localizer.get_message(
                    "errors.operation_failed",
                    error_message=context.extra_params.get("error", "Unknown error")
                )
            else:
                base_message = "Operation completed"
            
            # Add environment-specific context if needed
            if context.environment == "production" and message_type == MessageType.WARNING:
                production_warning = self.localizer.get_message(
                    f"warnings.production.{operation_type}_operation"
                )
                base_message = f"{production_warning}\n\n{base_message}"
            
            return base_message
            
        except Exception as e:
            logger.error(f"Failed to format operation message: {e}")
            return f"Operation {operation_type} - {message_type.value}"
    
    def format_workflow_message(self, 
                               workflow_name: str, 
                               context: MessageContext,
                               step_number: Optional[int] = None,
                               total_steps: Optional[int] = None) -> str:
        """
        Format workflow guidance messages.
        
        Args:
            workflow_name: Name of the workflow
            context: Message context
            step_number: Current step (optional)
            total_steps: Total number of steps (optional)
            
        Returns:
            Formatted workflow message
        """
        
        try:
            # Get workflow-specific message
            workflow_msg = self.localizer.get_message(
                f"workflows.{workflow_name}"
            )
            
            # Add step information if provided
            if step_number and total_steps:
                step_info = f"**Step {step_number} of {total_steps}**"
                workflow_msg = f"{step_info}\n{workflow_msg}"
            
            # Add environment-specific guidance
            if context.environment in ["production", "staging"]:
                safety_reminder = self.localizer.get_message("operations.dry_run_recommended")
                workflow_msg = f"{workflow_msg}\n\n{safety_reminder}"
            
            return workflow_msg
            
        except Exception as e:
            logger.error(f"Failed to format workflow message: {e}")
            return f"Workflow: {workflow_name}"
    
    def format_help_message(self, 
                           help_topic: Optional[str] = None,
                           context: Optional[MessageContext] = None) -> str:
        """
        Format help and guidance messages.
        
        Args:
            help_topic: Specific help topic (optional)
            context: Message context (optional)
            
        Returns:
            Formatted help message
        """
        
        try:
            if help_topic:
                help_msg = self.localizer.get_message(f"help.{help_topic}")
            else:
                # General help
                help_parts = [
                    self.localizer.get_message("help.getting_started"),
                    self.localizer.get_message("help.safety_first"),
                    self.localizer.get_message("help.need_help")
                ]
                
                # Add environment-specific help
                if context and context.environment == "demo":
                    help_parts.append(self.localizer.get_message("warnings.demo.learning_mode"))
                
                help_msg = "\n\n".join(help_parts)
            
            return f"🦜 **Bridget's Help**\n\n{help_msg}"
            
        except Exception as e:
            logger.error(f"Failed to format help message: {e}")
            return "🦜 Help is available! Ask me about specific workflows."
    
    def format_safety_warning(self, 
                             operation_type: str,
                             context: MessageContext,
                             severity: str = "high") -> str:
        """
        Format safety warnings based on environment and operation.
        
        Args:
            operation_type: Type of operation
            context: Message context
            severity: Warning severity (low, medium, high, critical)
            
        Returns:
            Formatted safety warning
        """
        
        try:
            # Get environment-specific warning
            if context.environment == "production":
                warning_key = f"warnings.production.{operation_type}_operation"
            elif context.environment == "staging":
                warning_key = "warnings.staging.validation_needed"
            else:
                # Default warning
                warning_key = f"operations.{operation_type}_recommended"
            
            warning_msg = self.localizer.get_message(warning_key)
            
            # Add severity indicator
            severity_icons = {
                "low": "💡",
                "medium": "⚠️", 
                "high": "🚨",
                "critical": "🔥"
            }
            
            icon = severity_icons.get(severity, "⚠️")
            return f"{icon} {warning_msg}"
            
        except Exception as e:
            logger.error(f"Failed to format safety warning: {e}")
            return f"⚠️ Please use caution with {operation_type} operations"
    
    def _format_warning_message(self, operation_type: str, context: MessageContext) -> str:
        """Format operation-specific warning messages."""
        
        # Check if this is a bulk operation
        if context.extra_params and context.extra_params.get("bulk_operation"):
            if context.environment == "production":
                return self.localizer.get_message("warnings.production.bulk_operation")
        
        # Check if operation is irreversible
        if operation_type == "delete":
            if context.environment == "production":
                return self.localizer.get_message("warnings.production.irreversible")
        
        # Default operation warning
        return self.localizer.get_message("operations.confirm_required")
    
    def _get_fallback_welcome(self, context: MessageContext) -> str:
        """Generate fallback welcome message when localization fails."""
        
        return f"""🦜 **Bridget here!**

Environment: {context.environment}
Safety Level: {context.safety_level}
URL: {context.netbox_url}

I'm ready to help with your NetBox infrastructure!

---
*Bridget - NetBox Infrastructure Guide*"""


class BridgetTemplateManager:
    """
    High-level template management for Bridget's messaging system.
    
    Provides simplified interface for generating consistent, context-aware
    messages across the entire NetBox MCP system.
    """
    
    def __init__(self, language: str = 'auto'):
        """
        Initialize the template manager.
        
        Args:
            language: Language preference ('nl', 'en', or 'auto')
        """
        self.localizer = BridgetLocalizer(language=language)
        self.formatter = BridgetMessageFormatter(self.localizer)
        
        logger.info(f"Bridget template manager initialized: {self.localizer.current_language}")
    
    def create_context(self, 
                      environment: str,
                      safety_level: str, 
                      netbox_url: str,
                      instance_type: str = "self-hosted",
                      **kwargs) -> MessageContext:
        """
        Create message context for template generation.
        
        Args:
            environment: Environment type (demo/staging/production/cloud)
            safety_level: Safety level (standard/high/maximum)
            netbox_url: NetBox instance URL
            instance_type: Instance type (self-hosted/cloud-hosted)
            **kwargs: Additional context parameters
            
        Returns:
            MessageContext instance
        """
        
        return MessageContext(
            environment=environment,
            safety_level=safety_level,
            instance_type=instance_type,
            netbox_url=netbox_url,
            extra_params=kwargs
        )
    
    def welcome_message(self, context: MessageContext) -> str:
        """Generate welcome message."""
        return self.formatter.format_welcome_message(context)
    
    def success_message(self, operation_type: str, context: MessageContext) -> str:
        """Generate success message."""
        return self.formatter.format_operation_message(
            operation_type, context, MessageType.SUCCESS
        )
    
    def warning_message(self, operation_type: str, context: MessageContext) -> str:
        """Generate warning message."""
        return self.formatter.format_operation_message(
            operation_type, context, MessageType.WARNING
        )
    
    def error_message(self, operation_type: str, context: MessageContext) -> str:
        """Generate error message."""
        return self.formatter.format_operation_message(
            operation_type, context, MessageType.ERROR
        )
    
    def workflow_message(self, workflow_name: str, context: MessageContext, **kwargs) -> str:
        """Generate workflow message."""
        return self.formatter.format_workflow_message(workflow_name, context, **kwargs)
    
    def help_message(self, help_topic: Optional[str] = None, context: Optional[MessageContext] = None) -> str:
        """Generate help message."""
        return self.formatter.format_help_message(help_topic, context)
    
    def safety_warning(self, operation_type: str, context: MessageContext, severity: str = "high") -> str:
        """Generate safety warning."""
        return self.formatter.format_safety_warning(operation_type, context, severity)
    
    def set_language(self, language: str):
        """Change current language."""
        self.localizer.set_language(language)
        logger.info(f"Template manager language changed to: {self.localizer.current_language}")
    
    def get_current_language(self) -> str:
        """Get current language code."""
        return self.localizer.current_language


# Global template manager instance
_global_template_manager: Optional[BridgetTemplateManager] = None

def get_template_manager(language: str = 'auto') -> BridgetTemplateManager:
    """
    Get global Bridget template manager instance.
    
    Args:
        language: Language preference ('nl', 'en', or 'auto')
        
    Returns:
        BridgetTemplateManager instance
    """
    global _global_template_manager
    
    if _global_template_manager is None:
        _global_template_manager = BridgetTemplateManager(language=language)
    elif language != 'auto' and _global_template_manager.get_current_language() != language:
        _global_template_manager.set_language(language)
    
    return _global_template_manager