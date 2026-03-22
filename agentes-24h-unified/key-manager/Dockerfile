FROM python:3.12-slim

LABEL maintainer="agentes-24h"

# curl para healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Sem dependências externas – stdlib pura para manter a imagem mínima
COPY key_manager.py .

# Usuário não-root
RUN useradd -m -u 1001 keymanager
USER keymanager

EXPOSE 8100

CMD ["python", "-u", "key_manager.py"]
