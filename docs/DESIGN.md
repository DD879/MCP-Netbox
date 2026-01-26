Design Document: NetBox Read/Write MCP Server
1. Visie en Doelstelling
Dit document beschrijft het ontwerp voor een Read/Write Model Context Protocol (MCP) Server voor NetBox. Het doel is om een robuuste, veilige en conversationele interface te bieden voor het lezen én muteren van data in een NetBox (Cloud) instance.

De primaire doelstelling is om als een robuuste bouwsteen te dienen in een breder automation-ecosysteem, aangestuurd door een orchestrator. Deze server biedt een pure, agnostische interface voor NetBox operaties zonder kennis van de databron. De server zal vanaf de start ontworpen worden met zowel lees- als schrijfmogelijkheden in het achterhoofd.

2. Kernprincipes
Idempotentie is Cruciaal: Elke schrijfactie (tool) moet idempotent zijn. Een tool die tweemaal met dezelfde parameters wordt aangeroepen, moet hetzelfde eindresultaat opleveren als wanneer deze eenmaal wordt aangeroepen, zonder fouten of ongewenste duplicaten te creëren. Tools zoals netbox_ensure_device_exists zijn hier een perfect voorbeeld van.
Veiligheid Voorop (Safety First): Omdat deze MCP destructieve acties kan uitvoeren, moeten er ingebouwde veiligheidsmechanismen zijn. Dit omvat een 'dry-run' modus en een expliciete bevestigingsparameter voor alle schrijfacties.
API-First Benadering: De kernlogica wordt geïsoleerd in een netbox_client.py. Deze client is een directe, goed geteste wrapper rond de NetBox REST API en de pynetbox library, en vormt de fundering van de server.
Atomische Operaties: MCP-tools moeten, waar mogelijk, volledige, logische handelingen uitvoeren. Een tool om een device met interfaces aan te maken, moet ofwel volledig slagen, ofwel volledig falen en de state terugdraaien, zonder een half-geconfigureerd object achter te laten.
Modulaire Architectuur: De server volgt een modulaire opbouw:
Configuratie (config.py): Gescheiden en hiërarchisch.
Client (netbox_client.py): Verantwoordelijk voor alle API-interactie.
Server (server.py): Bevat de MCP-tool definities en de HTTP-server.
Containerisatie (Dockerfile): Voor reproduceerbare deployments.
3. Componenten Architectuur
3.1. netbox_client.py
Deze client zal de pynetbox Python library wrappen om de interactie met de NetBox API te vereenvoudigen en te standaardiseren.

Initialisatie: Accepteert NetBox URL, token en configuratie-object.
Read-methodes: Functies voor alle benodigde GET-operaties (get_device, get_ip_address, get_prefix, get_vlan, etc.). Deze methodes moeten de krachtige filtermogelijkheden van de NetBox API exposeren.
Write-methodes:
create_object(type, data): Een generieke functie voor het aanmaken van objecten.
update_object(object): Gebruikt de .save() methode van pynetbox.
delete_object(object): Gebruikt de .delete() methode van pynetbox.
Idempotente "Ensure" Methodes: Hoger-niveau functies die de kern van de R/W-logica bevatten.
ensure_device(name, device_type, site): Zoekt een device. Als het bestaat, geeft het terug. Zo niet, maakt het aan.
ensure_ip_address(address, status): Zorgt ervoor dat een IP-adres object bestaat.
assign_ip_to_interface(device, interface_name, ip_address): De meest complexe logica, die relaties legt.
Error Handling: Vertaalt pynetbox exceptions naar duidelijke, consistente NetBoxError exceptions.
3.2. server.py
De kern van de MCP server. Bevat de tool-definities.

Read-Only Tools (Voorbeelden):

netbox_get_device(name: str, site: str)
netbox_list_devices(filters: dict)
netbox_find_ip(address: str)
netbox_get_vlan_by_name(name: str, site: str)
netbox_get_device_interfaces(device_name: str)
Read/Write Tools (Voorbeelden):

netbox_create_device(name: str, device_type: str, role: str, site: str, confirm: bool = False)
netbox_update_device_status(device_name: str, status: str, confirm: bool = False)
netbox_assign_ip_to_interface(device_name: str, interface_name: str, ip_address: str, confirm: bool = False)
netbox_delete_device(device_name: str, confirm: bool = False)
Agnostische Data Processing: Tools die generieke device-objecten accepteren en deze naar de juiste state in NetBox brengen. Deze tools maken geen aannames over de databron en verwachten dat data preprocessing door de orchestrator is uitgevoerd.
3.3. Write Operation Strategy
Dit is het meest kritieke onderdeel van het ontwerp.

Confirmation Parameter: Elke tool die data muteert of verwijdert, moet een confirm: bool = False parameter hebben. De tool mag geen schrijfactie uitvoeren tenzij confirm=True. Dit is een essentiële veiligheidsmaatregel voor gebruik met LLM's.
Dry-Run Modus: Een globale configuratie-optie (--dry-run flag of NETBOX_DRY_RUN=true env var) die de server in een modus zet waarbij alle schrijfacties worden gelogd alsof ze zijn uitgevoerd, maar er geen daadwerkelijke API-calls worden gedaan.
Gedetailleerde Logging: Elke schrijfactie (create, update, delete) moet een gedetailleerde log-entry genereren met informatie over wat er is gewijzigd, met welke data, en wat het resultaat was.
Response Format: Een succesvolle schrijfactie geeft het gewijzigde of aangemaakte object terug. Dit stelt de LLM in staat om de succesvolle mutatie te verifiëren. Bijvoorbeeld: {"status": "success", "action": "created", "object": {...netbox_device...}}.
3.4. Configuratie en Deployment
config.py: Zal NETBOX_URL en NETBOX_TOKEN als vereiste variabelen hebben. Ondersteunt YAML/TOML en environment-variabelen.
Dockerfile: Een multi-stage Dockerfile die resulteert in een kleine, veilige image die als non-root gebruiker draait.
Health Checks: Kubernetes-style health checks (/healthz, /readyz) die de bereikbaarheid van de NetBox API valideren in de readyz probe.
