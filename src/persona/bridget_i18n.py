"""
Bridget Internationalization (i18n) System

This module provides multi-language support for Bridget's persona-based assistance,
enabling automatic language detection and localized messaging for international
NetBox MCP deployment scenarios.
"""

import os
import locale
import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from threading import Lock

logger = logging.getLogger(__name__)

@dataclass
class LanguageConfig:
    """Configuration for language detection and selection."""
    code: str
    name: str
    country_indicators: list
    url_patterns: list
    fallback_to: Optional[str] = None

class BridgetLanguageDetector:
    """
    Intelligent language detection for Bridget's persona system.
    
    Detection Priority:
    1. Environment Variable (NETBOX_BRIDGET_LANGUAGE)
    2. NetBox URL patterns (regional indicators)
    3. System locale detection
    4. Default fallback (English for international use)
    """
    
    # Supported languages with detection patterns
    SUPPORTED_LANGUAGES = {
        'nl': LanguageConfig(
            code='nl',
            name='Nederlands',
            country_indicators=['.nl', 'netherlands', 'nederland', 'amsterdam'],
            url_patterns=['demo.netbox.nl', 'netbox.company.nl', '.nl/'],
        ),
        'en': LanguageConfig(
            code='en', 
            name='English',
            country_indicators=['.com', '.org', '.net', 'cloud'],
            url_patterns=['cloud.netboxapp.com', '.com/', '.org/'],
        )
    }
    
    def __init__(self):
        self._detection_cache = {}
        self._cache_lock = Lock()
    
    def detect_language(self, manual_override: Optional[str] = None) -> str:
        """
        Perform comprehensive language detection.
        
        Args:
            manual_override: Force specific language (bypasses all detection)
            
        Returns:
            Language code ('nl' or 'en')
        """
        
        # Check cache first for performance
        cache_key = f"{manual_override}_{os.getenv('NETBOX_URL', '')}_{os.getenv('NETBOX_BRIDGET_LANGUAGE', '')}"
        
        with self._cache_lock:
            if cache_key in self._detection_cache:
                return self._detection_cache[cache_key]
        
        try:
            # 1. Manual override (highest priority)
            if manual_override and manual_override.lower() in self.SUPPORTED_LANGUAGES:
                detected_lang = manual_override.lower()
                logger.debug(f"Manual language override: {detected_lang}")
                
            # 2. Environment variable override
            elif env_lang := self.get_language_from_environment():
                detected_lang = env_lang
                logger.debug(f"Environment variable language: {detected_lang}")
                
            # 3. NetBox URL pattern detection
            elif url_lang := self.get_language_from_netbox_url():
                detected_lang = url_lang
                logger.debug(f"URL pattern language: {detected_lang}")
                
            # 4. System locale detection
            elif locale_lang := self.get_language_from_system_locale():
                detected_lang = locale_lang
                logger.debug(f"System locale language: {detected_lang}")
                
            # 5. Default fallback (English for international)
            else:
                detected_lang = 'en'
                logger.debug("Using default language: en")
            
            # Cache the result
            with self._cache_lock:
                self._detection_cache[cache_key] = detected_lang
                
            logger.info(f"Bridget language detected: {detected_lang}")
            return detected_lang
            
        except Exception as e:
            logger.warning(f"Language detection failed: {e}, falling back to English")
            return 'en'
    
    def get_language_from_environment(self) -> Optional[str]:
        """
        Detect language from environment variables.
        
        Checks:
        - NETBOX_BRIDGET_LANGUAGE (explicit override)
        - NETBOX_BRIDGET_LOCALE (alternative format)
        """
        
        # Primary environment variable
        lang_override = os.getenv('NETBOX_BRIDGET_LANGUAGE', '').lower().strip()
        if lang_override in self.SUPPORTED_LANGUAGES:
            return lang_override
        
        # Alternative format support
        locale_override = os.getenv('NETBOX_BRIDGET_LOCALE', '').lower().strip()
        if locale_override.startswith('nl'):
            return 'nl'
        elif locale_override.startswith('en'):
            return 'en'
        
        return None
    
    def get_language_from_netbox_url(self) -> Optional[str]:
        """
        Detect language from NetBox instance URL patterns.
        
        Uses domain patterns and regional indicators to infer
        the most appropriate language for the user's context.
        """
        
        netbox_url = os.getenv('NETBOX_URL', '').lower().strip()
        if not netbox_url:
            return None
        
        logger.debug(f"Analyzing NetBox URL for language: {netbox_url}")
        
        # Check each supported language's patterns
        for lang_code, config in self.SUPPORTED_LANGUAGES.items():
            for indicator in config.country_indicators:
                if indicator in netbox_url:
                    logger.debug(f"Found {lang_code} indicator '{indicator}' in URL")
                    return lang_code
            
            for pattern in config.url_patterns:
                if pattern in netbox_url:
                    logger.debug(f"Found {lang_code} pattern '{pattern}' in URL")
                    return lang_code
        
        return None
    
    def get_language_from_system_locale(self) -> Optional[str]:
        """
        Detect language from system locale settings.
        
        Falls back to system locale when other detection methods fail.
        Useful for development environments and personal deployments.
        """
        
        try:
            # Get system default locale
            system_locale = locale.getdefaultlocale()
            if system_locale and system_locale[0]:
                locale_code = system_locale[0].lower()
                logger.debug(f"System locale: {locale_code}")
                
                # Check for Dutch locale variants
                if locale_code.startswith('nl'):
                    return 'nl'
                
                # Check for English locale variants  
                elif locale_code.startswith('en'):
                    return 'en'
            
        except Exception as e:
            logger.debug(f"System locale detection failed: {e}")
        
        return None
    
    def get_language_info(self, language_code: str) -> Optional[LanguageConfig]:
        """Get configuration information for a language."""
        return self.SUPPORTED_LANGUAGES.get(language_code)


class BridgetLocalizer:
    """
    Multi-language message localization for Bridget's persona system.
    
    Provides consistent, culturally-appropriate messaging across different
    languages while maintaining Bridget's professional yet friendly persona.
    """
    
    def __init__(self, language: str = 'auto'):
        """
        Initialize the localizer with language preference.
        
        Args:
            language: Language code ('nl', 'en', or 'auto' for detection)
        """
        self.detector = BridgetLanguageDetector()
        self._message_cache = {}
        self._cache_lock = Lock()
        
        # Resolve language
        if language == 'auto':
            self.current_language = self.detector.detect_language()
        else:
            self.current_language = self.detector.detect_language(manual_override=language)
        
        # Load language module
        self._load_language_module()
        
        logger.info(f"Bridget localizer initialized: {self.current_language}")
    
    def _load_language_module(self):
        """Load the appropriate language module for message templates."""
        try:
            if self.current_language == 'nl':
                try:
                    from .locales import nl
                except ImportError:
                    from locales import nl
                self.messages = nl.MESSAGES
                self.format_helpers = getattr(nl, 'FORMAT_HELPERS', {})
            elif self.current_language == 'en':
                try:
                    from .locales import en
                except ImportError:
                    from locales import en
                self.messages = en.MESSAGES
                self.format_helpers = getattr(en, 'FORMAT_HELPERS', {})
            else:
                raise ValueError(f"Unsupported language: {self.current_language}")
                
            logger.debug(f"Loaded language module: {self.current_language}")
            
        except ImportError as e:
            logger.error(f"Failed to load language module {self.current_language}: {e}")
            # Fallback to English
            if self.current_language != 'en':
                logger.warning("Falling back to English")
                self.current_language = 'en'
                try:
                    from .locales import en
                except ImportError:
                    from locales import en
                self.messages = en.MESSAGES
                self.format_helpers = getattr(en, 'FORMAT_HELPERS', {})
            else:
                raise
    
    def get_message(self, message_key: str, **kwargs) -> str:
        """
        Get localized message with parameter substitution.
        
        Args:
            message_key: Dot-notation key for message (e.g., 'environment_detected.production')
            **kwargs: Parameters for message formatting
            
        Returns:
            Formatted localized message
        """
        
        # Check cache first
        cache_key = f"{message_key}_{hash(frozenset(kwargs.items()) if kwargs else 0)}"
        
        with self._cache_lock:
            if cache_key in self._message_cache:
                return self._message_cache[cache_key]
        
        try:
            # Navigate nested message structure
            message_parts = message_key.split('.')
            current = self.messages
            
            for part in message_parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    raise KeyError(f"Message key '{message_key}' not found")
            
            # Format message with parameters
            if isinstance(current, str):
                formatted_message = current.format(**kwargs) if kwargs else current
            else:
                raise ValueError(f"Message key '{message_key}' does not resolve to string")
            
            # Cache the result
            with self._cache_lock:
                self._message_cache[cache_key] = formatted_message
            
            return formatted_message
            
        except Exception as e:
            logger.error(f"Failed to get message '{message_key}': {e}")
            # Return fallback message in English
            return f"[{message_key}]"  # Developer-friendly fallback
    
    def format_context_message(self, environment: str, safety_level: str, **extra_context) -> str:
        """
        Format complete context message for Bridget's welcome.
        
        Args:
            environment: Detected environment (demo/staging/production/cloud)
            safety_level: Assigned safety level (standard/high/maximum)
            **extra_context: Additional context parameters
            
        Returns:
            Complete formatted context message
        """
        
        try:
            # Get core message components
            welcome = self.get_message("welcome")
            env_detected = self.get_message(f"environment_detected.{environment}")
            safety_guidance = self.get_message(f"safety_guidance.{safety_level}")
            context_complete = self.get_message("context_complete")
            
            # Get environment-specific details
            env_details = self.get_message(f"environment_details.{environment}", **extra_context)
            
            # Build complete message
            message_parts = [
                welcome,
                "",  # Empty line for spacing
                env_detected,
                env_details,
                "",
                safety_guidance,
                "",
                context_complete
            ]
            
            # Add signature
            signature = self.get_message("signature")
            message_parts.extend(["", "---", signature])
            
            return "\n".join(message_parts)
            
        except Exception as e:
            logger.error(f"Failed to format context message: {e}")
            # Fallback to basic English message
            return f"🦜 Bridget here! Environment: {environment}, Safety: {safety_level}"
    
    def set_language(self, language: str):
        """
        Change the current language and reload messages.
        
        Args:
            language: New language code ('nl', 'en', or 'auto')
        """
        
        old_language = self.current_language
        
        if language == 'auto':
            self.current_language = self.detector.detect_language()
        else:
            self.current_language = self.detector.detect_language(manual_override=language)
        
        if self.current_language != old_language:
            # Clear cache and reload
            with self._cache_lock:
                self._message_cache.clear()
            
            self._load_language_module()
            logger.info(f"Language changed from {old_language} to {self.current_language}")
        else:
            logger.debug(f"Language remains: {self.current_language}")
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Get list of supported languages."""
        return {
            code: config.name 
            for code, config in self.detector.SUPPORTED_LANGUAGES.items()
        }
    
    def get_current_language_info(self) -> Tuple[str, str]:
        """Get current language code and name."""
        config = self.detector.get_language_info(self.current_language)
        return self.current_language, config.name if config else "Unknown"


# Global instance for easy access
_global_localizer: Optional[BridgetLocalizer] = None
_localizer_lock = Lock()

def get_localizer(language: str = 'auto') -> BridgetLocalizer:
    """
    Get global Bridget localizer instance.
    
    Args:
        language: Language preference ('nl', 'en', or 'auto')
        
    Returns:
        BridgetLocalizer instance
    """
    global _global_localizer
    
    with _localizer_lock:
        if _global_localizer is None:
            _global_localizer = BridgetLocalizer(language=language)
        elif language != 'auto' and _global_localizer.current_language != language:
            # Language change requested
            _global_localizer.set_language(language)
    
    return _global_localizer