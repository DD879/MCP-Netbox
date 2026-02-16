"""
Bridget Auto-Context Prompts

MCP prompts for automatic context initialization and environment feedback.
Provides intelligent welcome messages and safety guidance based on detected environment.
"""

from typing import Dict, Any
from ..registry import mcp_prompt
from ..persona import (
    auto_initialize_bridget_context,
    get_context_manager,
    BridgetPersona
)
from ..dependencies import get_netbox_client
import logging

logger = logging.getLogger(__name__)


@mcp_prompt(
    name="bridget_welcome_and_initialize",
    description="Bridget's intelligent welcome with automatic environment detection and context setup"
)
async def bridget_welcome_and_initialize_prompt() -> str:
    """
    Bridget's main auto-initialization prompt.
    
    Automatically detects the NetBox environment, assigns appropriate safety levels,
    and provides context-specific welcome message and guidance.
    
    This prompt is ideal for first-time users or when you want to establish
    the proper context for your NetBox MCP session.
    
    Returns:
        Comprehensive welcome message with environment detection and safety guidance
    """
    try:
        # Get NetBox client for environment detection
        client = get_netbox_client()
        
        # Get context manager
        context_manager = get_context_manager()
        
        # Initialize context if not already done
        if not context_manager.is_context_initialized():
            context_state = context_manager.initialize_context(client)
            context_message = context_manager.generate_context_message(context_state)
        else:
            context_state = context_manager.get_context_state()
            context_message = "🦜 **Context reeds geïnitialiseerd**\n\nJe context is al actief voor deze sessie."
        
        # Generate comprehensive welcome with Bridget branding
        welcome_message = f"""🦜 **Welkom bij NetBox MCP - Powered by Bridget!**

*Hallo daar! Bridget hier, jouw persoonlijke NetBox Infrastructure Guide!*

Ik heb automatisch jouw omgeving geanalyseerd en alles klaargezet voor een veilige en efficiënte NetBox ervaring.

---

{context_message}

---

## 🚀 **Wat Kan Ik Voor Je Doen?**

Nu je context is ingesteld, kan ik je helpen met:

### **📋 Workflow Guidance:**
• **Device Installation** - Complete device installatie workflows
• **Network Planning** - IP address allocation en VLAN management
• **Infrastructure Management** - Rack space en capacity planning
• **Troubleshooting** - Diagnostics en issue resolution

### **🔧 Direct Tool Access:**
• **DCIM Tools** - 51 tools voor datacenter infrastructure
• **IPAM Tools** - 16 tools voor IP address management  
• **Virtualization** - 30 tools voor complete VM lifecycle
• **Tenancy** - 8 tools voor multi-tenant environments

### **💡 Bridget's Specialiteiten:**
• Intelligent error prevention en safety checks
• Context-aware recommendations based on je omgeving
• Stap-voor-stap guidance door complexe workflows
• Nederlandse én Engelse support voor internationale teams

---

## 🎯 **Aanbevolen Volgende Stappen:**

{_get_next_steps_recommendations(context_state)}

---

## 💬 **Hoe Communiceren We?**

**Vraag me gewoon:**
• "Bridget, kun je me helpen met..."
• "Welke tools heb ik nodig voor..."
• "Hoe installeer ik een nieuwe device?"
• "Kun je de beschikbare VLANs laten zien?"

**Of start direct een workflow:**
• Gebruik `install_device_in_rack` voor device installatie
• Gebruik `activate_bridget` voor een complete capabilities overview

---

**Ik sta klaar om je te helpen! Wat gaan we samen bouwen?** 🏗️

*Bridget - NetBox Infrastructure Guide | Auto-Context System v1.0 | NetBox MCP v0.11.0+*"""

        logger.info("Bridget welcome and initialization completed successfully")
        return welcome_message
        
    except Exception as e:
        logger.error(f"Error in bridget_welcome_and_initialize_prompt: {e}")
        return _get_fallback_welcome_message()


@mcp_prompt(
    name="bridget_environment_detected", 
    description="Get detailed information about your detected NetBox environment and safety settings"
)
async def bridget_environment_detected_prompt() -> str:
    """
    Show detailed environment detection results and safety configuration.
    
    Provides comprehensive information about the detected NetBox environment,
    active safety protocols, and environment-specific recommendations.
    
    Returns:
        Detailed environment analysis and safety guidance
    """
    try:
        context_manager = get_context_manager()
        
        if not context_manager.is_context_initialized():
            # Initialize context first
            client = get_netbox_client()
            context_state = context_manager.initialize_context(client)
        else:
            context_state = context_manager.get_context_state()
        
        if not context_state:
            return "🦜 **Bridget**: Context nog niet geïnitialiseerd. Gebruik eerst `bridget_welcome_and_initialize`."
        
        # Generate detailed environment report
        environment_report = f"""🦜 **Bridget's Environment Detection Report**

*Gedetailleerde analyse van jouw NetBox omgeving*

---

## 🔍 **Detection Results:**

**🏢 Environment Type:** {context_state.environment.upper()}  
**🛡️ Safety Level:** {context_state.safety_level.upper()}  
**📊 Instance Type:** {context_state.instance_type.title()}  
**🌐 NetBox URL:** {context_state.netbox_url or 'Niet beschikbaar'}  
**📍 NetBox Version:** {context_state.netbox_version or 'Niet gedetecteerd'}  
**⏰ Initialized:** {context_state.initialization_time.strftime('%d-%m-%Y %H:%M:%S')}

---

## 🛡️ **Active Safety Protocols:**

{_get_detailed_safety_info(context_state.safety_level)}

---

## 📋 **Environment Analysis:**

{_get_environment_analysis(context_state.environment)}

---

## ⚙️ **Configuration Details:**

{_get_configuration_details(context_state)}

---

## 🎯 **Recommended Practices:**

{_get_environment_best_practices(context_state.environment, context_state.safety_level)}

---

*Environment Detection by Bridget Auto-Context System | NetBox MCP v0.11.0+*"""
        
        return environment_report
        
    except Exception as e:
        logger.error(f"Error in bridget_environment_detected_prompt: {e}")
        return "🦜 **Bridget**: Er is een fout opgetreden bij het ophalen van environment informatie."


@mcp_prompt(
    name="bridget_safety_guidance",
    description="Get comprehensive safety guidance and best practices for your current NetBox environment"
)
async def bridget_safety_guidance_prompt() -> str:
    """
    Provide comprehensive safety guidance based on current environment.
    
    Offers detailed safety recommendations, confirmation patterns,
    and environment-specific operational guidelines.
    
    Returns:
        Comprehensive safety guidance and operational recommendations
    """
    try:
        context_manager = get_context_manager()
        context_state = context_manager.get_context_state()
        
        if not context_state:
            return "🦜 **Bridget**: Context niet geïnitialiseerd. Gebruik eerst `bridget_welcome_and_initialize`."
        
        safety_guidance = f"""🦜 **Bridget's Comprehensive Safety Guide**

*Veiligheidsrichtlijnen voor {context_state.environment} omgeving*

---

## 🛡️ **Safety Level: {context_state.safety_level.upper()}**

{_get_safety_level_explanation(context_state.safety_level)}

---

## 📋 **Operational Guidelines:**

### **✅ Before Any Operation:**
{_get_pre_operation_checklist(context_state.safety_level)}

### **🔧 During Operations:**
{_get_operation_guidelines(context_state.safety_level)}

### **🔍 After Operations:**
{_get_post_operation_checklist(context_state.safety_level)}

---

## 🚨 **Critical Safety Rules:**

{_get_critical_safety_rules(context_state.environment, context_state.safety_level)}

---

## 💡 **Bridget's Pro Tips:**

{_get_safety_pro_tips(context_state.environment)}

---

## 🆘 **Emergency Procedures:**

**Als er iets misgaat:**
1. **STOP** onmiddellijk met verdere operaties
2. **Documenteer** wat er is gebeurd
3. **Gebruik rollback** procedures waar mogelijk
4. **Vraag Bridget** om hulp met troubleshooting
5. **Informeer** team members bij productie issues

**Bridget's Emergency Commands:**
• `netbox_get_recent_changes` - Bekijk recente wijzigingen
• `netbox_create_journal_entry` - Documenteer incidents
• Gebruik dry-run mode om impact te analyseren

---

## 📞 **Get Help from Bridget:**

**Veiligheids-gerelateerde vragen:**
• "Bridget, is deze operatie veilig?"
• "Wat zijn de risico's van..."
• "Kun je deze wijziging valideren?"
• "Help me met rollback van..."

---

*Safety First - Altijd! | Bridget - NetBox Infrastructure Guide*"""
        
        return safety_guidance
        
    except Exception as e:
        logger.error(f"Error in bridget_safety_guidance_prompt: {e}")
        return "🦜 **Bridget**: Er is een fout opgetreden bij het ophalen van safety guidance."


# Helper functions for message generation

def _get_next_steps_recommendations(context_state) -> str:
    """Generate context-specific next steps recommendations."""
    if context_state.environment in ['production', 'unknown']:
        return """
🔒 **Production Environment - Start Carefully:**
1. **Explore first** - Use `netbox_list_all_*` tools to understand current state
2. **Plan changes** - Always use dry-run mode (`confirm=False`) first  
3. **Validate thoroughly** - Check dependencies and conflicts
4. **Execute safely** - Use `confirm=True` only after validation"""
    
    elif context_state.environment == 'demo':
        return """
🧪 **Demo Environment - Experiment Freely:**
1. **Try workflows** - Start with `install_device_in_rack` workflow
2. **Explore tools** - Use various `netbox_*` commands to learn
3. **Test scenarios** - Practice different configurations
4. **Learn patterns** - Get familiar with NetBox MCP capabilities"""
    
    else:
        return """
🎭 **Staging Environment - Test Systematically:**
1. **Validate workflows** - Test procedures before production use
2. **Check integrations** - Ensure tools work with your setup
3. **Document processes** - Create procedures for production
4. **Train team** - Use for team training and onboarding"""


def _get_detailed_safety_info(safety_level: str) -> str:
    """Get detailed safety information based on level."""
    safety_info = {
        'standard': """
**🟢 Standard Safety Mode:**
• Basis veiligheidscontroles actief
• Confirmatie vereist voor destructive operaties
• Automatische conflict detectie
• Standaard audit logging""",
        
        'high': """
**🟡 High Safety Mode:**
• Verhoogde veiligheidsvalidatie
• Confirmatie vereist voor alle write operaties
• Uitgebreide dependency checks
• Enhanced audit logging met details""",
        
        'maximum': """
**🔴 Maximum Safety Mode:**
• Maximale veiligheidsprotocollen
• Expliciete confirmatie voor ELKE wijziging
• Comprehensive validation en pre-checks
• Volledige audit trail met rollback info
• Dry-run VERPLICHT voor alle nieuwe operaties"""
    }
    
    return safety_info.get(safety_level, safety_info['maximum'])


def _get_environment_analysis(environment: str) -> str:
    """Get detailed environment analysis."""
    analysis = {
        'demo': """
**🧪 Demo/Development Environment:**
• Lokale of test instance gedetecteerd
• Veilig voor experimenteren en leren
• Geen impact op productie systemen
• Ideaal voor training en development""",
        
        'staging': """
**🎭 Staging/Test Environment:**
• Pre-productie test omgeving
• Gebruikt voor validatie en testing
• Mirror van productie configuratie
• Veilig voor workflow testing""",
        
        'cloud': """
**☁️ NetBox Cloud Instance:**
• Managed cloud service gedetecteerd
• Professional hosting met SLA
• Automatische backups en monitoring
• Shared responsibility security model""",
        
        'production': """
**🏭 Production Environment:**
• Live productie systeem gedetecteerd
• Kritieke business operations
• Maximale veiligheid vereist
• Impact op echte infrastructuur""",
        
        'unknown': """
**❓ Unknown Environment:**
• Automatische detectie gefaald
• Conservatieve veiligheidsaanpak
• Behandeld als productie omgeving
• Extra voorzichtigheid vereist"""
    }
    
    return analysis.get(environment, analysis['unknown'])


def _get_configuration_details(context_state) -> str:
    """Get configuration details."""
    return f"""
**Auto-Context:** {'✅ Enabled' if context_state.auto_context_enabled else '❌ Disabled'}
**Override Variables:** {_check_environment_overrides()}
**Session Duration:** {_calculate_session_duration(context_state.initialization_time)}
**User Preferences:** {len(context_state.user_preferences)} settings configured"""


def _check_environment_overrides() -> str:
    """Check for active environment variable overrides."""
    import os
    overrides = []
    
    if os.getenv('NETBOX_ENVIRONMENT'):
        overrides.append('NETBOX_ENVIRONMENT')
    if os.getenv('NETBOX_SAFETY_LEVEL'):
        overrides.append('NETBOX_SAFETY_LEVEL')
    if os.getenv('NETBOX_AUTO_CONTEXT'):
        overrides.append('NETBOX_AUTO_CONTEXT')
    
    return ', '.join(overrides) if overrides else 'None'


def _calculate_session_duration(init_time) -> str:
    """Calculate session duration."""
    from datetime import datetime
    duration = datetime.now() - init_time
    
    if duration.seconds < 60:
        return f"{duration.seconds} seconden"
    elif duration.seconds < 3600:
        return f"{duration.seconds // 60} minuten"
    else:
        return f"{duration.seconds // 3600} uur, {(duration.seconds % 3600) // 60} minuten"


def _get_environment_best_practices(environment: str, safety_level: str) -> str:
    """Get environment-specific best practices."""
    if environment == 'production':
        return """
🏭 **Production Best Practices:**
• Plan alle wijzigingen vooraf
• Gebruik maintenance windows
• Test eerst in staging
• Houd rollback procedures klaar
• Documenteer alle changes
• Monitor na wijzigingen"""
    
    elif environment == 'staging':
        return """
🎭 **Staging Best Practices:**
• Mirror productie zo goed mogelijk
• Test complete workflows end-to-end
• Valideer integrations en dependencies
• Documenteer test resultaten
• Gebruik voor team training"""
    
    else:
        return """
🧪 **Development Best Practices:**
• Experimenteer met nieuwe features
• Test edge cases en error scenarios
• Develop automation en scripts
• Learn NetBox MCP capabilities
• Share knowledge met team"""


def _get_safety_level_explanation(safety_level: str) -> str:
    """Get detailed safety level explanation."""
    explanations = {
        'standard': "Basis veiligheidsprotocollen voor development en testing omgevingen.",
        'high': "Verhoogde veiligheid voor staging en cloud omgevingen met extra validatie.",
        'maximum': "Maximale veiligheid voor productie met volledige validatie en audit requirements."
    }
    return explanations.get(safety_level, explanations['maximum'])


def _get_pre_operation_checklist(safety_level: str) -> str:
    """Get pre-operation checklist based on safety level."""
    if safety_level == 'maximum':
        return """
• Valideer doelomgeving en permissions
• Check dependencies en gerelateerde resources  
• Plan rollback strategy
• Gebruik ALTIJD dry-run mode eerst
• Documenteer intended changes
• Get approval voor kritieke wijzigingen"""
    elif safety_level == 'high':
        return """
• Check target resources bestaan
• Valideer permissions en access
• Use dry-run mode voor nieuwe operaties
• Review impact op gerelateerde systems"""
    else:
        return """
• Verify target resources
• Check basic permissions
• Consider using dry-run voor belangrijke changes"""


def _get_operation_guidelines(safety_level: str) -> str:
    """Get operation guidelines based on safety level."""
    if safety_level == 'maximum':
        return """
• Monitor operations real-time
• Stop bij eerste error of warning
• Valideer intermediate results
• Keep audit trail van alle actions
• Be prepared om te rollback"""
    elif safety_level == 'high':
        return """
• Monitor key operations
• Validate results voor next steps
• Stop als unexpected behavior occurs
• Maintain operation log"""
    else:
        return """
• Monitor important operations
• Validate critical results
• Document significant changes"""


def _get_post_operation_checklist(safety_level: str) -> str:
    """Get post-operation checklist based on safety level."""
    if safety_level == 'maximum':
        return """
• Verify alle intended changes applied
• Test functionality van affected systems
• Update documentation en procedures
• Create audit journal entries
• Inform stakeholders van completion
• Monitor for delayed effects"""
    elif safety_level == 'high':
        return """
• Verify changes applied correctly
• Test basic functionality
• Update relevant documentation
• Create journal entry voor audit"""
    else:
        return """
• Verify changes successful
• Update documentation als needed"""


def _get_critical_safety_rules(environment: str, safety_level: str) -> str:
    """Get critical safety rules."""
    rules = [
        "🚨 **NEVER** use `confirm=True` without dry-run validation first",
        "🛡️ **ALWAYS** check dependencies before deleting resources",
        "📋 **DOCUMENT** all significant changes in journal entries"
    ]
    
    if environment in ['production', 'unknown']:
        rules.extend([
            "⏰ **PLAN** changes during maintenance windows",
            "📞 **COORDINATE** with team voor critical operations",
            "🔄 **PREPARE** rollback procedures before changes"
        ])
    
    return '\n'.join(f"{i+1}. {rule}" for i, rule in enumerate(rules))


def _get_safety_pro_tips(environment: str) -> str:
    """Get safety pro tips."""
    tips = [
        "💡 Use `netbox_list_all_*` tools om current state te verkennen",
        "🔍 Test new workflows in demo environment eerst",
        "📝 Keep een change log bij voor complex operations"
    ]
    
    if environment == 'production':
        tips.extend([
            "⚡ Gebruik batch operations voor efficiency en consistency",
            "📊 Monitor system performance na grote wijzigingen",
            "🎯 Focus op one change at a time voor betere control"
        ])
    
    return '\n'.join(f"• {tip}" for tip in tips)


def _get_fallback_welcome_message() -> str:
    """Get fallback welcome message if initialization fails."""
    return """🦜 **Bridget - NetBox Infrastructure Guide**

Welkom bij NetBox MCP! Er is een probleem opgetreden met automatische context detectie,
maar ik ben nog steeds hier om je te helpen.

🛡️ **Veilige Modus Actief:**
• Maximale veiligheidsprotocollen zijn geactiveerd
• Alle operaties vereisen expliciete confirmatie
• Gebruik altijd dry-run mode eerst

💬 **Hoe Kan Ik Helpen:**
• Vraag me om specific NetBox tools
• Use `activate_bridget` voor mijn volledige capabilities
• Ask voor guidance bij any NetBox operations

*Bridget - Je Trusted NetBox Infrastructure Guide*"""