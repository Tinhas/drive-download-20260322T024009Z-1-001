FROM python:3.12-slim

LABEL maintainer="agentes-24h-final"

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instala dependências do gateway
COPY mcp-gateway/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copia os módulos de ferramentas do mcp-server
COPY mcp-server/ /app/mcp-server/

# Copia o código do gateway
COPY mcp-gateway/gateway.py /app/gateway.py

# Cria usuário não-root
RUN useradd -m -u 1001 gateway && \
    mkdir -p /data/repos /data/logs && \
    chown -R gateway:gateway /data /app

USER gateway

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# PYTHONPATH permite que gateway.py importe server.py do mcp-server
ENV PYTHONPATH=/app/mcp-server
CMD ["python", "-u", "/app/gateway.py"]
