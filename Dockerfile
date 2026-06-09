# CV Optimizer ATS — imagen para desplegar en Render, Hugging Face Spaces, Fly.io, etc.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Instalar dependencias primero (aprovecha la cache de capas de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el codigo de la aplicacion
COPY app ./app
COPY static ./static

# El host inyecta $PORT (Render). Hugging Face Spaces usa 7860 por defecto.
EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
