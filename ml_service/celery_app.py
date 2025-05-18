from celery import Celery
import logging
from logging.handlers import RotatingFileHandler
import redis
from celery.signals import celeryd_init
import os

# Get Redis configuration from environment with defaults
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_DB = os.getenv("REDIS_DB", "0")
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

@celeryd_init.connect
def validate_broker_connection(sender=None, conf=None, **kwargs):
    """Validate Redis connection at worker startup"""
    try:
        redis_client = redis.from_url(REDIS_URL)
        redis_client.ping()
        logger.info("Successfully connected to Redis")
    except redis.ConnectionError as e:
        logger.error(f"Cannot connect to Redis at {REDIS_URL}: {e}")
import os

# Настройка Celery с Redis
app = Celery(
    "ml_service",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["services.tasks"]  # В этом модуле будут определены задачи
)

# Конфигурация Celery
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # Максимальное время выполнения задачи (5 мин)
    task_soft_time_limit=240,  # Мягкий лимит (4 мин)
    task_acks_late=True,  # Подтверждение задачи после выполнения
    worker_prefetch_multiplier=1,  # Обрабатывать одну задачу за раз
)

# Более детальный мониторинг
logger = logging.getLogger('celery')
handler = RotatingFileHandler(
    "celery.log",
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
handler.setLevel(logging.INFO)
logger.addHandler(handler)