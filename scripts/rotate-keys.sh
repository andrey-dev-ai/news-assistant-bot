#!/bin/bash
#===============================================================================
# rotate-keys.sh - Процедура безопасной ротации API ключей
# Использование: ./rotate-keys.sh [anthropic|telegram|openai|all]
#===============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PROJECT_DIR="/opt/news-assistant-bot"
ENV_FILE="$PROJECT_DIR/.env"
BACKUP_DIR="$PROJECT_DIR/backups/env"
SERVICE_NAME="news-bot"

KEY_TYPE="${1:-}"

echo "=========================================="
echo "  Ротация API ключей"
echo "=========================================="
echo ""

# Проверка root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Запустите скрипт от root: sudo ./rotate-keys.sh${NC}"
    exit 1
fi

# Создание бэкапа .env
mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/.env.$(date +%Y%m%d_%H%M%S)"
cp "$ENV_FILE" "$BACKUP_FILE"
chmod 600 "$BACKUP_FILE"
echo -e "${GREEN}[✓]${NC} Бэкап создан: $BACKUP_FILE"

# Функция обновления ключа
update_key() {
    local key_name=$1
    local new_value=$2
    
    if grep -q "^${key_name}=" "$ENV_FILE"; then
        sed -i "s|^${key_name}=.*|${key_name}=${new_value}|" "$ENV_FILE"
    else
        echo "${key_name}=${new_value}" >> "$ENV_FILE"
    fi
}

# Функция ротации
rotate_key() {
    local key_name=$1
    local key_display=$2
    local get_url=$3
    
    echo ""
    echo -e "${CYAN}--- Ротация $key_display ---${NC}"
    echo ""
    echo "1. Получите новый ключ: $get_url"
    echo "2. Введите новый ключ (или Enter для пропуска):"
    echo ""
    read -r -s NEW_KEY
    
    if [ -n "$NEW_KEY" ]; then
        # Валидация формата
        case $key_name in
            "ANTHROPIC_API_KEY")
                if [[ ! "$NEW_KEY" =~ ^sk-ant- ]]; then
                    echo -e "${YELLOW}[!]${NC} Ключ не начинается с sk-ant-, проверьте формат"
                fi
                ;;
            "OPENAI_API_KEY")
                if [[ ! "$NEW_KEY" =~ ^sk- ]]; then
                    echo -e "${YELLOW}[!]${NC} Ключ не начинается с sk-, проверьте формат"
                fi
                ;;
            "TELEGRAM_BOT_TOKEN")
                if [[ ! "$NEW_KEY" =~ ^[0-9]+: ]]; then
                    echo -e "${YELLOW}[!]${NC} Токен должен начинаться с цифр и двоеточия"
                fi
                ;;
        esac
        
        update_key "$key_name" "$NEW_KEY"
        echo -e "${GREEN}[✓]${NC} $key_display обновлен"
        return 0
    else
        echo -e "${YELLOW}[→]${NC} Пропущено"
        return 1
    fi
}

# Выбор ключей для ротации
KEYS_ROTATED=0

case $KEY_TYPE in
    "anthropic")
        rotate_key "ANTHROPIC_API_KEY" "Anthropic API Key" "https://console.anthropic.com/account/keys" && ((KEYS_ROTATED++))
        ;;
    "telegram")
        rotate_key "TELEGRAM_BOT_TOKEN" "Telegram Bot Token" "https://t.me/BotFather → /mybots → API Token" && ((KEYS_ROTATED++))
        ;;
    "openai")
        rotate_key "OPENAI_API_KEY" "OpenAI API Key" "https://platform.openai.com/api-keys" && ((KEYS_ROTATED++))
        ;;
    "all"|"")
        echo "Будут ротированы все ключи."
        echo "Нажмите Enter для продолжения или Ctrl+C для отмены..."
        read -r
        
        rotate_key "ANTHROPIC_API_KEY" "Anthropic API Key" "https://console.anthropic.com/account/keys" && ((KEYS_ROTATED++))
        rotate_key "TELEGRAM_BOT_TOKEN" "Telegram Bot Token" "https://t.me/BotFather" && ((KEYS_ROTATED++))
        rotate_key "OPENAI_API_KEY" "OpenAI API Key" "https://platform.openai.com/api-keys" && ((KEYS_ROTATED++))
        ;;
    *)
        echo "Использование: $0 [anthropic|telegram|openai|all]"
        exit 1
        ;;
esac

# Установка прав
chmod 600 "$ENV_FILE"

# Перезапуск сервиса
if [ $KEYS_ROTATED -gt 0 ]; then
    echo ""
    echo "Ключи обновлены. Перезапустить сервис? (y/n)"
    read -r RESTART
    
    if [ "$RESTART" = "y" ]; then
        systemctl restart "$SERVICE_NAME"
        sleep 2
        
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            echo -e "${GREEN}[✓]${NC} Сервис перезапущен успешно"
            
            # Проверка логов на ошибки авторизации
            echo ""
            echo "Проверка логов на ошибки..."
            sleep 3
            
            if journalctl -u "$SERVICE_NAME" --since "30 seconds ago" | grep -qi "auth\|unauthorized\|invalid.*key\|401"; then
                echo -e "${RED}[!]${NC} Обнаружены ошибки авторизации в логах!"
                echo "Проверьте: journalctl -u $SERVICE_NAME -f"
                echo ""
                echo "Откатить к предыдущим ключам? (y/n)"
                read -r ROLLBACK
                
                if [ "$ROLLBACK" = "y" ]; then
                    cp "$BACKUP_FILE" "$ENV_FILE"
                    chmod 600 "$ENV_FILE"
                    systemctl restart "$SERVICE_NAME"
                    echo -e "${GREEN}[✓]${NC} Откат выполнен"
                fi
            else
                echo -e "${GREEN}[✓]${NC} Ошибок авторизации не обнаружено"
            fi
        else
            echo -e "${RED}[!]${NC} Сервис не запустился!"
            echo "Откат к предыдущим ключам..."
            cp "$BACKUP_FILE" "$ENV_FILE"
            chmod 600 "$ENV_FILE"
            systemctl restart "$SERVICE_NAME"
        fi
    fi
fi

# Напоминание об удалении старых ключей
echo ""
echo "=========================================="
echo -e "${YELLOW}ВАЖНО: Не забудьте отозвать старые ключи!${NC}"
echo ""
echo "• Anthropic: https://console.anthropic.com/account/keys"
echo "• OpenAI: https://platform.openai.com/api-keys" 
echo "• Telegram: /revoke через @BotFather (если создали нового бота)"
echo "=========================================="

# Очистка старых бэкапов .env (старше 30 дней)
find "$BACKUP_DIR" -name ".env.*" -mtime +30 -delete 2>/dev/null || true

echo ""
echo -e "${GREEN}Готово!${NC}"
