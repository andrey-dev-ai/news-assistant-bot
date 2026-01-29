#!/bin/bash
#===============================================================================
# restore.sh - Восстановление SQLite базы данных из бэкапа
# Использование: ./restore.sh [backup_file.db.gz]
#===============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# === Конфигурация сервера ===
# VPS: vps-ec36a417.vps.ovh.net (OVH Amsterdam)
# IP: 141.227.152.143
# OS: Ubuntu 25.04 | 4 vCores | 8GB RAM | 75GB SSD
PROJECT_DIR="/opt/news-assistant-bot"
DB_FILE="$PROJECT_DIR/data/news_bot.db"
BACKUP_DIR="$PROJECT_DIR/backups/db"
SERVICE_NAME="news-bot"

BACKUP_FILE="${1:-}"

echo "=========================================="
echo "  Восстановление базы данных"
echo "=========================================="
echo ""

# Проверка root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Запустите скрипт от root: sudo ./restore.sh${NC}"
    exit 1
fi

# Если файл не указан, показать список
if [ -z "$BACKUP_FILE" ]; then
    echo "Доступные бэкапы:"
    echo ""
    
    ls -lht "$BACKUP_DIR"/*.db.gz 2>/dev/null | head -10 | while read -r line; do
        echo "  $line"
    done
    
    echo ""
    echo "Использование: $0 <путь_к_бэкапу>"
    echo "Пример: $0 $BACKUP_DIR/news_bot_20240115_120000.db.gz"
    echo ""
    echo "Или используйте 'latest' для последнего бэкапа:"
    echo "  $0 latest"
    exit 0
fi

# Обработка 'latest'
if [ "$BACKUP_FILE" = "latest" ]; then
    BACKUP_FILE="$BACKUP_DIR/latest.db.gz"
fi

# Проверка существования бэкапа
if [ ! -f "$BACKUP_FILE" ]; then
    echo -e "${RED}ОШИБКА: Файл не найден: $BACKUP_FILE${NC}"
    exit 1
fi

echo -e "${CYAN}Бэкап:${NC} $BACKUP_FILE"
echo -e "${CYAN}Размер:${NC} $(ls -lh "$BACKUP_FILE" | awk '{print $5}')"
echo ""

# Проверка чексуммы
CHECKSUM_FILE="$BACKUP_FILE.sha256"
if [ -f "$CHECKSUM_FILE" ]; then
    echo "Проверка чексуммы..."
    if sha256sum -c "$CHECKSUM_FILE" --quiet 2>/dev/null; then
        echo -e "${GREEN}[✓]${NC} Чексумма совпадает"
    else
        echo -e "${RED}[!]${NC} Чексумма НЕ совпадает! Бэкап может быть поврежден."
        echo "Продолжить? (yes/no)"
        read -r CONTINUE
        if [ "$CONTINUE" != "yes" ]; then
            echo "Отменено."
            exit 1
        fi
    fi
else
    echo -e "${YELLOW}[!]${NC} Чексумма не найдена, пропуск проверки"
fi

# Проверка целостности архива
echo "Проверка архива..."
if gzip -t "$BACKUP_FILE" 2>/dev/null; then
    echo -e "${GREEN}[✓]${NC} Архив валидный"
else
    echo -e "${RED}[!]${NC} Архив поврежден!"
    exit 1
fi

# Предупреждение
echo ""
echo -e "${YELLOW}ВНИМАНИЕ: Текущая база данных будет заменена!${NC}"
echo ""

# Показать что будет восстановлено
TEMP_CHECK=$(mktemp)
gunzip -c "$BACKUP_FILE" > "$TEMP_CHECK"

echo "Информация о бэкапе:"
TABLES=$(sqlite3 "$TEMP_CHECK" ".tables" 2>/dev/null || echo "не удалось прочитать")
echo "  Таблицы: $TABLES"

for table in $TABLES; do
    COUNT=$(sqlite3 "$TEMP_CHECK" "SELECT COUNT(*) FROM $table;" 2>/dev/null || echo "?")
    echo "  - $table: $COUNT записей"
done

rm -f "$TEMP_CHECK"

echo ""
echo "Продолжить восстановление? (yes/no)"
read -r CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Отменено."
    exit 0
fi

# Остановка сервиса
echo ""
echo "Остановка сервиса..."
systemctl stop "$SERVICE_NAME" 2>/dev/null || true
sleep 2

# Бэкап текущей БД
if [ -f "$DB_FILE" ]; then
    CURRENT_BACKUP="$DB_FILE.pre-restore.$(date +%Y%m%d_%H%M%S)"
    cp "$DB_FILE" "$CURRENT_BACKUP"
    echo -e "${GREEN}[✓]${NC} Текущая БД сохранена: $CURRENT_BACKUP"
fi

# Распаковка и восстановление
echo "Распаковка бэкапа..."
TEMP_DB=$(mktemp)
gunzip -c "$BACKUP_FILE" > "$TEMP_DB"

# Проверка целостности распакованной БД
echo "Проверка целостности..."
INTEGRITY=$(sqlite3 "$TEMP_DB" "PRAGMA integrity_check;" 2>&1)
if [ "$INTEGRITY" != "ok" ]; then
    echo -e "${RED}[!]${NC} База данных в бэкапе повреждена!"
    echo "Результат: $INTEGRITY"
    rm -f "$TEMP_DB"
    
    # Восстановление предыдущей БД
    if [ -f "$CURRENT_BACKUP" ]; then
        mv "$CURRENT_BACKUP" "$DB_FILE"
    fi
    
    systemctl start "$SERVICE_NAME"
    exit 1
fi
echo -e "${GREEN}[✓]${NC} Целостность: OK"

# Замена БД
echo "Применение бэкапа..."
mv "$TEMP_DB" "$DB_FILE"
chmod 644 "$DB_FILE"
chown root:root "$DB_FILE"  # Или другой пользователь под которым работает бот

# Запуск сервиса
echo "Запуск сервиса..."
systemctl start "$SERVICE_NAME"
sleep 3

# Проверка статуса
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo -e "${GREEN}[✓]${NC} Сервис запущен"
else
    echo -e "${RED}[!]${NC} Сервис не запустился!"
    echo "Проверьте: journalctl -u $SERVICE_NAME -n 50"
    
    echo ""
    echo "Откатить к предыдущей БД? (yes/no)"
    read -r ROLLBACK
    
    if [ "$ROLLBACK" = "yes" ] && [ -f "$CURRENT_BACKUP" ]; then
        mv "$CURRENT_BACKUP" "$DB_FILE"
        systemctl start "$SERVICE_NAME"
        echo "Откат выполнен"
    fi
    exit 1
fi

# Финальная проверка
echo ""
echo "Проверка логов на ошибки..."
sleep 2
if journalctl -u "$SERVICE_NAME" --since "10 seconds ago" 2>/dev/null | grep -qi "error\|exception\|fail"; then
    echo -e "${YELLOW}[!]${NC} Обнаружены ошибки в логах, проверьте:"
    echo "  journalctl -u $SERVICE_NAME -f"
else
    echo -e "${GREEN}[✓]${NC} Ошибок не обнаружено"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}Восстановление завершено успешно!${NC}"
echo "=========================================="
echo ""
echo "Предыдущая БД сохранена: $CURRENT_BACKUP"
echo "Удалите её после проверки работоспособности."
