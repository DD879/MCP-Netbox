"""
Nederlandse Bridget Messages

Authentic Dutch localization for Bridget's persona system, maintaining
professional yet approachable communication style typical of Dutch
business culture.
"""

MESSAGES = {
    # Core persona messages
    "welcome": "🦜 **Hallo! Bridget hier, jouw NetBox Infrastructure Guide!**",
    
    "intro": "*Leuk je te ontmoeten! Ik help je graag met het beheren van je NetBox infrastructuur.*",
    
    # Environment detection messages
    "environment_detected": {
        "production": "🚨 **PRODUCTIE OMGEVING GEDETECTEERD**",
        "staging": "🔧 **STAGING OMGEVING GEDETECTEERD**", 
        "demo": "🧪 **DEMO OMGEVING GEDETECTEERD**",
        "cloud": "☁️ **CLOUD OMGEVING GEDETECTEERD**",
        "unknown": "❓ **ONBEKENDE OMGEVING GEDETECTEERD**"
    },
    
    # Environment-specific details and guidance
    "environment_details": {
        "production": """**Productie NetBox Instance**
- URL: {netbox_url}
- Instance Type: {instance_type}
- Maximum veiligheidsprotocollen zijn actief""",
        
        "staging": """**Staging NetBox Instance** 
- URL: {netbox_url}
- Instance Type: {instance_type}
- Enhanced validation voor pre-productie testing""",
        
        "demo": """**Demo NetBox Instance**
- URL: {netbox_url}  
- Instance Type: {instance_type}
- Experimenteren en leren is aangemoedigd!""",
        
        "cloud": """**Cloud NetBox Instance**
- URL: {netbox_url}
- Instance Type: {instance_type}  
- Cloud-specific best practices worden toegepast""",
        
        "unknown": """**NetBox Instance**
- URL: {netbox_url}
- Instance Type: {instance_type}
- Conservatieve veiligheidsinstellingen actief"""
    },
    
    # Safety level guidance
    "safety_guidance": {
        "maximum": """🛡️ **MAXIMALE VEILIGHEID ACTIEF**
- 🚨 ALTIJD eerst dry-run mode gebruiken!
- Dubbele bevestiging VERPLICHT voor alle wijzigingen
- Audit logs worden bijgehouden
- Change management procedures volgen
- Backup verificatie aanbevolen""",
        
        "high": """⚠️ **HOGE VEILIGHEID MODUS**
- Dry-run mode sterk aanbevolen
- Dubbele bevestiging voor wijzigingen  
- Test scenarios grondig valideren
- Enhanced monitoring actief
- Pre-productie validatie vereist""",
        
        "standard": """✅ **STANDAARD VEILIGHEID**
- Dry-run mode aanbevolen maar niet verplicht
- Bevestigingen voor belangrijke wijzigingen
- Experimenteer vrij met nieuwe configuraties
- Basis audit logging actief
- Development-vriendelijke instellingen"""
    },
    
    # Operation-specific messages
    "operations": {
        "dry_run_recommended": "💡 **Tip**: Gebruik eerst `confirm=false` om te zien wat er zou gebeuren",
        "confirm_required": "⚠️ **Bevestiging vereist**: Stel `confirm=true` in om deze actie uit te voeren",
        "backup_recommended": "💾 **Aanbeveling**: Maak eerst een backup voordat je doorgaat",
        "change_management": "📋 **Change Management**: Documenteer deze wijziging volgens je procedures"
    },
    
    # Workflow guidance
    "workflows": {
        "device_installation": "Apparaat installatie workflow gestart",
        "network_configuration": "Netwerk configuratie workflow gestart", 
        "ip_management": "IP adres beheer workflow gestart",
        "tenant_onboarding": "Tenant onboarding workflow gestart"
    },
    
    # Error and warning messages
    "errors": {
        "api_connection": "⚠️ Kan geen verbinding maken met NetBox API",
        "insufficient_permissions": "⚠️ Onvoldoende rechten voor deze operatie",
        "validation_failed": "❌ Validatie gefaald: {details}",
        "conflict_detected": "⚠️ Conflict gedetecteerd: {conflict_info}",
        "operation_failed": "❌ Operatie mislukt: {error_message}"
    },
    
    # Success messages
    "success": {
        "operation_completed": "✅ Operatie succesvol uitgevoerd",
        "resource_created": "✅ Resource '{resource_name}' succesvol aangemaakt",
        "resource_updated": "✅ Resource '{resource_name}' succesvol bijgewerkt", 
        "resource_deleted": "✅ Resource '{resource_name}' succesvol verwijderd",
        "workflow_completed": "🎉 Workflow '{workflow_name}' succesvol afgerond"
    },
    
    # Context completion
    "context_complete": "**Context geïnitialiseerd!** Waarmee kan ik je vandaag helpen?",
    
    # Help and guidance
    "help": {
        "getting_started": "Begin met `netbox_list_all_sites` om je omgeving te verkennen",
        "safety_first": "Gebruik altijd dry-run mode (`confirm=false`) bij twijfel",
        "need_help": "Heb je hulp nodig? Vraag gerust naar specifieke workflows!",
        "best_practices": "Volg Nederlandse datacenter best practices voor optimale resultaten"
    },
    
    # Environment-specific warnings
    "warnings": {
        "production": {
            "write_operation": "🚨 **PRODUCTIE WAARSCHUWING**: Je staat op het punt een wijziging door te voeren in de productie omgeving. Zeker weten?",
            "bulk_operation": "⚠️ **BULK OPERATIE**: Dit beïnvloedt meerdere resources in productie. Extra voorzichtigheid geboden!",
            "irreversible": "🔒 **ONOMKEERBAAR**: Deze actie kan niet ongedaan gemaakt worden"
        },
        "staging": {
            "deployment_ready": "🚀 Ziet er goed uit voor deployment naar productie",
            "validation_needed": "✅ Validatie succesvol - klaar voor productie review"
        },
        "demo": {
            "learning_mode": "🎓 Demo modus - perfect voor het leren van NetBox workflows",
            "experiment_freely": "🧪 Experimenteer gerust - dit is een veilige omgeving"
        }
    },
    
    # Signature and branding
    "signature": "*Bridget - NetBox Infrastructure Guide | NetBox MCP v0.11.0+ | 🦜 LEGO Parrot Mascotte*",
    
    # Technical terminology (Dutch IT context)
    "technical_terms": {
        "rack": "rek",
        "device": "apparaat", 
        "interface": "interface",
        "vlan": "VLAN",
        "subnet": "subnet",
        "tenant": "tenant",
        "site": "site",
        "datacenter": "datacenter",
        "switch": "switch",
        "router": "router",
        "server": "server"
    }
}

# Format helpers for Dutch-specific formatting
FORMAT_HELPERS = {
    "plural": {
        # Dutch pluralization rules
        "device": {"singular": "apparaat", "plural": "apparaten"},
        "rack": {"singular": "rek", "plural": "rekken"},
        "site": {"singular": "site", "plural": "sites"},
        "vlan": {"singular": "VLAN", "plural": "VLANs"},
        "tenant": {"singular": "tenant", "plural": "tenants"}
    },
    
    "politeness": {
        # Dutch politeness levels
        "formal": "U",
        "informal": "je",
        "professional": "je"  # Dutch IT culture is generally informal but professional
    },
    
    "time_expressions": {
        "now": "nu",
        "today": "vandaag", 
        "yesterday": "gisteren",
        "tomorrow": "morgen",
        "this_week": "deze week",
        "next_week": "volgende week"
    }
}