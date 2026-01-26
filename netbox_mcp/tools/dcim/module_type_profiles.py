#!/usr/bin/env python3
"""
DCIM Module Type Profiles Management Tools

Enterprise-grade tools for managing NetBox 4.3.x Module Type Profiles with comprehensive
schema validation and structured attribute management. Provides full lifecycle management
for modular component standardization with dual-tool pattern architecture.

Key Features:
- Profile Creation: Define JSON schema templates for module attributes
- Schema Validation: Enforce data types, required fields, and enums
- Profile Management: Complete CRUD operations with enterprise safety
- Module Type Association: Assign and manage profile relationships
- Structured Data: Validate module attributes against profile schemas
- Enterprise Safety: Comprehensive validation, conflict detection, and dry-run capabilities

NetBox 4.3.x Feature: Module Type Profiles provide structured schema definitions
for module attributes, enabling standardized hardware inventory management with
robust data validation and consistency across modular equipment deployments.
"""

from typing import Dict, Optional, Any
import logging
import json
from ...registry import mcp_tool
from ...client import NetBoxClient
from ...exceptions import (
    NetBoxValidationError as ValidationError,
    NetBoxNotFoundError as NotFoundError,
    NetBoxConflictError as ConflictError
)

logger = logging.getLogger(__name__)


# ======================================================================
# MODULE TYPE PROFILES MANAGEMENT (NetBox 4.3.x NEW FEATURE)
# ======================================================================

@mcp_tool(category="dcim")
def netbox_create_module_type_profile(
    client: NetBoxClient,
    name: str,
    schema: Dict[str, Any],
    description: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Create a module type profile for structured module attribute validation.
    
    This enterprise-grade function enables creation of JSON schema-based profiles
    that define and validate module type attributes. Essential for standardizing
    hardware inventory data with type safety and consistency across deployments.
    
    Args:
        client: NetBoxClient instance (injected)
        name: Profile name (e.g., "CPU", "Memory", "Storage")
        schema: JSON schema definition with properties, types, and validation rules
        description: Optional detailed description of the profile
        confirm: Must be True to execute (enterprise safety)
        
    Returns:
        Success status with profile details or error information
        
    Schema Format:
        {
            "properties": {
                "field_name": {
                    "type": "string|integer|number|boolean",
                    "title": "Display Name",
                    "description": "Field description",
                    "enum": ["option1", "option2"]  # For restricted values
                }
            },
            "required": ["field1", "field2"]  # Optional required fields list
        }
        
    Example:
        netbox_create_module_type_profile(
            name="Memory",
            schema={
                "properties": {
                    "class": {
                        "type": "string",
                        "title": "Memory Class", 
                        "enum": ["DDR3", "DDR4", "DDR5"]
                    },
                    "size": {
                        "type": "integer",
                        "title": "Size (GB)",
                        "description": "Memory capacity in gigabytes"
                    },
                    "ecc": {
                        "type": "boolean",
                        "title": "ECC Support"
                    }
                },
                "required": ["class", "size"]
            },
            description="Profile for memory modules with class, size, and ECC validation",
            confirm=True
        )
    """
    
    # STEP 1: DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Module Type Profile would be created. Set confirm=True to execute.",
            "would_create": {
                "name": name,
                "schema": schema,
                "description": description
            }
        }
    
    # STEP 2: PARAMETER VALIDATION
    if not name or not name.strip():
        raise ValidationError("Profile name cannot be empty")
    
    if not schema or not isinstance(schema, dict):
        raise ValidationError("Schema must be a valid dictionary")
    
    if "properties" not in schema:
        raise ValidationError("Schema must contain 'properties' field")
    
    if not isinstance(schema["properties"], dict):
        raise ValidationError("Schema 'properties' must be a dictionary")
    
    # Validate schema structure
    for field_name, field_def in schema["properties"].items():
        if not isinstance(field_def, dict):
            raise ValidationError(f"Field definition for '{field_name}' must be a dictionary")
        
        if "type" not in field_def:
            raise ValidationError(f"Field '{field_name}' must have a 'type' specification")
        
        valid_types = ["string", "integer", "number", "boolean"]
        if field_def["type"] not in valid_types:
            raise ValidationError(f"Field '{field_name}' type must be one of: {', '.join(valid_types)}")
    
    logger.info(f"Creating Module Type Profile '{name}' with {len(schema['properties'])} fields")
    
    # STEP 3: CONFLICT DETECTION - Check for existing profile with same name
    try:
        # ULTRATHINK FIX 1: Expand parameters optimization for profile conflict detection
        existing_profiles = list(client.dcim.module_type_profiles.filter(
            name=name,
            expand=["profile"],  # Expand related profile data
            no_cache=True,  # Force live check for accurate conflict detection
            limit=10
        ))
        
        if existing_profiles:
            existing_profile = existing_profiles[0]
            existing_id = existing_profile.get('id') if isinstance(existing_profile, dict) else existing_profile.id
            logger.warning(f"Profile conflict detected: '{name}' already exists (ID: {existing_id})")
            raise ConflictError(
                resource_type="Module Type Profile",
                identifier=name,
                existing_id=existing_id
            )
            
    except ConflictError:
        raise
    except Exception as e:
        logger.warning(f"Could not check for existing profiles: {e}")
    
    # STEP 4: CREATE PROFILE
    create_payload = {
        "name": name,
        "schema": schema,
        "description": description or ""
    }
    
    logger.info(f"Creating Module Type Profile with payload: {create_payload}")
    
    try:
        new_profile = client.dcim.module_type_profiles.create(confirm=confirm, **create_payload)
        
        # Handle both dict and object responses
        profile_id = new_profile.get('id') if isinstance(new_profile, dict) else new_profile.id
        profile_name = new_profile.get('name') if isinstance(new_profile, dict) else new_profile.name
        
        logger.info(f"Successfully created Module Type Profile '{profile_name}' (ID: {profile_id})")
        
    except Exception as e:
        logger.error(f"NetBox API error during profile creation: {e}")
        raise ValidationError(f"NetBox API error during profile creation: {e}")
    
    # STEP 5: RETURN SUCCESS
    return {
        "success": True,
        "message": f"Module Type Profile '{name}' successfully created.",
        "data": {
            "profile_id": profile_id,
            "name": profile_name,
            "schema": schema,
            "description": create_payload.get("description"),
            "field_count": len(schema["properties"]),
            "required_fields": schema.get("required", [])
        }
    }


@mcp_tool(category="dcim")
def netbox_list_all_module_type_profiles(
    client: NetBoxClient,
    limit: int = 100
) -> Dict[str, Any]:
    """
    List all module type profiles with comprehensive schema analysis.
    
    This discovery tool provides bulk profile exploration with schema statistics
    and field analysis. Essential for profile catalog management and standardized
    module attribute validation across the NetBox infrastructure.
    
    Args:
        client: NetBoxClient instance (injected)
        limit: Maximum number of profiles to return (default: 100)
        
    Returns:
        Comprehensive list of profiles with schema details and statistics
        
    Example:
        netbox_list_all_module_type_profiles()
    """
    
    logger.info(f"Listing Module Type Profiles (limit: {limit})")
    
    try:
        # ULTRATHINK FIX 1: Expand parameters optimization for profile discovery
        # Fetch all module type profiles with expanded data
        profiles_raw = list(client.dcim.module_type_profiles.filter(
            expand=["profile"],  # Expand profile relationships
            limit=limit
        ))
        
        # Process profiles with defensive dict/object handling
        profiles = []
        profile_stats = {
            "total_profiles": 0,
            "total_fields": 0,
            "field_types": {},
            "profiles_with_required_fields": 0
        }
        
        for profile in profiles_raw:
            # Apply defensive dict/object handling
            profile_id = profile.get('id') if isinstance(profile, dict) else profile.id
            name = profile.get('name') if isinstance(profile, dict) else profile.name
            description = profile.get('description') if isinstance(profile, dict) else getattr(profile, 'description', '')
            schema = profile.get('schema') if isinstance(profile, dict) else getattr(profile, 'schema', {})
            
            # Analyze schema structure
            field_count = 0
            field_types = {}
            required_fields = []
            
            if isinstance(schema, dict) and "properties" in schema:
                properties = schema["properties"]
                field_count = len(properties)
                
                for field_name, field_def in properties.items():
                    if isinstance(field_def, dict) and "type" in field_def:
                        field_type = field_def["type"]
                        field_types[field_type] = field_types.get(field_type, 0) + 1
                        profile_stats["field_types"][field_type] = profile_stats["field_types"].get(field_type, 0) + 1
                
                required_fields = schema.get("required", [])
                if required_fields:
                    profile_stats["profiles_with_required_fields"] += 1
            
            profile_stats["total_fields"] += field_count
            
            profiles.append({
                "id": profile_id,
                "name": name,
                "description": description,
                "field_count": field_count,
                "field_types": field_types,
                "required_fields": required_fields,
                "required_field_count": len(required_fields)
            })
        
        profile_stats["total_profiles"] = len(profiles)
        
        logger.info(f"Successfully retrieved {len(profiles)} module type profiles")
        
        return {
            "success": True,
            "count": len(profiles),
            "profiles": sorted(profiles, key=lambda x: x["name"]),
            "summary": profile_stats
        }
        
    except Exception as e:
        logger.error(f"Failed to list module type profiles: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@mcp_tool(category="dcim")
def netbox_get_module_type_profile_info(
    client: NetBoxClient,
    profile_name: str
) -> Dict[str, Any]:
    """
    Get detailed information about a specific module type profile.
    
    This inspection tool provides comprehensive profile details including
    complete schema definition, field specifications, validation rules,
    and usage statistics. Essential for profile verification and module
    type planning with structured attribute validation.
    
    Args:
        client: NetBoxClient instance (injected)
        profile_name: Profile name to inspect
        
    Returns:
        Detailed profile information with schema analysis or error details
        
    Example:
        netbox_get_module_type_profile_info("Memory")
    """
    
    if not profile_name or not profile_name.strip():
        raise ValidationError("Profile name cannot be empty")
    
    logger.info(f"Getting Module Type Profile info for '{profile_name}'")
    
    try:
        # ULTRATHINK FIX 1: Expand parameters optimization for profile lookup
        # Find profile by name with expanded data
        profiles = list(client.dcim.module_type_profiles.filter(
            name=profile_name,
            expand=["profile"],  # Expand profile relationships
            limit=10
        ))
        if not profiles:
            raise NotFoundError(f"Module Type Profile '{profile_name}' not found")
        
        profile = profiles[0]
        
        # Apply defensive dict/object handling
        profile_id = profile.get('id') if isinstance(profile, dict) else profile.id
        name = profile.get('name') if isinstance(profile, dict) else profile.name
        description = profile.get('description') if isinstance(profile, dict) else getattr(profile, 'description', '')
        schema = profile.get('schema') if isinstance(profile, dict) else getattr(profile, 'schema', {})
        
        # Analyze schema in detail
        schema_analysis = {
            "field_count": 0,
            "required_fields": [],
            "optional_fields": [],
            "field_details": {},
            "validation_rules": {
                "has_enums": False,
                "enum_fields": [],
                "type_distribution": {}
            }
        }
        
        if isinstance(schema, dict) and "properties" in schema:
            properties = schema["properties"]
            required_fields = schema.get("required", [])
            
            schema_analysis["field_count"] = len(properties)
            schema_analysis["required_fields"] = required_fields
            schema_analysis["optional_fields"] = [f for f in properties.keys() if f not in required_fields]
            
            for field_name, field_def in properties.items():
                if isinstance(field_def, dict):
                    field_type = field_def.get("type", "unknown")
                    field_title = field_def.get("title", field_name)
                    field_description = field_def.get("description", "")
                    field_enum = field_def.get("enum", [])
                    
                    # Track type distribution
                    schema_analysis["validation_rules"]["type_distribution"][field_type] = \
                        schema_analysis["validation_rules"]["type_distribution"].get(field_type, 0) + 1
                    
                    # Track enum usage
                    if field_enum:
                        schema_analysis["validation_rules"]["has_enums"] = True
                        schema_analysis["validation_rules"]["enum_fields"].append(field_name)
                    
                    schema_analysis["field_details"][field_name] = {
                        "type": field_type,
                        "title": field_title,
                        "description": field_description,
                        "required": field_name in required_fields,
                        "enum_values": field_enum,
                        "has_enum": bool(field_enum)
                    }
        
        # ULTRATHINK FIX 1: Expand parameters optimization for module type usage lookup
        # Count module types using this profile with manufacturer data
        module_types_using_profile = list(client.dcim.module_types.filter(
            profile_id=profile_id,
            expand=["manufacturer", "profile"],  # Expand manufacturer and profile data
            limit=50
        ))
        usage_count = len(module_types_using_profile)
        
        return {
            "success": True,
            "profile": {
                "id": profile_id,
                "name": name,
                "description": description,
                "schema": schema,
                "schema_analysis": schema_analysis,
                "usage": {
                    "module_types_count": usage_count,
                    "module_types_using": [
                        {
                            "model": mt.get('model') if isinstance(mt, dict) else mt.model,
                            "id": mt.get('id') if isinstance(mt, dict) else mt.id
                        }
                        for mt in module_types_using_profile[:10]  # Show first 10
                    ]
                }
            }
        }
        
    except (NotFoundError, ValidationError):
        raise
    except Exception as e:
        logger.error(f"Failed to get module type profile info for '{profile_name}': {e}")
        raise ValidationError(f"Failed to retrieve profile information: {e}")


@mcp_tool(category="dcim")
def netbox_update_module_type_profile(
    client: NetBoxClient,
    profile_name: str,
    new_name: Optional[str] = None,
    schema: Optional[Dict[str, Any]] = None,
    description: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Update module type profile properties with enterprise safety validation.
    
    This enterprise-grade function enables profile updates including schema
    modifications, name changes, and description updates. Uses established
    NetBox MCP update patterns with comprehensive schema validation.
    
    SAFETY WARNING: Schema changes may affect existing module type validations.
    Ensure compatibility with existing module types before updating schemas.
    
    Args:
        client: NetBoxClient instance (injected)
        profile_name: Current profile name
        new_name: Updated profile name
        schema: Updated JSON schema definition
        description: Updated description
        confirm: Must be True to execute (enterprise safety)
        
    Returns:
        Success status with updated profile details or error information
        
    Example:
        netbox_update_module_type_profile(
            profile_name="Memory",
            description="Updated memory module profile with enhanced validation",
            schema={
                "properties": {
                    "class": {"type": "string", "enum": ["DDR3", "DDR4", "DDR5"]},
                    "size": {"type": "integer", "title": "Size (GB)"},
                    "speed": {"type": "integer", "title": "Speed (MHz)"}
                },
                "required": ["class", "size"]
            },
            confirm=True
        )
    """
    
    # STEP 1: DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Module Type Profile would be updated. Set confirm=True to execute.",
            "would_update": {
                "profile_name": profile_name,
                "new_name": new_name,
                "schema": schema,
                "description": description
            },
            "warning": "Schema changes may affect existing module type validations."
        }
    
    # STEP 2: PARAMETER VALIDATION
    if not profile_name or not profile_name.strip():
        raise ValidationError("Profile name cannot be empty")
    
    if not any([new_name, schema, description]):
        raise ValidationError("At least one field (new_name, schema, description) must be provided for update")
    
    # Validate schema if provided
    if schema is not None:
        if not isinstance(schema, dict):
            raise ValidationError("Schema must be a valid dictionary")
        
        if "properties" not in schema:
            raise ValidationError("Schema must contain 'properties' field")
        
        if not isinstance(schema["properties"], dict):
            raise ValidationError("Schema 'properties' must be a dictionary")
        
        # Validate schema field definitions
        for field_name, field_def in schema["properties"].items():
            if not isinstance(field_def, dict):
                raise ValidationError(f"Field definition for '{field_name}' must be a dictionary")
            
            if "type" not in field_def:
                raise ValidationError(f"Field '{field_name}' must have a 'type' specification")
            
            valid_types = ["string", "integer", "number", "boolean"]
            if field_def["type"] not in valid_types:
                raise ValidationError(f"Field '{field_name}' type must be one of: {', '.join(valid_types)}")
    
    logger.info(f"Updating Module Type Profile '{profile_name}'")

    try:
        # STEP 3: LOOKUP PROFILE (with defensive dict/object handling)
        # ULTRATHINK FIX 1: Expand parameters optimization for profile lookup
        profiles = list(client.dcim.module_type_profiles.filter(
            name=profile_name,
            expand=["profile"],  # Expand profile relationships
            limit=10
        ))
        if not profiles:
            raise NotFoundError(f"Module Type Profile '{profile_name}' not found")
        
        profile = profiles[0]
        profile_id = profile.get('id') if isinstance(profile, dict) else profile.id
        
        # STEP 4: CONFLICT DETECTION - Check for name conflicts if new_name provided
        if new_name and new_name != profile_name:
            # ULTRATHINK FIX 1: Expand parameters optimization for conflict detection
            existing_names = list(client.dcim.module_type_profiles.filter(
                name=new_name,
                expand=["profile"],  # Expand profile data
                no_cache=True,
                limit=10
            ))
            if existing_names:
                conflicting_profile = existing_names[0]
                conflicting_id = conflicting_profile.get('id') if isinstance(conflicting_profile, dict) else conflicting_profile.id
                raise ConflictError(
                    resource_type="Module Type Profile",
                    identifier=new_name,
                    existing_id=conflicting_id
                )
        
        # STEP 5: BUILD UPDATE PAYLOAD
        update_payload = {}
        if new_name is not None:
            update_payload["name"] = new_name
        if schema is not None:
            update_payload["schema"] = schema
        if description is not None:
            update_payload["description"] = description
        
        logger.info(f"Updating profile {profile_id} with payload: {update_payload}")
        
        # STEP 6: UPDATE PROFILE - Use proven NetBox MCP update pattern
        updated_profile = client.dcim.module_type_profiles.update(profile_id, confirm=confirm, **update_payload)
        
        # Handle both dict and object responses
        updated_name = updated_profile.get('name') if isinstance(updated_profile, dict) else updated_profile.name
        updated_schema = updated_profile.get('schema') if isinstance(updated_profile, dict) else getattr(updated_profile, 'schema', {})
        updated_description = updated_profile.get('description') if isinstance(updated_profile, dict) else getattr(updated_profile, 'description', '')
        
        logger.info(f"Successfully updated Module Type Profile '{profile_name}'")
        
        # STEP 7: RETURN SUCCESS
        return {
            "success": True,
            "message": f"Module Type Profile '{profile_name}' successfully updated.",
            "data": {
                "profile_id": profile_id,
                "original_name": profile_name,
                "updated_fields": {
                    "name": updated_name,
                    "description": updated_description,
                    "schema": updated_schema if schema is not None else None
                },
                "schema_field_count": len(updated_schema.get("properties", {})) if updated_schema else None
            }
        }
        
    except (NotFoundError, ValidationError, ConflictError):
        raise
    except Exception as e:
        logger.error(f"Failed to update module type profile '{profile_name}': {e}")
        raise ValidationError(f"NetBox API error during profile update: {e}")


@mcp_tool(category="dcim")
def netbox_delete_module_type_profile(
    client: NetBoxClient,
    profile_name: str,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Delete a module type profile with enterprise safety validation.
    
    This enterprise-grade function enables safe profile removal with comprehensive
    validation and dependency checking. Uses established NetBox MCP delete patterns
    with defensive error handling.
    
    SAFETY WARNING: This operation cannot be undone. Ensure no module types are
    using this profile before deletion.
    
    Args:
        client: NetBoxClient instance (injected)
        profile_name: Profile name to delete
        confirm: Must be True to execute (enterprise safety)
        
    Returns:
        Success status with deletion details or error information
        
    Example:
        netbox_delete_module_type_profile(
            profile_name="Obsolete_Profile",
            confirm=True
        )
    """
    
    # STEP 1: DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Module Type Profile would be deleted. Set confirm=True to execute.",
            "would_delete": {
                "profile_name": profile_name
            },
            "warning": "This operation cannot be undone. Ensure no module types are using this profile."
        }
    
    # STEP 2: PARAMETER VALIDATION
    if not profile_name or not profile_name.strip():
        raise ValidationError("Profile name cannot be empty")
    
    logger.info(f"Deleting Module Type Profile '{profile_name}'")

    try:
        # STEP 3: LOOKUP PROFILE (with defensive dict/object handling)
        # ULTRATHINK FIX 1: Expand parameters optimization for profile deletion lookup
        profiles = list(client.dcim.module_type_profiles.filter(
            name=profile_name,
            expand=["profile"],  # Expand profile relationships
            limit=10
        ))
        if not profiles:
            raise NotFoundError(f"Module Type Profile '{profile_name}' not found")
        
        profile = profiles[0]
        profile_id = profile.get('id') if isinstance(profile, dict) else profile.id
        profile_name_actual = profile.get('name') if isinstance(profile, dict) else profile.name
        profile_description = profile.get('description') if isinstance(profile, dict) else getattr(profile, 'description', '')
        
        # STEP 4: DEPENDENCY CHECK - Check for module types using this profile
        # ULTRATHINK FIX 1: Expand parameters optimization for dependency checking
        module_types_using_profile = list(client.dcim.module_types.filter(
            profile_id=profile_id,
            expand=["manufacturer", "profile"],  # Expand manufacturer and profile data
            no_cache=True,
            limit=100
        ))
        if module_types_using_profile:
            module_type_models = []
            for module_type in module_types_using_profile[:5]:  # Show first 5 module types
                model_name = module_type.get('model') if isinstance(module_type, dict) else module_type.model
                module_type_models.append(model_name)
            
            return {
                "success": False,
                "error": f"Cannot delete profile '{profile_name}' - {len(module_types_using_profile)} module types are using this profile",
                "error_type": "DependencyError",
                "details": {
                    "module_types_using_profile": len(module_types_using_profile),
                    "example_module_types": module_type_models,
                    "action_required": "Remove or change profile for all module types before deletion"
                }
            }
        
        logger.info(f"Deleting profile {profile_id} ('{profile_name_actual}') - no dependencies found")
        
        # STEP 5: DELETE PROFILE - Use proven NetBox MCP delete pattern
        client.dcim.module_type_profiles.delete(profile_id, confirm=confirm)
        
        logger.info(f"Successfully deleted Module Type Profile '{profile_name}'")
        
        # STEP 6: RETURN SUCCESS
        return {
            "success": True,
            "message": f"Module Type Profile '{profile_name}' successfully deleted.",
            "data": {
                "deleted_profile": {
                    "id": profile_id,
                    "name": profile_name_actual,
                    "description": profile_description
                }
            }
        }
        
    except (NotFoundError, ValidationError):
        raise
    except Exception as e:
        logger.error(f"Failed to delete module type profile '{profile_name}': {e}")
        raise ValidationError(f"NetBox API error during profile deletion: {e}")


@mcp_tool(category="dcim")
def netbox_assign_profile_to_module_type(
    client: NetBoxClient,
    manufacturer: str,
    model: str,
    profile_name: str,
    attributes: Optional[Dict[str, Any]] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Assign a module type profile to a module type with optional attributes.
    
    This enterprise-grade function enables profile assignment and structured
    attribute validation for module types. Validates attributes against the
    profile schema and ensures data consistency.
    
    Args:
        client: NetBoxClient instance (injected)
        manufacturer: Module type manufacturer name
        model: Module type model name
        profile_name: Profile name to assign
        attributes: Optional structured attributes validated against profile schema
        confirm: Must be True to execute (enterprise safety)
        
    Returns:
        Success status with assignment details or error information
        
    Example:
        netbox_assign_profile_to_module_type(
            manufacturer="Cisco",
            model="SFP-10G-LR",
            profile_name="SFP",
            attributes={
                "speed": "10G",
                "interface": "LC",
                "wavelength": 1310
            },
            confirm=True
        )
    """
    
    # STEP 1: DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Profile would be assigned to module type. Set confirm=True to execute.",
            "would_assign": {
                "manufacturer": manufacturer,
                "model": model,
                "profile_name": profile_name,
                "attributes": attributes
            }
        }
    
    # STEP 2: PARAMETER VALIDATION
    if not manufacturer or not manufacturer.strip():
        raise ValidationError("Manufacturer cannot be empty")
    
    if not model or not model.strip():
        raise ValidationError("Model cannot be empty")
    
    if not profile_name or not profile_name.strip():
        raise ValidationError("Profile name cannot be empty")
    
    logger.info(f"Assigning profile '{profile_name}' to module type '{model}' by '{manufacturer}'")
    
    try:
        # STEP 3: LOOKUP PROFILE (with defensive dict/object handling)
        # ULTRATHINK FIX 1: Expand parameters optimization for profile assignment lookup
        profiles = list(client.dcim.module_type_profiles.filter(
            name=profile_name,
            expand=["profile"],  # Expand profile relationships
            limit=10
        ))
        if not profiles:
            raise NotFoundError(f"Module Type Profile '{profile_name}' not found")
        
        profile = profiles[0]
        profile_id = profile.get('id') if isinstance(profile, dict) else profile.id
        profile_schema = profile.get('schema') if isinstance(profile, dict) else getattr(profile, 'schema', {})
        
        # STEP 4: LOOKUP MODULE TYPE
        # ULTRATHINK FIX 1: Expand parameters optimization + ULTRATHINK FIX 4: Enhanced fallback
        # Find manufacturer first with expanded data
        manufacturers = list(client.dcim.manufacturers.filter(
            name=manufacturer,
            expand=["manufacturer"],  # Expand manufacturer relationships
            limit=10
        ))

        # ULTRATHINK FIX 4: Slug-based fallback with case-insensitive search
        if not manufacturers:
            manufacturers = list(client.dcim.manufacturers.filter(
                slug=manufacturer.lower().replace(' ', '-'),
                expand=["manufacturer"],
                limit=10
            ))

        # ULTRATHINK FIX 4: Case-insensitive name fallback
        if not manufacturers:
            manufacturers = list(client.dcim.manufacturers.filter(
                name__icontains=manufacturer,
                expand=["manufacturer"],
                limit=10
            ))

        if not manufacturers:
            raise NotFoundError(f"Manufacturer '{manufacturer}' not found")

        manufacturer_obj = manufacturers[0]
        manufacturer_id = manufacturer_obj.get('id') if isinstance(manufacturer_obj, dict) else manufacturer_obj.id
        manufacturer_name = manufacturer_obj.get('name') if isinstance(manufacturer_obj, dict) else manufacturer_obj.name

        # ULTRATHINK FIX 1: Expand parameters optimization for module type lookup
        # Find module type with manufacturer and profile data
        module_types = list(client.dcim.module_types.filter(
            manufacturer_id=manufacturer_id,
            model=model,
            expand=["manufacturer", "profile"],  # Expand manufacturer and profile data
            limit=10
        ))
        if not module_types:
            raise NotFoundError(f"Module type '{model}' by '{manufacturer}' not found")
        
        module_type = module_types[0]
        module_type_id = module_type.get('id') if isinstance(module_type, dict) else module_type.id
        
        # STEP 5: VALIDATE ATTRIBUTES AGAINST SCHEMA (if attributes provided)
        if attributes and isinstance(profile_schema, dict) and "properties" in profile_schema:
            schema_properties = profile_schema["properties"]
            required_fields = profile_schema.get("required", [])
            
            # Check required fields
            for required_field in required_fields:
                if required_field not in attributes:
                    raise ValidationError(f"Required field '{required_field}' missing in attributes")
            
            # Validate field types and enums
            for attr_name, attr_value in attributes.items():
                if attr_name in schema_properties:
                    field_def = schema_properties[attr_name]
                    expected_type = field_def.get("type")
                    
                    # Type validation
                    if expected_type == "string" and not isinstance(attr_value, str):
                        raise ValidationError(f"Field '{attr_name}' must be a string")
                    elif expected_type == "integer" and not isinstance(attr_value, int):
                        raise ValidationError(f"Field '{attr_name}' must be an integer")
                    elif expected_type == "number" and not isinstance(attr_value, (int, float)):
                        raise ValidationError(f"Field '{attr_name}' must be a number")
                    elif expected_type == "boolean" and not isinstance(attr_value, bool):
                        raise ValidationError(f"Field '{attr_name}' must be a boolean")
                    
                    # Enum validation
                    if "enum" in field_def:
                        allowed_values = field_def["enum"]
                        if attr_value not in allowed_values:
                            raise ValidationError(f"Field '{attr_name}' value '{attr_value}' not in allowed values: {allowed_values}")
        
        # STEP 6: UPDATE MODULE TYPE WITH PROFILE AND ATTRIBUTES
        update_payload = {
            "profile": profile_id
        }
        
        if attributes:
            update_payload["attributes"] = attributes
        
        logger.info(f"Updating module type {module_type_id} with profile assignment: {update_payload}")
        
        # Use proven NetBox MCP update pattern
        updated_module_type = client.dcim.module_types.update(module_type_id, confirm=confirm, **update_payload)
        
        # Handle both dict and object responses
        updated_attributes = updated_module_type.get('attributes') if isinstance(updated_module_type, dict) else getattr(updated_module_type, 'attributes', {})
        
        logger.info(f"Successfully assigned profile '{profile_name}' to module type '{model}' by '{manufacturer}'")
        
        # STEP 7: RETURN SUCCESS
        return {
            "success": True,
            "message": f"Profile '{profile_name}' successfully assigned to module type '{model}' by '{manufacturer}'.",
            "data": {
                "module_type": {
                    "id": module_type_id,
                    "model": model,
                    "manufacturer": {
                        "name": manufacturer_name,
                        "id": manufacturer_id
                    }
                },
                "profile": {
                    "id": profile_id,
                    "name": profile_name
                },
                "attributes": updated_attributes,
                "attribute_count": len(updated_attributes) if updated_attributes else 0
            }
        }
        
    except (NotFoundError, ValidationError):
        raise
    except Exception as e:
        logger.error(f"Failed to assign profile '{profile_name}' to module type '{model}' by '{manufacturer}': {e}")
        raise ValidationError(f"NetBox API error during profile assignment: {e}")