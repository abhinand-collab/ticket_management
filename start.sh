#!/bin/bash

celery -A config worker --loglevel=info &
celery -A config beat --loglevel=info &

gunicorn config.wsgi:application