#!/bin/bash
# ==============================================================================
# ControlCheck AI — Automated PostgreSQL Database Backup Script
# Usage: ./tools/db_backup.sh [/path/to/backup_dir] [retention_days]
# ==============================================================================

set -euo pipefail

BACKUP_DIR="${1:-./var/backups}"
RETENTION_DAYS="${2:-14}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
FILENAME="controlcheck_backup_${TIMESTAMP}.sql.gz"
TARGET_PATH="${BACKUP_DIR}/${FILENAME}"

mkdir -p "${BACKUP_DIR}"

echo "[$(date)] Starting ControlCheck AI database backup..."

if command -v docker >/dev/null 2>&1 && docker ps | grep -q controlcheck-postgres; then
    echo "Dumping from Docker container 'controlcheck-postgres'..."
    docker exec -t controlcheck-postgres pg_dump -U "${POSTGRES_USER:-controlcheck}" "${POSTGRES_DB:-controlcheck}" | gzip -9 > "${TARGET_PATH}"
else
    echo "Dumping using local pg_dump..."
    pg_dump -U "${POSTGRES_USER:-controlcheck}" -d "${POSTGRES_DB:-controlcheck}" | gzip -9 > "${TARGET_PATH}"
fi

BACKUP_SIZE=$(du -h "${TARGET_PATH}" | cut -f1)
echo "[$(date)] Backup successfully saved to: ${TARGET_PATH} (Size: ${BACKUP_SIZE})"

# Retention Cleanup
echo "[$(date)] Cleaning up backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -name "controlcheck_backup_*.sql.gz" -mtime +"${RETENTION_DAYS}" -exec rm -f {} \;
echo "[$(date)] Database backup routine finished."
