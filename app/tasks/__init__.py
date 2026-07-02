from celery import Celery


def make_celery(app=None):
    from flask import Flask
    if app is None:
        app = Flask(__name__)
    celery = Celery(app.import_name)
    celery.conf.update(
        broker_url=app.config.get("CELERY_BROKER_URL", "redis://localhost:6379/1"),
        result_backend=app.config.get("REDIS_URL", "redis://localhost:6379/0"),
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="Asia/Colombo",
        task_always_eager=False,
    )
    return celery
