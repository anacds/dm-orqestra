#!/bin/bash
set -e

echo "Waiting for database to be ready..."
until PGPASSWORD=orqestra_password psql -h db -U orqestra -d postgres -c '\q' 2>/dev/null; do
  echo "Database is unavailable - sleeping"
  sleep 1
done

echo "Creating database if it doesn't exist (idempotent)..."
if ! PGPASSWORD=orqestra_password psql -h db -U orqestra -d postgres -tc "SELECT 1 FROM pg_database WHERE datname = 'content_validation'" | grep -q 1; then
  PGPASSWORD=orqestra_password psql -h db -U orqestra -d postgres -c "CREATE DATABASE content_validation"
  echo "Database 'content_validation' created"
else
  echo "Database 'content_validation' already exists"
fi

echo "Verifying database connection..."
until PGPASSWORD=orqestra_password psql -h db -U orqestra -d content_validation -c '\q' 2>/dev/null; do
  echo "Waiting for database 'content_validation' to be ready..."
  sleep 1
done

echo "Running database migrations..."
cd /app
alembic upgrade head
echo "Migrations completed successfully!"

echo "Starting Content Validation Service..."
exec uvicorn main:app --host 0.0.0.0 --port 8004
