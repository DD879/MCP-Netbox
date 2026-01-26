"""
English Bridget Messages

International English localization for Bridget's persona system, maintaining
professional yet approachable communication suitable for global enterprise
environments.
"""

MESSAGES = {
    # Core persona messages
    "welcome": "🦜 **Hi! I'm Bridget, your NetBox Infrastructure Guide!**",
    
    "intro": "*Nice to meet you! I'm here to help you manage your NetBox infrastructure with expertise and care.*",
    
    # Environment detection messages
    "environment_detected": {
        "production": "🚨 **PRODUCTION ENVIRONMENT DETECTED**",
        "staging": "🔧 **STAGING ENVIRONMENT DETECTED**", 
        "demo": "🧪 **DEMO ENVIRONMENT DETECTED**",
        "cloud": "☁️ **CLOUD ENVIRONMENT DETECTED**",
        "unknown": "❓ **UNKNOWN ENVIRONMENT DETECTED**"
    },
    
    # Environment-specific details and guidance
    "environment_details": {
        "production": """**Production NetBox Instance**
- URL: {netbox_url}
- Instance Type: {instance_type}
- Maximum safety protocols are active""",
        
        "staging": """**Staging NetBox Instance** 
- URL: {netbox_url}
- Instance Type: {instance_type}
- Enhanced validation for pre-production testing""",
        
        "demo": """**Demo NetBox Instance**
- URL: {netbox_url}  
- Instance Type: {instance_type}
- Experimentation and learning encouraged!""",
        
        "cloud": """**Cloud NetBox Instance**
- URL: {netbox_url}
- Instance Type: {instance_type}  
- Cloud-specific best practices applied""",
        
        "unknown": """**NetBox Instance**
- URL: {netbox_url}
- Instance Type: {instance_type}
- Conservative safety settings active"""
    },
    
    # Safety level guidance
    "safety_guidance": {
        "maximum": """🛡️ **MAXIMUM SAFETY ACTIVE**
- 🚨 ALWAYS use dry-run mode first!
- Double confirmation REQUIRED for all changes
- Audit logs are maintained
- Follow change management procedures
- Backup verification recommended""",
        
        "high": """⚠️ **HIGH SAFETY MODE**
- Dry-run mode strongly recommended
- Double confirmation for changes  
- Thoroughly validate test scenarios
- Enhanced monitoring active
- Pre-production validation required""",
        
        "standard": """✅ **STANDARD SAFETY**
- Dry-run mode recommended but not required
- Confirmations for important changes
- Feel free to experiment with new configurations
- Basic audit logging active
- Development-friendly settings"""
    },
    
    # Operation-specific messages
    "operations": {
        "dry_run_recommended": "💡 **Tip**: Use `confirm=false` first to see what would happen",
        "confirm_required": "⚠️ **Confirmation required**: Set `confirm=true` to execute this action",
        "backup_recommended": "💾 **Recommendation**: Create a backup before proceeding",
        "change_management": "📋 **Change Management**: Document this change according to your procedures"
    },
    
    # Workflow guidance
    "workflows": {
        "device_installation": "Device installation workflow started",
        "network_configuration": "Network configuration workflow started", 
        "ip_management": "IP address management workflow started",
        "tenant_onboarding": "Tenant onboarding workflow started"
    },
    
    # Error and warning messages
    "errors": {
        "api_connection": "⚠️ Cannot connect to NetBox API",
        "insufficient_permissions": "⚠️ Insufficient permissions for this operation",
        "validation_failed": "❌ Validation failed: {details}",
        "conflict_detected": "⚠️ Conflict detected: {conflict_info}",
        "operation_failed": "❌ Operation failed: {error_message}"
    },
    
    # Success messages
    "success": {
        "operation_completed": "✅ Operation completed successfully",
        "resource_created": "✅ Resource '{resource_name}' created successfully",
        "resource_updated": "✅ Resource '{resource_name}' updated successfully", 
        "resource_deleted": "✅ Resource '{resource_name}' deleted successfully",
        "workflow_completed": "🎉 Workflow '{workflow_name}' completed successfully"
    },
    
    # Context completion
    "context_complete": "**Context initialized!** How can I assist you today?",
    
    # Help and guidance
    "help": {
        "getting_started": "Start with `netbox_list_all_sites` to explore your environment",
        "safety_first": "Always use dry-run mode (`confirm=false`) when in doubt",
        "need_help": "Need help? Feel free to ask about specific workflows!",
        "best_practices": "Follow infrastructure best practices for optimal results"
    },
    
    # Environment-specific warnings
    "warnings": {
        "production": {
            "write_operation": "🚨 **PRODUCTION WARNING**: You're about to make changes in the production environment. Are you sure?",
            "bulk_operation": "⚠️ **BULK OPERATION**: This affects multiple resources in production. Extra caution advised!",
            "irreversible": "🔒 **IRREVERSIBLE**: This action cannot be undone"
        },
        "staging": {
            "deployment_ready": "🚀 Looks good for production deployment",
            "validation_needed": "✅ Validation successful - ready for production review"
        },
        "demo": {
            "learning_mode": "🎓 Demo mode - perfect for learning NetBox workflows",
            "experiment_freely": "🧪 Feel free to experiment - this is a safe environment"
        }
    },
    
    # Signature and branding
    "signature": "*Bridget - NetBox Infrastructure Guide | NetBox MCP v0.11.0+ | 🦜 LEGO Parrot Mascotte*",
    
    # Technical terminology (International IT context)
    "technical_terms": {
        "rack": "rack",
        "device": "device", 
        "interface": "interface",
        "vlan": "VLAN",
        "subnet": "subnet",
        "tenant": "tenant",
        "site": "site",
        "datacenter": "data center",
        "switch": "switch",
        "router": "router",
        "server": "server"
    }
}

# Format helpers for English-specific formatting
FORMAT_HELPERS = {
    "plural": {
        # English pluralization rules
        "device": {"singular": "device", "plural": "devices"},
        "rack": {"singular": "rack", "plural": "racks"},
        "site": {"singular": "site", "plural": "sites"},
        "vlan": {"singular": "VLAN", "plural": "VLANs"},
        "tenant": {"singular": "tenant", "plural": "tenants"},
        "switch": {"singular": "switch", "plural": "switches"},
        "address": {"singular": "address", "plural": "addresses"}
    },
    
    "politeness": {
        # English politeness levels
        "formal": "you",
        "informal": "you",
        "professional": "you"  # English uses consistent "you"
    },
    
    "time_expressions": {
        "now": "now",
        "today": "today", 
        "yesterday": "yesterday",
        "tomorrow": "tomorrow",
        "this_week": "this week",
        "next_week": "next week"
    },
    
    "articles": {
        # English article usage
        "definite": "the",
        "indefinite_consonant": "a",
        "indefinite_vowel": "an"
    }
}