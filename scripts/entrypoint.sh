#!/bin/sh
set -eu
python manage.py migrate --noinput
python manage.py bootstrap_superuser
python manage.py seed_roles
python manage.py collectstatic --noinput
exec "$@"
