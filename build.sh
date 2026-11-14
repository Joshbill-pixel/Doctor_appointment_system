#!/usr/bin/env bash
# Render build step: install dependencies and collect static files.
# Database migrations run at startup (see render.yaml), when the database is reachable.
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt
python manage.py collectstatic --no-input
