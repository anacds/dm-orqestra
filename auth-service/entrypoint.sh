#!/bin/bash
set -e

echo "Waiting for database to be ready..."
until PGPASSWORD=orqestra_password psql -h db -U orqestra -d postgres -c '\q' 2>/dev/null; do
  echo "Database is unavailable - sleeping"
  sleep 1
done

echo "Creating database if it doesn't exist (idempotent)..."
if ! PGPASSWORD=orqestra_password psql -h db -U orqestra -d postgres -tc "SELECT 1 FROM pg_database WHERE datname = 'auth_service'" | grep -q 1; then
  PGPASSWORD=orqestra_password psql -h db -U orqestra -d postgres -c "CREATE DATABASE auth_service"
  echo "Database 'auth_service' created"
else
  echo "Database 'auth_service' already exists"
fi

echo "Verifying database connection..."
until PGPASSWORD=orqestra_password psql -h db -U orqestra -d auth_service -c '\q' 2>/dev/null; do
  echo "Waiting for database 'auth_service' to be ready..."
  sleep 1
done

echo "Running database migrations..."
cd /app
alembic upgrade head

echo "Migrations completed successfully!"
echo "Starting server..."

exec uvicorn main:app --host 0.0.0.0 --port 8002

