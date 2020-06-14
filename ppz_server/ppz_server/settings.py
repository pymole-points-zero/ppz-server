"""
Django settings for ppz_server project.

Generated by 'django-admin startproject' using Django 2.2.7.

For more information on this file, see
https://docs.djangoproject.com/en/2.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.2/ref/settings/
"""

import os
import keyring

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'hyq$6(7%!03$n5o%!7mv1hh$v4yf2g4*31^%)0j#*(g&@k2cm1'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # есть 2 способа записи приложения: путь к папке с приложением
    'core.apps.CoreConfig',      # и путь к конфигурации (предпочтительнее)
    'rest_framework'
]


REST_FRAMEWORK = {
    # Use Django's standard `django.contrib.auth` permissions,
    # or allow read-only access for unauthenticated users.
    'DEFAULT_PERMISSION_CLASSES': []
}


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ppz_server.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'ppz_server.wsgi.application'


# Database
# https://docs.djangoproject.com/en/2.2/ref/settings/#databases

# before the start set password in keyring
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'ppz',
        'HOST': '127.0.0.1',
        'PORT': '5432',
        'USER': 'postgres',
        'PASSWORD': keyring.get_password('ppz', 'postgres')
    }
}


# Password validation
# https://docs.djangoproject.com/en/2.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

AUTH_USER_MODEL = 'core.User'

# Internationalization
# https://docs.djangoproject.com/en/2.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.2/howto/static-files/

STATIC_URL = '/static/'


MATCHES = {
    'update_threshold': 0.55,
    'games_to_finish': 20
}


MATCH_SGF_PATH = os.path.join(BASE_DIR, 'sgf', 'matches')
MATCH_COLLECTION_SGF_PATH = os.path.join(BASE_DIR, 'sgf', 'match_collection')
TRAINING_SGF_PATH = os.path.join(BASE_DIR, 'sgf', 'training')
TRAINING_EXAMPLES_PATH = os.path.join(BASE_DIR, 'examples')
NETWORKS_PATH = os.path.join(BASE_DIR, 'networks')

TRAINING_CHUNK_SIZE = 100
TRAINING_PATH = '/home/pymole/PycharmProjects/ppz-training/'


CLOUD_TRAINING = False
CLOUD_STORAGE = False
AWS_ACCESS_KEY_ID = keyring.get_password('access_key', 'aws')
AWS_SECRET_ACCESS_KEY = keyring.get_password('secret_access_key', 'aws')

if CLOUD_STORAGE:
    import boto3
    S3 = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY_ID,
                      aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
    S3_NETWORKS_BUCKET_NAME = 'ppz-networks'
    S3_EXAMPLES_BUCKET_NAME = 'ppz-examples'


from celery.schedules import crontab
# app.conf.beat_schedule
CELERY_BEAT_SCHEDULE = {
    'elo-update': {
        'task': 'core.tasks.task_update_elo',
        'schedule': crontab(minute=0, hour='*/1'),
    },
    #
    # 'training': {
    #     'task': 'core.tasks.task_run_training',
    #     'schedule': crontab(minute=0, hour='*/3'),
    # },

    'compact-examples': {
        'task': 'core.tasks.task_compact_examples',
        'schedule': crontab(minute='*/1'),
    },
}

CELERY_BEAT_SCHEDULE['upload-examples'] = {
    'task': 'core.tasks.task_upload_examples',
    'schedule': crontab(minute='*/1'),
}

if CLOUD_STORAGE:
    CELERY_BEAT_SCHEDULE['upload-examples'] = {
        'task': 'core.tasks.task_upload_examples',
        'schedule': crontab(minute=0, hour='*/1'),
    }

CELERY_BROKER_URL = 'redis://localhost:6379'
CELERY_RESULT_BACKEND = 'redis://localhost:6379'
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TASK_SERIALIZER = 'json'
