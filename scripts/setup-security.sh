#!/bin/bash
#===============================================================================
# setup-security.sh - Полная установка системы безопасности
# Использование: sudo ./setup-security.sh
#===============================================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PROJECT_DIR="/opt/news-assistant-bot"

echo "=========================================="
echo "  Установка системы безопасности"
echo "  News Assistant Bot"
echo "=========================================="
echo ""

# Проверка root
if [ "$EUID" -ne 0 ]; then 
    echo "Запустите от root: sudo ./setup-security.sh"
    exit 1
fi

# Создание директорий
echo -e "${CYAN}[1/7]${NC} Создание директорий..."
mkdir -p "$PROJECT_DIR"/{data,logs,backups/db,backups/env}
chmod 700 "$PROJECT_DIR/backups"

# Установка зависимостей
echo -e "${CYAN}[2/7]${NC} Установка пакетов..."
apt-get update
apt-get install -y ufw fail2ban sqlite3 gzip

# Права на скрипты
echo -e "${CYAN}[3/7]${NC} Установка прав на скрипты..."
chmod +x "$PROJECT_DIR/scripts/"*.sh
chmod +x "$PROJECT_DIR/security/"*.sh

# Настройка .env
echo -e "${CYAN}[4/7]${NC} Настройка .env..."
if [ ! -f "$PROJECT_DIR/.env" ]; then
    if [ -f "$PROJECT_DIR/.env.example" ]; then
        cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
        echo -e "${YELLOW}[!]${NC} Создан .env из .env.example - заполните реальными значениями!"
    fi
fi
if [ -f "$PROJECT_DIR/.env" ]; then
    chmod 600 "$PROJECT_DIR/.env"
    chown root:root "$PROJECT_DIR/.env"
fi

# UFW
echo -e "${CYAN}[5/7]${NC} Настройка UFW..."
"$PROJECT_DIR/security/ufw-setup.sh" <<< "yes" || true

# Fail2ban
echo -e "${CYAN}[6/7]${NC} Настройка Fail2ban..."
"$PROJECT_DIR/security/fail2ban-setup.sh" || true

# Crontab
echo -e "${CYAN}[7/7]${NC} Настройка Crontab..."
CRON_FILE="$PROJECT_DIR/security/crontab-backup.txt"
if [ -f "$CRON_FILE" ]; then
    # Добавляем к существующему crontab
    (crontab -l 2>/dev/null | grep -v news-assistant-bot; cat "$CRON_FILE") | crontab -
    echo -e "${GREEN}[✓]${NC} Crontab обновлен"
fi

# Первый бэкап
echo ""
echo "Создать первый бэкап? (y/n)"
read -r CREATE_BACKUP
if [ "$CREATE_BACKUP" = "y" ]; then
    if [ -f "$PROJECT_DIR/data/news_bot.db" ]; then
        "$PROJECT_DIR/scripts/backup.sh"
    else
        echo "БД не найдена, бэкап пропущен"
    fi
fi

# Итоги
echo ""
echo "=========================================="
echo -e "${GREEN}Установка завершена!${NC}"
echo "=========================================="
echo ""
echo "Следующие шаги:"
echo "1. Заполните .env реальными API ключами"
echo "2. Проверьте настройки: ./scripts/check-secrets.sh"
echo "3. Прочитайте: docs/security-checklist.md"
echo ""
echo "Статус компонентов:"
echo "  UFW:       $(ufw status | head -1)"
echo "  Fail2ban:  $(systemctl is-active fail2ban)"
echo "  Crontab:   $(crontab -l 2>/dev/null | grep -c backup) задач"
echo ""
