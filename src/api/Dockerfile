# Dockerfile para el backend (Python)

FROM python:3.11-slim

# Instalar dependencias del sistema para pyzbar
RUN apt-get update && apt-get install -y libzbar0 && rm -rf /var/lib/apt/lists/*


WORKDIR /app
ENV PYTHONPATH=/app

COPY api/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY api /app/api
## No copiar db para evitar conflicto de volumen, solo crear el directorio
COPY common /app/common

RUN mkdir -p /app/db
RUN mkdir -p /app/db
# Copiar solo los archivos de código fuente de db (sin db.sqlite3)
COPY db/*.py /app/db/
	# COPY db/__pycache__/ /app/db/__pycache__/

# Si tienes archivos de configuración, descomenta la siguiente línea
# COPY .env ./

EXPOSE 8000

CMD ["uvicorn", "api.backend:app", "--host", "0.0.0.0", "--port", "8000"]
