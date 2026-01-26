#!/usr/bin/env python3
"""
Shared validation utilities for NetBox MCP tools.

This module provides centralized validation logic to reduce code duplication
across NetBox MCP tools, ensuring consistent validation behavior.
"""

from typing import List, Optional
from netbox_mcp.exceptions import NetBoxValidationError


class CableValidator:
    """Validator for cable-related parameters."""
    
    # Standard cable colors supported by NetBox
    VALID_COLORS = [
        "pink", "red", "blue", "green", "yellow", "orange", 
        "purple", "grey", "black", "white", "brown", "cyan", 
        "magenta", "lime", "silver", "gold"
    ]
    
    # Standard cable types supported by NetBox
    VALID_TYPES = [
        "cat3", "cat5", "cat5e", "cat6", "cat6a", "cat7", "cat7a", "cat8",
        "dac-active", "dac-passive", "mrj21-trunk", "coaxial", "mmf", "mmf-om1",
        "mmf-om2", "mmf-om3", "mmf-om4", "mmf-om5", "smf", "smf-os1", "smf-os2",
        "aoc", "power"
    ]
    
    @classmethod
    def normalize_and_validate_color(cls, color_input: str, valid_colors: List[str] = None) -> Optional[str]:
        """
        Normaliseert en valideert een kleur-string gebaseerd op Gemini's aanbeveling.
        Retourneert de valide kleurnaam of None als deze niet wordt gevonden.
        
        GEMINI FIX: Enhanced color validation that extracts color from compound strings.
        Handles inputs like "cat6 green", "green cable", etc.
        
        Args:
            color_input: Input string that may contain color (e.g., "cat6 green")
            valid_colors: List of valid colors (defaults to VALID_COLORS)
            
        Returns:
            Normalized color string or None if not found
        """
        if not color_input:
            return None
        
        if valid_colors is None:
            valid_colors = cls.VALID_COLORS
        
        color_lower = color_input.lower().strip()
        
        # First try: Look for color names within the input string
        for valid_color in valid_colors:
            if valid_color in color_lower:
                return valid_color  # e.g. "cat6 green" -> "green"
                
        # Second try: Check if the input is a direct color name
        if color_lower in valid_colors:
            return color_lower
            
        return None  # Color not found

    @classmethod
    def validate_color(cls, color: Optional[str]) -> Optional[str]:
        """
        Validate and normalize cable color with enhanced extraction capability.
        
        GEMINI FIX: Uses improved normalize_and_validate_color for better UX.
        
        Args:
            color: Color string to validate (case-insensitive, can be compound)
            
        Returns:
            Normalized color string (lowercase) or None if input is None
            
        Raises:
            NetBoxValidationError: If color is invalid
        """
        if color is None:
            return None
            
        # Use enhanced color normalization
        normalized_color = cls.normalize_and_validate_color(color, cls.VALID_COLORS)
        
        if color is not None and not normalized_color:
            # Provide clear feedback with available options
            raise NetBoxValidationError(
                f"Kleur '{color}' is niet valide. Geldige kleuren zijn: {', '.join(cls.VALID_COLORS)}"
            )
        
        return normalized_color
    
    @classmethod
    def validate_type(cls, cable_type: str) -> str:
        """
        Validate cable type.
        
        Args:
            cable_type: Cable type string to validate
            
        Returns:
            Validated cable type string
            
        Raises:
            NetBoxValidationError: If cable type is invalid
        """
        if not cable_type or not cable_type.strip():
            raise NetBoxValidationError("Cable type cannot be empty")
        
        # Normalize cable type to lowercase and strip whitespace
        normalized_type = cable_type.strip().lower()
        
        # Validate against known types
        if normalized_type not in cls.VALID_TYPES:
            raise NetBoxValidationError(
                f"Invalid cable_type: '{cable_type}'. "
                f"Valid types: {', '.join(cls.VALID_TYPES)}"
            )
        
        return normalized_type
    
    @classmethod
    def get_valid_colors(cls) -> List[str]:
        """Get list of valid cable colors."""
        return cls.VALID_COLORS.copy()
    
    @classmethod
    def get_valid_types(cls) -> List[str]:
        """Get list of valid cable types."""
        return cls.VALID_TYPES.copy()


class PowerValidator:
    """Validator for power-related parameters."""
    
    # Standard power cable types
    VALID_POWER_TYPES = [
        "power", "dc-power", "ac-power"
    ]
    
    # Standard power outlet types
    VALID_OUTLET_TYPES = [
        "iec-60320-c5", "iec-60320-c7", "iec-60320-c13", "iec-60320-c15", 
        "iec-60320-c19", "iec-60320-c21", "iec-60309-p-n-e-4h", "iec-60309-p-n-e-6h", 
        "iec-60309-2p-e-4h", "iec-60309-2p-e-6h", "iec-60309-3p-e-4h", "iec-60309-3p-e-6h",
        "iec-60309-3p-n-e-4h", "iec-60309-3p-n-e-6h", "nema-1-15r", "nema-5-15r", 
        "nema-5-20r", "nema-5-30r", "nema-5-50r", "nema-6-15r", "nema-6-20r", 
        "nema-6-30r", "nema-6-50r", "nema-10-30r", "nema-10-50r", "nema-14-20r", 
        "nema-14-30r", "nema-14-50r", "nema-14-60r", "nema-15-15r", "nema-15-20r", 
        "nema-15-30r", "nema-15-50r", "nema-15-60r", "nema-l1-15r", "nema-l5-15r", 
        "nema-l5-20r", "nema-l5-30r", "nema-l5-50r", "nema-l6-15r", "nema-l6-20r", 
        "nema-l6-30r", "nema-l6-50r", "nema-l10-30r", "nema-l14-20r", "nema-l14-30r", 
        "nema-l14-50r", "nema-l14-60r", "nema-l15-20r", "nema-l15-30r", "nema-l15-50r", 
        "nema-l15-60r", "nema-l21-20r", "nema-l21-30r", "nema-l22-20r", "nema-l22-30r", 
        "cs6360c", "cs6364c", "cs8164c", "cs8264c", "cs8364c", "cs8464c", "ita-e", 
        "ita-f", "ita-g", "ita-h", "ita-i", "ita-j", "ita-k", "ita-l", "ita-m", 
        "ita-n", "ita-o", "schuko", "cee-7-7", "bs-1363", "other"
    ]
    
    @classmethod
    def validate_power_type(cls, power_type: str) -> str:
        """
        Validate power cable type.
        
        Args:
            power_type: Power cable type string to validate
            
        Returns:
            Validated power cable type string
            
        Raises:
            NetBoxValidationError: If power type is invalid
        """
        if not power_type or not power_type.strip():
            raise NetBoxValidationError("Power cable type cannot be empty")
        
        # Normalize power type to lowercase and strip whitespace
        normalized_type = power_type.strip().lower()
        
        # Validate against known types
        if normalized_type not in cls.VALID_POWER_TYPES:
            raise NetBoxValidationError(
                f"Invalid power_type: '{power_type}'. "
                f"Valid types: {', '.join(cls.VALID_POWER_TYPES)}"
            )
        
        return normalized_type
    
    @classmethod
    def validate_outlet_type(cls, outlet_type: str) -> str:
        """
        Validate power outlet type.
        
        Args:
            outlet_type: Power outlet type string to validate
            
        Returns:
            Validated power outlet type string
            
        Raises:
            NetBoxValidationError: If outlet type is invalid
        """
        if not outlet_type or not outlet_type.strip():
            raise NetBoxValidationError("Power outlet type cannot be empty")
        
        # Normalize outlet type to lowercase and strip whitespace
        normalized_type = outlet_type.strip().lower()
        
        # Validate against known types
        if normalized_type not in cls.VALID_OUTLET_TYPES:
            raise NetBoxValidationError(
                f"Invalid outlet_type: '{outlet_type}'. "
                f"Valid types: {', '.join(cls.VALID_OUTLET_TYPES)}"
            )
        
        return normalized_type
    
    @classmethod
    def get_valid_power_types(cls) -> List[str]:
        """Get list of valid power cable types."""
        return cls.VALID_POWER_TYPES.copy()
    
    @classmethod
    def get_valid_outlet_types(cls) -> List[str]:
        """Get list of valid power outlet types."""
        return cls.VALID_OUTLET_TYPES.copy()