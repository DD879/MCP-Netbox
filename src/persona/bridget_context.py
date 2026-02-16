"""
Bridget Auto-Context System - Context Manager Implementation

Provides automatic environment detection and safety level assignment
for Bridget persona in NetBox MCP interactions.
"""

import os
import re
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse

from .bridget_i18n import get_localizer
from .message_templates import get_template_manager, MessageContext

logger = logging.getLogger(__name__)


@dataclass
class ContextState:
    """Represents the current context state for a NetBox MCP session."""
    environment: str
    safety_level: str
    instance_type: str
    initialization_time: datetime
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    netbox_url: Optional[str] = None
    netbox_version: Optional[str] = None
    auto_context_enabled: bool = True


class BridgetContextManager:
    """
    Manages automatic context detection and initialization for Bridget persona.
    
    Provides intelligent environment detection, safety level assignment,
    and context-appropriate messaging for NetBox MCP interactions.
    """
    
    def __init__(self):
        self._context_state: Optional[ContextState] = None
        self._initialization_lock = False
        self._template_manager = None
        self._localizer = None
        
    def detect_environment(self, client) -> str:
        """
        Detect the NetBox environment based on URL patterns and metadata.
        
        Args:
            client: NetBoxClient instance for API access
            
        Returns:
            Environment type: 'demo', 'staging', 'production', 'cloud', or 'unknown'
        """
        try:
            # Check environment variable override first
            env_override = os.getenv('NETBOX_ENVIRONMENT')
            if env_override and env_override.lower() in ['demo', 'staging', 'production', 'cloud']:
                logger.info(f"Environment overridden via NETBOX_ENVIRONMENT: {env_override}")
                return env_override.lower()
            
            # Get NetBox URL from client configuration
            netbox_url = getattr(client, 'url', None) or os.getenv('NETBOX_URL', '')
            
            if not netbox_url:
                logger.warning("No NetBox URL available for environment detection")
                return 'unknown'
            
            # Parse URL for pattern matching
            parsed_url = urlparse(netbox_url)
            hostname = parsed_url.hostname or ''
            full_url = netbox_url.lower()
            
            logger.debug(f"Analyzing NetBox URL for environment detection: {hostname}")
            
            # Environment detection patterns
            detection_patterns = {
                'demo': [
                    r'demo\..*',
                    r'.*demo.*',
                    r'localhost',
                    r'127\.0\.0\.1',
                    r'.*\.local'
                ],
                'staging': [
                    r'stag.*\..*',
                    r'.*staging.*',
                    r'.*test.*',
                    r'.*dev.*'
                ],
                'cloud': [
                    r'.*\.cloud\.netboxapp\.com',
                    r'.*cloud\.netbox.*'
                ],
                'production': [
                    r'.*\.prod.*',
                    r'.*production.*',
                    r'netbox\..*'
                ]
            }
            
            # Check patterns in order of specificity
            for env_type, patterns in detection_patterns.items():
                for pattern in patterns:
                    if re.match(pattern, hostname) or re.search(pattern, full_url):
                        logger.info(f"Environment detected as '{env_type}' based on URL pattern: {pattern}")
                        return env_type
            
            # Additional checks for cloud instances
            if 'cloud.netboxapp.com' in full_url:
                return 'cloud'
                
            # Check for specific demo/test keywords in URL
            demo_keywords = ['demo', 'test', 'dev', 'sandbox', 'trial']
            for keyword in demo_keywords:
                if keyword in full_url:
                    logger.info(f"Environment detected as 'demo' based on keyword: {keyword}")
                    return 'demo'
            
            # Default to production for safety (highest security level)
            logger.warning(f"Could not determine environment from URL: {hostname}. Defaulting to 'production' for safety.")
            return 'production'
            
        except Exception as e:
            logger.error(f"Error during environment detection: {e}")
            return 'unknown'
    
    def detect_safety_level(self, environment: str) -> str:
        """
        Determine appropriate safety level based on environment.
        
        Args:
            environment: Detected environment type
            
        Returns:
            Safety level: 'standard', 'high', or 'maximum'
        """
        # Check for safety level override
        safety_override = os.getenv('NETBOX_SAFETY_LEVEL')
        if safety_override and safety_override.lower() in ['standard', 'high', 'maximum']:
            logger.info(f"Safety level overridden via NETBOX_SAFETY_LEVEL: {safety_override}")
            return safety_override.lower()
        
        # Safety level mapping based on environment
        safety_mapping = {
            'demo': 'standard',
            'staging': 'high', 
            'cloud': 'high',
            'production': 'maximum',
            'unknown': 'maximum'  # Safe default
        }
        
        safety_level = safety_mapping.get(environment, 'maximum')
        logger.info(f"Safety level assigned: {safety_level} for environment: {environment}")
        
        return safety_level
    
    def detect_instance_type(self, client) -> str:
        """
        Detect the type of NetBox instance (cloud, self-hosted, etc.).
        
        Args:
            client: NetBoxClient instance for API access
            
        Returns:
            Instance type: 'cloud', 'self-hosted', or 'unknown'
        """
        try:
            netbox_url = getattr(client, 'url', None) or os.getenv('NETBOX_URL', '')
            
            if 'cloud.netboxapp.com' in netbox_url:
                return 'cloud'
            elif any(domain in netbox_url for domain in ['localhost', '127.0.0.1', '192.168.', '10.', '172.']):
                return 'self-hosted'
            else:
                return 'self-hosted'  # Assume self-hosted if not clearly cloud
                
        except Exception as e:
            logger.warning(f"Could not detect instance type: {e}")
            return 'unknown'
    
    def generate_context_message(self, context_state: ContextState) -> str:
        """
        Generate a Bridget persona context message based on detected environment.
        
        Args:
            context_state: Current context state
            
        Returns:
            Formatted context message string
        """
        try:
            # Initialize i18n components if not already done
            if self._template_manager is None:
                self._template_manager = get_template_manager()
                self._localizer = get_localizer()
            
            # Create message context for template generation
            message_context = MessageContext(
                environment=context_state.environment,
                safety_level=context_state.safety_level,
                instance_type=context_state.instance_type,
                netbox_url=context_state.netbox_url or "Unknown",
                extra_params={
                    'initialization_time': context_state.initialization_time.strftime('%H:%M:%S')
                }
            )
            
            # Generate localized welcome message
            welcome_message = self._template_manager.welcome_message(message_context)
            
            return welcome_message
            
        except Exception as e:
            logger.error(f"Error generating context message: {e}")
            return self._get_fallback_context_message()
    
    
    def _get_fallback_context_message(self) -> str:
        """Get a safe fallback context message if generation fails."""
        try:
            # Try to use localized fallback message
            if self._localizer is None:
                self._localizer = get_localizer()
            
            fallback_message = self._localizer.get_message("welcome")
            
            # Create basic context information
            fallback_context = """

🛡️ **MAXIMUM SAFETY ACTIVE**
📋 **Recommendation:** Always use dry-run mode first

*Bridget - NetBox Infrastructure Guide*"""
            
            return f"{fallback_message}{fallback_context}"
            
        except Exception:
            # Ultimate fallback in case i18n system fails
            return """🦜 **Bridget Context System - Safe Mode**

A problem occurred while detecting your environment.
Maximum safety protocols are activated.

🛡️ **Active:** All operations require explicit confirmation
📋 **Recommendation:** Always use dry-run mode first

*Bridget - NetBox Infrastructure Guide*"""
    
    def initialize_context(self, client) -> ContextState:
        """
        Initialize context for the current session.
        
        Args:
            client: NetBoxClient instance for environment detection
            
        Returns:
            Initialized ContextState object
        """
        if self._initialization_lock:
            logger.warning("Context initialization already in progress")
            return self._context_state
            
        self._initialization_lock = True
        
        try:
            logger.info("Initializing Bridget auto-context system...")
            
            # Check if auto-context is enabled
            auto_context = os.getenv('NETBOX_AUTO_CONTEXT', 'true').lower() == 'true'
            
            # Detect environment and safety level
            environment = self.detect_environment(client)
            safety_level = self.detect_safety_level(environment)
            instance_type = self.detect_instance_type(client)
            
            # Get NetBox version if available
            netbox_version = None
            netbox_url = getattr(client, 'url', None)
            
            try:
                status = client.health_check()
                if hasattr(status, 'version'):
                    netbox_version = status.version
            except Exception as e:
                logger.warning(f"Could not retrieve NetBox version: {e}")
            
            # Create context state
            self._context_state = ContextState(
                environment=environment,
                safety_level=safety_level,
                instance_type=instance_type,
                initialization_time=datetime.now(),
                netbox_url=netbox_url,
                netbox_version=netbox_version,
                auto_context_enabled=auto_context
            )
            
            logger.info(f"Context initialized: {environment}/{safety_level}/{instance_type}")
            return self._context_state
            
        except Exception as e:
            logger.error(f"Context initialization failed: {e}")
            # Create safe fallback context
            self._context_state = ContextState(
                environment='unknown',
                safety_level='maximum',
                instance_type='unknown',
                initialization_time=datetime.now(),
                auto_context_enabled=True
            )
            return self._context_state
            
        finally:
            self._initialization_lock = False
    
    def is_context_initialized(self) -> bool:
        """Check if context has been initialized for current session."""
        return self._context_state is not None
    
    def get_context_state(self) -> Optional[ContextState]:
        """Get current context state."""
        return self._context_state
    
    def update_user_preferences(self, preferences: Dict[str, Any]) -> None:
        """Update user preferences in current context."""
        if self._context_state:
            self._context_state.user_preferences.update(preferences)
            logger.info(f"User preferences updated: {list(preferences.keys())}")
    
    def reset_context(self) -> None:
        """Reset context state (useful for testing or session changes)."""
        self._context_state = None
        self._initialization_lock = False
        logger.info("Context state reset")


# Global context manager instance
_context_manager = BridgetContextManager()


def get_context_manager() -> BridgetContextManager:
    """Get the global context manager instance."""
    return _context_manager


def auto_initialize_bridget_context(client) -> str:
    """
    Auto-initialize Bridget context and return welcome message.
    
    Args:
        client: NetBoxClient instance
        
    Returns:
        Bridget welcome message with context information
    """
    try:
        context_manager = get_context_manager()
        
        # Check if auto-context is disabled
        if not os.getenv('NETBOX_AUTO_CONTEXT', 'true').lower() == 'true':
            logger.info("Auto-context disabled via NETBOX_AUTO_CONTEXT")
            return ""
        
        # Skip if already initialized
        if context_manager.is_context_initialized():
            logger.debug("Context already initialized, skipping auto-initialization")
            return ""
        
        # Initialize context
        context_state = context_manager.initialize_context(client)
        
        # Generate welcome message
        welcome_message = context_manager.generate_context_message(context_state)
        
        logger.info("Bridget auto-context successfully initialized")
        return welcome_message
        
    except Exception as e:
        logger.error(f"Auto-context initialization failed: {e}")
        try:
            # Try to use localized error message
            localizer = get_localizer()
            return localizer.get_message("welcome") + "\n\n⚠️ " + localizer.get_message("safety_guidance.maximum")
        except Exception:
            # Ultimate fallback
            return "🦜 **Bridget**: Context detection temporarily unavailable. Standard safety protocols active."


def merge_context_with_result(original_result: Any, context_message: str) -> Any:
    """
    Merge context message with original tool result.
    
    Args:
        original_result: Original tool execution result
        context_message: Context message to inject
        
    Returns:
        Merged result with context information
    """
    if not context_message:
        return original_result
    
    try:
        # Handle different result types
        if isinstance(original_result, dict):
            # Add context as new field
            merged_result = original_result.copy()
            merged_result['bridget_context'] = context_message
            return merged_result
        
        elif isinstance(original_result, str):
            # Prepend context to string result
            return f"{context_message}\n\n---\n\n{original_result}"
        
        else:
            # For other types, return as-is with context logged
            logger.debug(f"Context message available but not merged with result type: {type(original_result)}")
            return original_result
            
    except Exception as e:
        logger.error(f"Error merging context with result: {e}")
        return original_result