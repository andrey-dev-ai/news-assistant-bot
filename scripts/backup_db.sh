#!/bin/bash
# ============================================
# AI ДЛЯ ДОМА — Скрипт бэкапа базы данных
# ============================================

# Настройки
DB_PATH="${DB_PATH:-./data/news_bot.db}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
KEEP_DAYS="${KEEP_DAYS:-7}"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция логирования
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARN:${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

# Проверка наличия базы данных
if [ ! -f "$DB_PATH" ]; then
    error "База данных не найдена: $DB_PATH"
    exit 1
fi

# Создание директории для бэкапов
mkdir -p "$BACKUP_DIR"

# Имя файла бэкапа с временной меткой
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
BACKUP_FILE="$BACKUP_DIR/news_bot_backup_$TIMESTAMP.db"

log "Начинаю бэкап базы данных..."
log "Источник: $DB_PATH"
log "Назначение: $BACKUP_FILE"

# Создание бэкапа через SQLite (безопасный способ)
if command -v sqlite3 &> /dev/null; then
    sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"
    BACKUP_METHOD="sqlite3 .backup"
else
    # Fallback на обычное копирование
    cp "$DB_PATH" "$BACKUP_FILE"
    BACKUP_METHOD="file copy"
fi

if [ $? -eq 0 ]; then
    # Получаем размер бэкапа
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log "Бэкап создан успешно ($BACKUP_METHOD)"
    log "Размер: $BACKUP_SIZE"

    # Создаём сжатую версию
    if command -v gzip &> /dev/null; then
        gzip -c "$BACKUP_FILE" > "$BACKUP_FILE.gz"
        GZIP_SIZE=$(du -h "$BACKUP_FILE.gz" | cut -f1)
        log "Сжатая версия: $BACKUP_FILE.gz ($GZIP_SIZE)"
    fi
else
    error "Ошибка создания бэкапа!"
    exit 1
fi

# Удаление старых бэкапов
log "Удаляю бэкапы старше $KEEP_DAYS дней..."
find "$BACKUP_DIR" -name "news_bot_backup_*.db" -mtime +$KEEP_DAYS -delete 2>/dev/null
find "$BACKUP_DIR" -name "news_bot_backup_*.db.gz" -mtime +$KEEP_DAYS -delete 2>/dev/null

# Статистика
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/news_bot_backup_*.db 2>/dev/null | wc -l)
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)

log "================================"
log "Бэкап завершён"
log "Всего бэкапов: $BACKUP_COUNT"
log "Общий размер директории: $TOTAL_SIZE"
log "================================"
