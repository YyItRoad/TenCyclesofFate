#!/bin/bash
set -e

# Wait for the external database to be ready
echo "Waiting for external MySQL at host.docker.internal:3308..."
while ! nc -z host.docker.internal 3308; do
  sleep 1
done
echo "MySQL is up."

# Run the database initialization script
echo "Initializing database..."
python scripts/init_db.py

# Execute the main command (passed from CMD in Dockerfile)
exec "$@"