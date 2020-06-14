from core.scripts.update_elo import update_elo
from core.scripts.run_training import run_training
from core.scripts.compact_examples import compact_examples
from core.scripts.upload_examples import upload_examples
from celery import shared_task
from django.conf import settings


@shared_task()
def task_update_elo():
    update_elo()


@shared_task()
def task_run_training():
    run_training()


@shared_task()
def task_compact_examples():
    compact_examples()


if settings.CLOUD_STORAGE:
    @shared_task()
    def task_upload_examples():
        upload_examples()


@shared_task()
def task_upload_examples():
    upload_examples()