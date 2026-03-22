"""
beat_schedule.py
================
Configuração do Celery Beat – define quando cada tarefa recorrente é executada.

Os intervalos são lidos das variáveis de ambiente para facilitar ajuste sem rebuild.
"""

import os
from celery import Celery
from celery.schedules import crontab

BROKER_URL  = os.environ.get("CELERY_BROKER_URL",  "redis://redis:6379/0")
BACKEND_URL = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/1")

# Intervalos em segundos (com defaults conservadores)
INTERVAL_FIX_BUGS       = int(os.environ.get("TASK_FIX_BUGS_INTERVAL",       3600))   # 1h
INTERVAL_ADD_FEATURE    = int(os.environ.get("TASK_ADD_FEATURE_INTERVAL",     7200))   # 2h
INTERVAL_REFACTOR       = int(os.environ.get("TASK_REFACTOR_INTERVAL",       14400))   # 4h
INTERVAL_PEN_TEST       = int(os.environ.get("TASK_PEN_TEST_INTERVAL",       86400))   # 24h
INTERVAL_IMPROVE_SELF   = int(os.environ.get("TASK_IMPROVE_SELF_INTERVAL",   43200))   # 12h
INTERVAL_HEALTH_CHECK   = 300  # 5 minutos (fixo)

app = Celery("scheduler", broker=BROKER_URL, backend=BACKEND_URL)

app.conf.update(
    timezone="America/Sao_Paulo",
    enable_utc=True,
    beat_schedule={
        # ----------------------------------------------------------------
        # Correção de bugs – a cada N segundos
        # ----------------------------------------------------------------
        "fix-bugs-periodically": {
            "task": "tasks.fix_bugs",
            "schedule": INTERVAL_FIX_BUGS,
            "options": {"queue": "default"},
        },

        # ----------------------------------------------------------------
        # Adicionar features – a cada N segundos
        # ----------------------------------------------------------------
        "add-feature-periodically": {
            "task": "tasks.add_feature",
            "schedule": INTERVAL_ADD_FEATURE,
            "options": {"queue": "default"},
            "kwargs": {
                # Feature padrão se nenhuma for especificada
                "feature_description": (
                    "Melhore a cobertura de testes e adicione type hints "
                    "onde estão faltando."
                )
            },
        },

        # ----------------------------------------------------------------
        # Refatoração – a cada N segundos
        # ----------------------------------------------------------------
        "refactor-periodically": {
            "task": "tasks.refactor",
            "schedule": INTERVAL_REFACTOR,
            "options": {"queue": "default"},
        },

        # ----------------------------------------------------------------
        # Pentest – 1x por dia às 3h da manhã
        # ----------------------------------------------------------------
        "pen-test-daily": {
            "task": "tasks.pen_test",
            "schedule": crontab(hour=3, minute=0),
            "options": {"queue": "default"},
        },

        # ----------------------------------------------------------------
        # Melhoria do próprio sistema – 2x por dia
        # ----------------------------------------------------------------
        "improve-self-periodically": {
            "task": "tasks.improve_self",
            "schedule": INTERVAL_IMPROVE_SELF,
            "options": {"queue": "default"},
        },

        # ----------------------------------------------------------------
        # Health check – a cada 5 minutos
        # ----------------------------------------------------------------
        "health-check": {
            "task": "tasks.health_check",
            "schedule": INTERVAL_HEALTH_CHECK,
            "options": {"queue": "high_priority"},
        },
    },
)

if __name__ == "__main__":
    # Execução direta para debug
    print("Beat schedule configurado:")
    for name, config in app.conf.beat_schedule.items():
        print(f"  {name}: {config['task']} @ {config['schedule']}")
