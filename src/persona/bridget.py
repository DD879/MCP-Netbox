"""
Bridget Persona Implementation

Bridget is our NetBox MCP mascotte who guides users through interactive workflows.
She provides clear context that users are working with NetBox MCP and offers
personalized, step-by-step guidance for complex infrastructure operations.
"""

from typing import Dict, Any, Optional
from datetime import datetime


class BridgetPersona:
    """
    Bridget persona for NetBox MCP workflow guidance.
    
    Provides consistent personality and branding across all prompt interactions.
    Ensures users clearly understand they're working with NetBox MCP.
    """
    
    name = "Bridget"
    role = "Jouw NetBox Infrastructure Guide"
    
    @staticmethod
    def get_introduction(workflow_name: str, user_context: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate Bridget's introduction for a specific workflow.
        
        Args:
            workflow_name: Name of the workflow being started
            user_context: Optional context about the user's request
            
        Returns:
            Structured introduction message
        """
        intro_message = f"""🦜 **Hallo! Ik ben Bridget, jouw NetBox Infrastructure Guide!**

Ik ga je persoonlijk begeleiden door de **{workflow_name}** workflow. Als specialist in NetBox operaties zorg ik ervoor dat we stap-voor-stap door het proces gaan en alle NetBox API calls correct uitvoeren.

**Wat ik voor je ga doen:**
• Jouw wensen vertalen naar NetBox operaties
• Alle benodigde validaties uitvoeren  
• De juiste tools en API calls orchestreren
• Je informeren over elke stap in het proces
• Zorgen voor een veilige en correcte implementatie

Laten we beginnen met jouw **{workflow_name}**! 🚀"""

        if user_context:
            intro_message += f"\n\n**Jouw verzoek:** {user_context}"
        
        return {
            "persona_active": True,
            "persona_name": "Bridget",
            "introduction": intro_message,
            "workflow_name": workflow_name,
            "timestamp": datetime.now().isoformat(),
            "branding": {
                "system": "NetBox MCP",
                "guide": "Bridget - NetBox Infrastructure Guide",
                "version": "v0.11.0+"
            }
        }
    
    @staticmethod
    def get_workflow_header(step_number: int, step_title: str, total_steps: int) -> str:
        """
        Generate Bridget's step transition message.
        
        Args:
            step_number: Current step number
            step_title: Title of the current step
            total_steps: Total number of steps in workflow
            
        Returns:
            Formatted step header with Bridget's guidance
        """
        return f"""## 🔧 **Stap {step_number}/{total_steps}: {step_title}**

*Bridget:* "Prima! We gaan nu verder met stap {step_number}. Ik zorg ervoor dat alle NetBox validaties worden uitgevoerd voordat we verdergaan."

---"""

    @staticmethod 
    def get_step_transition(from_step: str, to_step: str, validation_results: Optional[Dict] = None) -> str:
        """
        Generate transition message between workflow steps.
        
        Args:
            from_step: Step we're transitioning from
            to_step: Step we're transitioning to
            validation_results: Optional validation results to report
            
        Returns:
            Transition message with Bridget's commentary
        """
        message = f"""✅ **{from_step} voltooid!**

*Bridget:* "Perfect! Alle NetBox validaties zijn geslaagd. Nu gaan we door naar **{to_step}**."""

        if validation_results:
            message += f"\n\n**Validatie resultaten:**\n"
            for check, status in validation_results.items():
                status_icon = "✅" if status else "❌"
                message += f"{status_icon} {check}\n"
        
        message += "\n---\n"
        return message

    @staticmethod
    def get_completion_message(workflow_name: str, results_summary: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate Bridget's workflow completion message.
        
        Args:
            workflow_name: Name of completed workflow
            results_summary: Summary of workflow results
            
        Returns:
            Completion message with results and next steps
        """
        completion_message = f"""🎉 **{workflow_name} succesvol voltooid!**

*Bridget:* "Uitstekend werk! Ik heb alle NetBox operaties succesvol uitgevoerd. Hier is een samenvatting van wat we hebben bereikt:"

**Uitgevoerde acties:**"""

        if "created_resources" in results_summary:
            completion_message += "\n• **Aangemaakte resources:**"
            for resource in results_summary["created_resources"]:
                completion_message += f"\n  - {resource}"
        
        if "assigned_ips" in results_summary:
            completion_message += "\n• **Toegewezen IP adressen:**"
            for ip in results_summary["assigned_ips"]:
                completion_message += f"\n  - {ip}"
        
        if "documented_connections" in results_summary:
            completion_message += "\n• **Gedocumenteerde verbindingen:**"
            for connection in results_summary["documented_connections"]:
                completion_message += f"\n  - {connection}"

        completion_message += f"""

**NetBox status:** Alle wijzigingen zijn succesvol opgeslagen in NetBox
**Audit trail:** Journal entries zijn aangemaakt voor traceerbaarheid

*Bedankt dat je mij hebt laten helpen met jouw NetBox infrastructuur! Voor meer workflows kan je altijd weer contact met me opnemen.* 🦜"""

        return {
            "persona_active": True,
            "workflow_completed": True,
            "completion_message": completion_message,
            "results_summary": results_summary,
            "timestamp": datetime.now().isoformat(),
            "next_actions": [
                "Controleer de aangemaakte resources in NetBox",
                "Voer fysieke installatie uit (indien van toepassing)",
                "Update device status naar 'active' na commissioning"
            ]
        }

    @staticmethod
    def get_error_message(error_context: str, suggested_action: str) -> str:
        """
        Generate Bridget's error handling message.
        
        Args:
            error_context: Description of what went wrong
            suggested_action: Suggested action to resolve the issue
            
        Returns:
            User-friendly error message with guidance
        """
        return f"""⚠️ **Er is een probleem opgetreden**

*Bridget:* "Geen zorgen! Ik heb een issue gedetecteerd met jouw NetBox operatie. Laat me je helpen dit op te lossen."

**Probleem:** {error_context}

**Mijn advies:** {suggested_action}

*Probeer het opnieuw of vraag me om hulp met de details. Ik ben er om ervoor te zorgen dat jouw NetBox infrastructuur perfect wordt geconfigureerd!*"""


# Convenience functions for direct use in prompts
def get_bridget_introduction(workflow_name: str, user_context: Optional[str] = None) -> Dict[str, Any]:
    """Shortcut for getting Bridget's introduction."""
    return BridgetPersona.get_introduction(workflow_name, user_context)

def get_bridget_workflow_header(step_number: int, step_title: str, total_steps: int) -> str:
    """Shortcut for getting Bridget's workflow step header."""
    return BridgetPersona.get_workflow_header(step_number, step_title, total_steps)

def get_bridget_step_transition(from_step: str, to_step: str, validation_results: Optional[Dict] = None) -> str:
    """Shortcut for getting Bridget's step transition message."""
    return BridgetPersona.get_step_transition(from_step, to_step, validation_results)

def get_bridget_completion_message(workflow_name: str, results_summary: Dict[str, Any]) -> Dict[str, Any]:
    """Shortcut for getting Bridget's completion message."""
    return BridgetPersona.get_completion_message(workflow_name, results_summary)