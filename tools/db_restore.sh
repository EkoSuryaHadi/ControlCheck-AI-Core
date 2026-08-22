#!/bin/bash
# ==============================================================================
# ControlCheck AI — PostgreSQL Database Restore Script
# Usage: ./tools/db_restore.sh <backup_file.sql.gz>
# ==============================================================================

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <path_to_backup.sql.gz>"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "ERROR: Backup file '${BACKUP_FILE}' does not exist."
    exit 1
fi

echo "[$(date)] WARNING: This will restore database '${POSTGRES_DB:-controlcheck}' from ${BACKUP_FILE}."
read -p "Are you sure you want to continue? (yes/no): " CONFIRM
if [ "${CONFIRM}" != "yes" ]; then
    echo "Restore operation cancelled."
    exit 0
fi

echo "[$(date)] Restoring database..."

if command -v docker >/dev/null 2>&1 && docker ps | grep -q controlcheck-postgres; then
    echo "Restoring into Docker container 'controlcheck-postgres'..."
    gunzip < "${BACKUP_FILE}" | docker exec -i controlcheck-postgres psql -U "${POSTGRES_USER:-controlcheck}" -d "${POSTGRES_DB:-controlcheck}"
else
    echo "Restoring using local psql..."
    gunzip < "${BACKUP_FILE}" | psql -U "${POSTGRES_USER:-controlcheck}" -d "${POSTGRES_DB:-controlcheck}"
fi

echo "[$(date)] Database restore completed successfully."
