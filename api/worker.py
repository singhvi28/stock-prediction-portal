from celery import Celery
import os
from dotenv import load_dotenv

load_dotenv()

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672//")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "worker",
    broker=RABBITMQ_URL,
    backend=REDIS_URL,
    include=['tasks']
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    task_routes={
        'tasks.process_payment': {'queue': 'payments'},
        'tasks.predict_task': {'queue': 'ml'},
        'tasks.cleanup_stuck_tasks': {'queue': 'payments'}, # Run cleanup on payments worker (lightweight)
    },
    beat_schedule={
        'cleanup-every-hour': {
            'task': 'tasks.cleanup_stuck_tasks',
            'schedule': 3600.0, # 60 minutes
        },
    }
)
