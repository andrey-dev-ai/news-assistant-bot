#!/bin/bash
#===============================================================================
# ufw-setup.sh - Минимальный firewall для Telegram-бота
# Использование: sudo ./ufw-setup.sh
#===============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "  Настройка UFW для Telegram-бота"
echo "=========================================="
echo ""

# Проверка root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Запустите от root: sudo ./ufw-setup.sh${NC}"
    exit 1
fi

# Проверка UFW
if ! command -v ufw &> /dev/null; then
    echo "Установка UFW..."
    apt-get update && apt-get install -y ufw
fi

# Сброс к дефолту
echo "Сброс правил UFW..."
ufw --force reset

# Политика по умолчанию
echo "Настройка политик..."
ufw default deny incoming
ufw default allow outgoing

# SSH - КРИТИЧЕСКИ ВАЖНО!
echo "Разрешение SSH..."
ufw allow ssh
# Если SSH на нестандартном порту:
# ufw allow 2222/tcp

# Telegram Bot API использует HTTPS (исходящий) - уже разрешено
# Бот НЕ слушает входящие порты (polling режим)

# Опционально: если используете webhook режим
# ufw allow 443/tcp
# ufw allow 8443/tcp

# Включение UFW
echo ""
echo -e "${YELLOW}ВНИМАНИЕ: Убедитесь что SSH доступ настроен правильно!${NC}"
echo "Текущие правила:"
ufw show added
echo ""
echo "Включить UFW? (yes/no)"
read -r ENABLE

if [ "$ENABLE" = "yes" ]; then
    ufw --force enable
    echo ""
    ufw status verbose
    echo ""
    echo -e "${GREEN}[✓]${NC} UFW включен"
else
    echo "UFW не включен. Включите вручную: sudo ufw enable"
fi

echo ""
echo "=========================================="
echo "Полезные команды:"
echo "  ufw status          - текущий статус"
echo "  ufw status numbered - правила с номерами"
echo "  ufw delete N        - удалить правило N"
echo "  ufw disable         - выключить firewall"
echo "=========================================="
