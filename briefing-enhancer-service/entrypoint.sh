#!/bin/bash
set -e

# Credenciais via env vars com defaults sensatos (overridable via docker-compose)
DB_HOST="${POSTGRES_HOST:-db}"
DB_USER="${POSTGRES_USER:-orqestra}"
DB_PASS="${POSTGRES_PASSWORD:-orqestra_password}"
DB_NAME="briefing_enhancer"
DB_PORT="${POSTGRES_PORT:-5432}"

echo "Waiting for database to be ready..."
until PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c '\q' 2>/dev/null; do
  echo "Database is unavailable - sleeping"
  sleep 1
done

echo "Creating database if it doesn't exist (idempotent)..."
if ! PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -tc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1; then
  PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "CREATE DATABASE $DB_NAME"
  echo "Database '$DB_NAME' created"
else
  echo "Database '$DB_NAME' already exists"
fi

echo "Verifying database connection..."
until PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c '\q' 2>/dev/null; do
  echo "Waiting for database '$DB_NAME' to be ready..."
  sleep 1
done

echo "Running database migrations..."
cd /app
alembic upgrade head

echo "Migrations completed successfully!"
echo "Starting server..."

exec uvicorn main:app --host 0.0.0.0 --port 8001
