Project Roadmap: NetBox Read/Write MCP Server
Dit document beschrijft een iteratief ontwikkelplan om de NetBox R/W MCP Server te bouwen. De roadmap is opgedeeld in fases, waarbij elke fase een stabiel en testbaar product oplevert.

Fase 1: Fundering en Read-Only Kern (v0.1)
Doel: Een stabiele, read-only server die de basis legt voor toekomstige ontwikkeling.

Projectstructuur: Opzetten van de repository met pyproject.toml, .gitignore, README.md, etc.
Configuratie: Implementeren van config.py met ondersteuning voor NETBOX_URL en NETBOX_TOKEN.
NetBox Client (Read-Only): Implementeren van de netbox_client.py met pynetbox. Focus op GET-operaties: get_device, list_sites, get_ip_address, get_vlan.
Eerste MCP Tools: Implementeren van de eerste set read-only tools in server.py:
netbox_get_device
netbox_list_devices
netbox_get_site_by_name
Basis Docker-support: Creëren van een Dockerfile en docker-compose.yml voor een werkende, read-only container.
CI/CD Pipeline: Opzetten van een GitHub Actions workflow voor linting, testing en het bouwen van de Docker image.
Fase 2: Initiele Schrijfmogelijkheden en Veiligheid (v0.2)
Doel: De eerste, simpele schrijfacties introduceren met maximale veiligheid.

Write-methodes in Client: Uitbreiden van netbox_client.py met basis create, update, en delete methodes.
Veiligheidsmechanismen: Implementeren van de confirm: bool = False parameter in de write-tools en de globale dry-run modus.
Eerste Write Tools: Implementeren van de eerste, meest basale write-tools:
netbox_create_site(name: str, slug: str, confirm: bool = False)
netbox_create_manufacturer(name: str, slug: str, confirm: bool = False)
netbox_create_device_role(name: str, slug: str, color: str, confirm: bool = False)
Uitgebreide Logging: Implementeren van gedetailleerde logging voor alle schrijfacties.
Integratie Tests: Opzetten van de eerste integratietests die (in dry-run of tegen een test-instance) de schrijfacties valideren.
Fase 3: Geavanceerde R/W Operaties en Relaties (v0.3)
Doel: Complexe tools bouwen die objecten aan elkaar koppelen en de basis leggen voor enterprise-integratie.

Idempotente "Ensure" Logica: Implementeren van ensure_* methodes in de netbox_client.py.
Complexe MCP Tools: Implementeren van tools die relaties leggen:
netbox_create_device (met koppeling aan site, role, type)
netbox_create_interface_for_device
netbox_assign_ip_to_interface
Data Mapping Logica: Ontwikkelen van een strategie om enterprise-velden (zoals device type en vendor) te mappen naar NetBox-objecten (DeviceType, Manufacturer).
Kern Integratie Tool: Implementeren van enterprise device management tools. Dit is de belangrijkste mijlpaal van deze fase.
Fase 4: Enterprise Features en Integratie-gereedheid (v0.4)
Doel: De server robuuster maken en voorbereiden op productiegebruik en de daadwerkelijke koppeling.

Caching Systeem: Implementeren van een caching-laag voor veelgevraagde read-only data om de performance te verbeteren en de load op de NetBox API te verlagen.
Geavanceerde Zoek- en Filtertools: Implementeren van tools die de krachtige filtermogelijkheden van NetBox gebruiken, bijv. netbox_find_available_ips_in_prefix.
Verbeterde Health Checks: Uitbreiden van /readyz om de NetBox API-versie en status te controleren.
Documentatie: Schrijven van de initiële Wiki-documentatie voor installatie, configuratie en API-referentie.
Fase 5: Productie-waardigheid en Volledige Integratie (v1.0)
Doel: Een stabiele, goed gedocumenteerde v1.0 release en een werkende end-to-end enterprise-naar-NetBox workflow.

Performance Tuning: Optimaliseren van de client en de tools voor bulk-operaties.
Volledige Test-coverage: Zorgen voor hoge test-coverage, met name voor alle write- en ensure- paden.
End-to-End Workflow: Creëren van een voorbeeldscript of notebook dat laat zien hoe enterprise tools en NetBox MCP samenwerken om een NetBox-instance te synchroniseren.
Wiki-documentatie: Voltooien van de documentatie met uitgebreide voorbeelden, use-cases en best practices voor R/W-operaties.
Security Hardening: Een laatste review van alle security-aspecten.
Toekomstige Ideeën (Post-v1.0)
Webhook Support: Luisteren naar NetBox webhooks om acties te triggeren.
Custom Reports: Tools die complexe, samengestelde rapporten genereren uit NetBox data.
Service Modeling: Tools voor het modelleren van complete netwerkdiensten (bijv. het opzetten van een VPN met alle bijbehorende objecten).
Uitgebreide 'Diff' functionaliteit: Een tool die een (door enterprise tools ontdekt) device vergelijkt met zijn state in NetBox en een 'plan' genereert van de benodigde wijzigingen.
