
# Dockerfile para el watcher de correos (Python)

FROM python:3.11-slim

# Instalar dependencias del sistema para pyzbar
RUN apt-get update && apt-get install -y libzbar0 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY email_watcher/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY email_watcher/ ./email_watcher/
COPY api/ ./api/
COPY db/ ./db/

# Si tienes archivos de configuración, descomenta la siguiente línea
# COPY .env ./

CMD ["python", "-m", "email_watcher.watcher_main"]
