#!/bin/bash
#===============================================================================
# backup.sh - Бэкап SQLite базы данных
# Использование: ./backup.sh [--s3]
#===============================================================================

set -e

# === Конфигурация сервера ===
# VPS: vps-ec36a417.vps.ovh.net (OVH Amsterdam)
# IP: 141.227.152.143
# OS: Ubuntu 25.04 | 4 vCores | 8GB RAM | 75GB SSD
PROJECT_DIR="/opt/news-assistant-bot"
DB_FILE="$PROJECT_DIR/data/news_bot.db"
BACKUP_DIR="$PROJECT_DIR/backups/db"
RETENTION_DAYS=7
LOG_FILE="$PROJECT_DIR/logs/backup.log"

# S3 конфигурация (опционально)
S3_BUCKET="${S3_BACKUP_BUCKET:-}"
S3_PREFIX="news-bot-backups"
USE_S3="${1:-}"

# Создание директорий
mkdir -p "$BACKUP_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

# Функция логирования
log() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$message"
    echo "$message" >> "$LOG_FILE"
}

log "========== Начало бэкапа =========="

# Проверка существования БД
if [ ! -f "$DB_FILE" ]; then
    log "ОШИБКА: База данных не найдена: $DB_FILE"
    exit 1
fi

# Имя файла бэкапа
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/news_bot_${TIMESTAMP}.db"
BACKUP_COMPRESSED="$BACKUP_FILE.gz"

# Проверка целостности БД перед бэкапом
log "Проверка целостности БД..."
INTEGRITY=$(sqlite3 "$DB_FILE" "PRAGMA integrity_check;" 2>&1)
if [ "$INTEGRITY" != "ok" ]; then
    log "ОШИБКА: База данных повреждена!"
    log "Результат проверки: $INTEGRITY"
    exit 1
fi
log "Целостность БД: OK"

# Создание бэкапа через SQLite (безопасно для активной БД)
log "Создание бэкапа..."
sqlite3 "$DB_FILE" ".backup '$BACKUP_FILE'"

# Проверка размера
ORIGINAL_SIZE=$(stat -c%s "$DB_FILE" 2>/dev/null || stat -f%z "$DB_FILE")
BACKUP_SIZE=$(stat -c%s "$BACKUP_FILE" 2>/dev/null || stat -f%z "$BACKUP_FILE")

if [ "$BACKUP_SIZE" -lt "$((ORIGINAL_SIZE / 2))" ]; then
    log "ПРЕДУПРЕЖДЕНИЕ: Бэкап подозрительно маленький"
fi

# Сжатие
log "Сжатие бэкапа..."
gzip -9 "$BACKUP_FILE"

COMPRESSED_SIZE=$(stat -c%s "$BACKUP_COMPRESSED" 2>/dev/null || stat -f%z "$BACKUP_COMPRESSED")
log "Размер: $(numfmt --to=iec $ORIGINAL_SIZE 2>/dev/null || echo $ORIGINAL_SIZE) → $(numfmt --to=iec $COMPRESSED_SIZE 2>/dev/null || echo $COMPRESSED_SIZE)"

# Проверка что архив валидный
if ! gzip -t "$BACKUP_COMPRESSED" 2>/dev/null; then
    log "ОШИБКА: Архив поврежден!"
    rm -f "$BACKUP_COMPRESSED"
    exit 1
fi

# Создание чексуммы
sha256sum "$BACKUP_COMPRESSED" > "$BACKUP_COMPRESSED.sha256"
log "Чексумма создана: $BACKUP_COMPRESSED.sha256"

# Загрузка в S3 (опционально)
if [ "$USE_S3" = "--s3" ] && [ -n "$S3_BUCKET" ]; then
    log "Загрузка в S3: s3://$S3_BUCKET/$S3_PREFIX/"
    
    if command -v aws &> /dev/null; then
        aws s3 cp "$BACKUP_COMPRESSED" "s3://$S3_BUCKET/$S3_PREFIX/" --quiet
        aws s3 cp "$BACKUP_COMPRESSED.sha256" "s3://$S3_BUCKET/$S3_PREFIX/" --quiet
        log "S3 загрузка: OK"
        
        # Очистка старых бэкапов в S3 (старше 30 дней)
        aws s3 ls "s3://$S3_BUCKET/$S3_PREFIX/" | while read -r line; do
            file_date=$(echo "$line" | awk '{print $1}')
            file_name=$(echo "$line" | awk '{print $4}')
            if [ -n "$file_name" ]; then
                file_epoch=$(date -d "$file_date" +%s 2>/dev/null || echo 0)
                cutoff_epoch=$(date -d "30 days ago" +%s)
                if [ "$file_epoch" -lt "$cutoff_epoch" ]; then
                    aws s3 rm "s3://$S3_BUCKET/$S3_PREFIX/$file_name" --quiet
                    log "S3: удален старый бэкап $file_name"
                fi
            fi
        done
    else
        log "ПРЕДУПРЕЖДЕНИЕ: AWS CLI не установлен, S3 бэкап пропущен"
    fi
elif [ "$USE_S3" = "--s3" ]; then
    log "ПРЕДУПРЕЖДЕНИЕ: S3_BACKUP_BUCKET не задан в окружении"
fi

# Очистка старых локальных бэкапов
log "Очистка бэкапов старше $RETENTION_DAYS дней..."
DELETED_COUNT=$(find "$BACKUP_DIR" -name "*.db.gz" -mtime +$RETENTION_DAYS -delete -print | wc -l)
find "$BACKUP_DIR" -name "*.sha256" -mtime +$RETENTION_DAYS -delete 2>/dev/null || true
log "Удалено старых бэкапов: $DELETED_COUNT"

# Статистика
TOTAL_BACKUPS=$(find "$BACKUP_DIR" -name "*.db.gz" | wc -l)
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
log "Всего бэкапов: $TOTAL_BACKUPS, занято: $TOTAL_SIZE"

# Создание симлинка на последний бэкап
ln -sf "$BACKUP_COMPRESSED" "$BACKUP_DIR/latest.db.gz"

log "========== Бэкап завершен =========="
log "Файл: $BACKUP_COMPRESSED"
echo ""

# Код возврата
exit 0
