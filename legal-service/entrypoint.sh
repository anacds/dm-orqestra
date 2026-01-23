#!/bin/bash
set -e

echo "Waiting for database to be ready..."
until PGPASSWORD=orqestra_password psql -h db -U orqestra -d postgres -c '\q' 2>/dev/null; do
  echo "Database is unavailable - sleeping"
  sleep 1
done

echo "Creating database if it doesn't exist (idempotent)..."
if ! PGPASSWORD=orqestra_password psql -h db -U orqestra -d postgres -tc "SELECT 1 FROM pg_database WHERE datname = 'legal_service'" | grep -q 1; then
  PGPASSWORD=orqestra_password psql -h db -U orqestra -d postgres -c "CREATE DATABASE legal_service"
  echo "Database 'legal_service' created"
else
  echo "Database 'legal_service' already exists"
fi

echo "Verifying database connection..."
until PGPASSWORD=orqestra_password psql -h db -U orqestra -d legal_service -c '\q' 2>/dev/null; do
  echo "Waiting for database 'legal_service' to be ready..."
  sleep 1
done

echo "Waiting for Weaviate to be ready..."
until curl -f http://weaviate:8080/v1/.well-known/ready 2>/dev/null; do
  echo "Weaviate is unavailable - sleeping"
  sleep 1
done

echo "Weaviate is ready!"

if [ "$CACHE_ENABLED" = "true" ]; then
  echo "Waiting for Redis to be ready..."
  until redis-cli -h redis -p 6379 ping 2>/dev/null; do
    echo "Redis is unavailable - sleeping"
    sleep 1
  done
  echo "Redis is ready!"
fi

echo "Running database migrations..."
cd /app
alembic upgrade head

echo "Migrations completed successfully!"

# Se argumentos foram passados, executa eles em vez do servidor
if [ $# -gt 0 ]; then
  echo "Executing command: $@"
  exec "$@"
else
  echo "Starting server..."
  exec uvicorn main:app --host 0.0.0.0 --port 8005
fi

