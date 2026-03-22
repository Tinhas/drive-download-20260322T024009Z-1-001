FROM python:3.12-slim

LABEL maintainer="agentes-24h"

# Dependências de sistema: git (para commits), curl (healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependências Python primeiro (cache de camadas)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código dos workers e skills
COPY . .

# Criar usuário não-root
RUN useradd -m -u 1001 worker && \
    mkdir -p /data/repos /data/logs && \
    chown -R worker:worker /data /app

USER worker

# Configurar Git global (o repositório específico será configurado por git_utils.py)
RUN git config --global init.defaultBranch main && \
    git config --global safe.directory '*'

# Iniciar Celery worker
CMD ["celery", "-A", "tasks", "worker", \
     "--loglevel=info", \
     "--concurrency=2", \
     "--queues=default,high_priority", \
     "--hostname=worker@%h"]
