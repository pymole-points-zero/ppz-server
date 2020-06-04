from core.scripts.update_elo import update_elo
from core.scripts.run_training import run_training
from celery import shared_task


@shared_task()
def task_update_elo():
    update_elo()


@shared_task()
def task_run_training():
    run_training()

