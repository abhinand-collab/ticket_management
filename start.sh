#!/bin/bash


python manage.py migrate &&
python manage.py create_admin &&
python manage.py collectstatic --noinput &&
celery -A config worker --loglevel=info &
celery -A config beat --loglevel=info &

gunicorn config.wsgi:application