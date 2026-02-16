#!/usr/bin/env python3
"""
Tenancy Contact Management Tools

High-level tools for managing NetBox contacts, contact roles,
and contact assignments with enterprise-grade functionality.
"""

from typing import Dict, Optional, Any
import logging
from ...registry import mcp_tool
from ...client import NetBoxClient

logger = logging.getLogger(__name__)


@mcp_tool(category="tenancy")
def netbox_create_contact_for_tenant(
    client: NetBoxClient,
    tenant_name: str,
    contact_name: str,
    role_name: str,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    address: Optional[str] = None,
    title: Optional[str] = None,
    organization: Optional[str] = None,
    comments: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Create and assign a new contact to a tenant with specified role for operational management.
    
    This enterprise-grade contact management tool simplifies the creation and assignment of
    contacts to tenants, essential for operational processes, customer relationship management,
    and administrative workflows in multi-tenant NetBox environments.
    
    Args:
        client: NetBoxClient instance (injected)
        tenant_name: Name or slug of the target tenant
        contact_name: Full name of the contact person
        role_name: Contact role (e.g., "Technical", "Administrative", "Billing", "Emergency")
        phone: Contact phone number (optional)
        email: Contact email address (optional)
        address: Contact postal address (optional)
        title: Contact job title (optional)
        organization: Contact organization/company (optional)
        comments: Additional notes about the contact (optional)
        confirm: Safety confirmation (default: False)
        
    Returns:
        Contact creation and assignment result with tenant linkage
        
    Examples:
        # Create technical contact for tenant
        netbox_create_contact_for_tenant(
            tenant_name="MegaCorp Inc",
            contact_name="John Smith",
            role_name="Technical",
            phone="+1-555-0123",
            email="john.smith@megacorp.com",
            confirm=True
        )
        
        # Create administrative contact with full details
        netbox_create_contact_for_tenant(
            tenant_name="Enterprise-Customer",
            contact_name="Jane Doe",
            role_name="Administrative", 
            phone="+1-555-0456",
            email="jane.doe@enterprise.com",
            title="IT Manager",
            organization="Enterprise Customer Corp",
            confirm=True
        )
        
        # Emergency contact for critical operations
        netbox_create_contact_for_tenant(
            tenant_name="Critical-Services",
            contact_name="Emergency NOC",
            role_name="Emergency",
            phone="+1-555-911",
            email="noc@critical-services.com",
            comments="24/7 emergency contact for critical incidents",
            confirm=True
        )
    """
    try:
        if not confirm:
            return {
                "success": False,
                "error": "Contact creation requires confirm=True for safety",
                "error_type": "ValidationError"
            }
        
        if not tenant_name or not contact_name or not role_name:
            return {
                "success": False,
                "error": "tenant_name, contact_name, and role_name are required",
                "error_type": "ValidationError"
            }
        
        logger.info(f"Creating contact '{contact_name}' for tenant '{tenant_name}' with role '{role_name}'")
        
        # Step 1: Resolve tenant
        logger.debug(f"Looking up tenant: {tenant_name}")
        # ULTRATHINK FIX 1: Expand parameters optimization + ULTRATHINK FIX 4: Enhanced fallback
        tenants = list(client.tenancy.tenants.filter(
            name=tenant_name,
            expand=["group"],  # Expand tenant group relationships
            limit=10
        ))
        if not tenants:
            # ULTRATHINK FIX 4: Slug-based fallback with expand parameters
            tenants = list(client.tenancy.tenants.filter(
                slug=tenant_name,
                expand=["group"],
                limit=10
            ))
        # ULTRATHINK FIX 4: Case-insensitive name fallback
        if not tenants:
            tenants = list(client.tenancy.tenants.filter(
                name__icontains=tenant_name,
                expand=["group"],
                limit=10
            ))
        
        if not tenants:
            return {
                "success": False,
                "error": f"Tenant '{tenant_name}' not found",
                "error_type": "NotFoundError"
            }
        
        tenant_obj = tenants[0]
        tenant_id = tenant_obj["id"]
        logger.debug(f"Found tenant: {tenant_obj['name']} (ID: {tenant_id})")
        
        # Step 2: Resolve contact role
        logger.debug(f"Looking up contact role: {role_name}")
        # ULTRATHINK FIX 1: Expand parameters optimization + ULTRATHINK FIX 4: Enhanced fallback
        roles = list(client.tenancy.contact_roles.filter(
            name=role_name,
            expand=["role"],  # Expand role relationships
            limit=10
        ))
        if not roles:
            # ULTRATHINK FIX 4: Slug-based fallback with expand parameters
            roles = list(client.tenancy.contact_roles.filter(
                slug=role_name,
                expand=["role"],
                limit=10
            ))
        # ULTRATHINK FIX 4: Case-insensitive name fallback
        if not roles:
            roles = list(client.tenancy.contact_roles.filter(
                name__icontains=role_name,
                expand=["role"],
                limit=10
            ))
        
        if not roles:
            return {
                "success": False,
                "error": f"Contact role '{role_name}' not found. Available roles can be checked via NetBox admin interface.",
                "error_type": "NotFoundError"
            }
        
        role_obj = roles[0]
        role_id = role_obj["id"]
        logger.debug(f"Found contact role: {role_obj['name']} (ID: {role_id})")
        
        # Step 3: Prepare contact data
        contact_data = {
            "name": contact_name
        }
        
        # Add optional fields if provided
        if phone:
            contact_data["phone"] = phone
        if email:
            contact_data["email"] = email
        if address:
            contact_data["address"] = address
        if title:
            contact_data["title"] = title
        if organization:
            contact_data["organization"] = organization
        if comments:
            contact_data["comments"] = comments
        
        logger.debug(f"Contact data prepared: {list(contact_data.keys())}")
        
        # Step 4: Create contact
        logger.info(f"Creating contact: {contact_name}")
        created_contact = client.tenancy.contacts.create(confirm=True, **contact_data)
        contact_id = created_contact["id"]
        
        logger.info(f"✅ Contact created: {contact_name} (ID: {contact_id})")
        
        # Step 5: Create contact assignment to tenant
        logger.info(f"Assigning contact {contact_id} to tenant {tenant_id} with role {role_id}")
        
        assignment_data = {
            "object_type": "tenancy.tenant",  # Content type for tenant
            "object_id": tenant_id,
            "contact": contact_id,
            "role": role_id
        }
        
        created_assignment = client.tenancy.contact_assignments.create(confirm=True, **assignment_data)
        assignment_id = created_assignment["id"]
        
        logger.info(f"✅ Contact assignment created: Assignment ID {assignment_id}")
        
        # Step 6: Apply cache invalidation pattern
        logger.debug("Invalidating cache after contact creation and assignment...")
        try:
            client.cache.invalidate_pattern("tenancy.contacts")
            client.cache.invalidate_pattern("tenancy.contact_assignments")
            client.cache.invalidate_pattern("tenancy.tenants")
        except Exception as cache_error:
            logger.warning(f"Cache invalidation failed after contact creation: {cache_error}")
        
        # Step 7: Build comprehensive response
        result = {
            "success": True,
            "action": "created_and_assigned",
            "contact": {
                "id": contact_id,
                "name": created_contact["name"],
                "email": created_contact.get("email", ""),
                "phone": created_contact.get("phone", ""),
                "title": created_contact.get("title", ""),
                "organization": created_contact.get("organization", ""),
                "url": created_contact.get("url", ""),
                "display_url": created_contact.get("display_url", "")
            },
            "tenant": {
                "id": tenant_id,
                "name": tenant_obj["name"],
                "slug": tenant_obj.get("slug", "")
            },
            "role": {
                "id": role_id,
                "name": role_obj["name"],
                "slug": role_obj.get("slug", "")
            },
            "assignment": {
                "id": assignment_id,
                "object_type": "tenancy.tenant",
                "object_id": tenant_id,
                "url": created_assignment.get("url", "")
            },
            "dry_run": False
        }
        
        logger.info(f"✅ Contact management complete: '{contact_name}' assigned to '{tenant_obj['name']}' as '{role_obj['name']}'")
        return result
        
    except Exception as e:
        logger.error(f"Failed to create contact for tenant {tenant_name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


# TODO: Implement advanced contact management tools
# - netbox_automate_contact_lifecycle
# - netbox_automate_contact_roles
# - netbox_manage_multi_tenant_contacts
# - netbox_integrate_contact_communication
# - netbox_audit_contact_compliance