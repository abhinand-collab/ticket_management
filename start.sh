#!/bin/bash

python manage.py migrate &&
python manage.py create_admin &&
python manage.py collectstatic --noinput &&

celery -A config worker --loglevel=info --concurrency=1 --pool=solo &
celery -A config beat --loglevel=info &

gunicorn config.wsgi:application --workers 1