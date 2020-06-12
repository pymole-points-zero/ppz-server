# runserver
venv/bin/python manage.py runserver 0.0.0.0:8000
# run celery
celery worker -A ppz_server -B --loglevel=info