from ppz_server.core.scripts.update_elo import update_elo
from celery import shared_task


@shared_task()
def task_update_elo():
    update_elo()


