#!/bin/sh

# Exit immediately if any command fails
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting the FastAPI server..."
exec "$@"