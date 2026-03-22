FROM python:3.12-slim

LABEL maintainer="agentes-24h"

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

RUN useradd -m -u 1001 mcp
USER mcp

# MCP usa stdio – não expõe porta HTTP
CMD ["python", "-u", "server.py"]
