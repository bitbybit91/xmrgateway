#!/usr/bin/env bash
# backup.sh - Backup CryptoInvest database and website files
set -euo pipefail

BACKUP_BASE="/var/backups/cryptoinvest"
WEB_ROOT="/var/www/cryptoinvest"
DB_NAME="cryptoinvest"
RETENTION_DAYS=7
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_BASE}/${TIMESTAMP}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting backup..."

# Create backup directory
mkdir -p "$BACKUP_DIR"

# 1. Database backup
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backing up database '$DB_NAME'..."
mysqldump --single-transaction --quick --lock-tables=false "$DB_NAME" > "${BACKUP_DIR}/database.sql"
gzip "${BACKUP_DIR}/database.sql"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Database backup complete: ${BACKUP_DIR}/database.sql.gz"

# 2. Website files backup (exclude temp/cache files)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backing up website files..."
tar -czf "${BACKUP_DIR}/website.tar.gz" \
    --exclude="${WEB_ROOT}/public/cache" \
    --exclude="${WEB_ROOT}/public/tmp" \
    -C "$(dirname "$WEB_ROOT")" \
    "$(basename "$WEB_ROOT")"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Website backup complete: ${BACKUP_DIR}/website.tar.gz"

# 3. Remove old backups
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Removing backups older than ${RETENTION_DAYS} days..."
find "$BACKUP_BASE" -maxdepth 1 -type d -mtime +${RETENTION_DAYS} -print -exec rm -rf {} \;

# 4. Summary
DB_SIZE=$(du -sh "${BACKUP_DIR}/database.sql.gz" | cut -f1)
WEB_SIZE=$(du -sh "${BACKUP_DIR}/website.tar.gz" | cut -f1)
BACKUP_COUNT=$(find "$BACKUP_BASE" -maxdepth 1 -type d | tail -n +2 | wc -l)

echo ""
echo "===== Backup Summary ====="
echo "Timestamp:    $TIMESTAMP"
echo "Directory:    $BACKUP_DIR"
echo "Database:     database.sql.gz ($DB_SIZE)"
echo "Website:      website.tar.gz ($WEB_SIZE)"
echo "Total backups kept: $BACKUP_COUNT"
echo "=========================="
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backup completed successfully."
