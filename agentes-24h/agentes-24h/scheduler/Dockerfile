FROM python:3.12-slim

LABEL maintainer="agentes-24h"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY beat_schedule.py .

RUN useradd -m -u 1001 scheduler
USER scheduler

CMD ["celery", "-A", "beat_schedule", "beat", "--loglevel=info", "--schedule=/tmp/celerybeat-schedule"]
