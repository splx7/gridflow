from celery import Celery

from app.config import settings

celery_app = Celery(
    "gridflow",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_track_started=True,
    result_expires=86400,
    include=["app.worker.tasks", "app.worker.sensitivity_task", "app.worker.batch_task"],
)

celery_app.autodiscover_tasks(["app.worker"])
