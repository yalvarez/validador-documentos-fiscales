# Dockerfile para el backend (Python)

FROM python:3.11-slim

# Instalar dependencias del sistema para pyzbar
RUN apt-get update && apt-get install -y libzbar0 && rm -rf /var/lib/apt/lists/*


WORKDIR /app
ENV PYTHONPATH=/app

COPY ../requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ../__init__.py ./
COPY . .

# Si tienes archivos de configuración, descomenta la siguiente línea
# COPY .env ./

EXPOSE 7000

CMD ["uvicorn", "api.backend:app", "--host", "0.0.0.0", "--port", "7000"]
