# =================================================================
# STAGE 1: De "Builder" - Installeert dependencies en compileert
# =================================================================
# Gebruik een volledige Python image die de nodige build-tools bevat
FROM python:3.11 AS builder

# Voorkom interactieve prompts tijdens apt-installaties
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# --- Optimaliseer APT & Caching ---
# Voer apt-get update en install in één RUN-commando uit om caching te optimaliseren.
# Gebruik NOOIT 'apt-get upgrade'. Installeer alleen wat strikt noodzakelijk is.
# Ruim de apt-cache direct op in dezelfde laag om de image-grootte te beperken.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# --- Optimaliseer PIP & Caching ---
# Kopieer éérst alleen de dependency-bestanden.
# Zolang deze bestanden niet wijzigen, wordt de langzame 'pip install'-laag
# uit de cache gehaald, zelfs als je je eigen code aanpast.
COPY requirements.txt pyproject.toml ./

# Installeer de Python dependencies. --no-cache-dir verkleint de layer size.
RUN pip install --no-cache-dir -r requirements.txt

# Installeer het project zelf in development mode
RUN pip install --no-cache-dir -e .

# =================================================================
# STAGE 2: De "Final Image" - Lichtgewicht en Productie-klaar
# =================================================================
# Start vanaf een minimale, schone en veilige 'slim' image.
FROM python:3.11-slim

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Kopieer alleen de geïnstalleerde packages uit de 'builder' stage.
# De build-tools en andere ballast blijven achter.
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Kopieer nu pas de applicatiecode. Dit is de laag die het vaakst verandert
# en staat daarom bewust als een van de laatste stappen.
COPY . .

# Maak een niet-root gebruiker aan om de applicatie te draaien.
# Dit is een cruciale security best practice.
RUN useradd --create-home --uid 1000 appuser
USER appuser

# Expose ports
# - 8000: MCP Streamable HTTP
# - 8080: Health endpoints
EXPOSE 8000 8080

# Health check - gebruik /healthz voor liveness probe (altijd beschikbaar)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    NETBOX_MCP_TRANSPORT=streamable-http \
    NETBOX_MCP_HOST=0.0.0.0 \
    NETBOX_MCP_PORT=8000 \
    NETBOX_MCP_PATH=/mcp

# Commando om de applicatie te starten
CMD ["python", "main.py"]