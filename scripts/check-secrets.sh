#!/bin/bash
#===============================================================================
# check-secrets.sh - Проверка безопасности секретов
# Использование: ./check-secrets.sh [--fix]
#===============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# === Конфигурация сервера ===
# VPS: vps-ec36a417.vps.ovh.net (OVH Amsterdam)
# IP: 141.227.152.143
# OS: Ubuntu 25.04 | 4 vCores | 8GB RAM | 75GB SSD
PROJECT_DIR="/opt/news-assistant-bot"
ENV_FILE="$PROJECT_DIR/.env"
FIX_MODE="${1:-}"

echo "=========================================="
echo "  Проверка безопасности секретов"
echo "=========================================="
echo ""

ERRORS=0
WARNINGS=0

# Функция проверки
check() {
    local status=$1
    local message=$2
    if [ "$status" = "OK" ]; then
        echo -e "${GREEN}[OK]${NC} $message"
    elif [ "$status" = "WARN" ]; then
        echo -e "${YELLOW}[WARN]${NC} $message"
        ((WARNINGS++))
    else
        echo -e "${RED}[FAIL]${NC} $message"
        ((ERRORS++))
    fi
}

# 1. Проверка существования .env
echo "--- Проверка .env файла ---"
if [ -f "$ENV_FILE" ]; then
    check "OK" ".env файл существует"
else
    check "FAIL" ".env файл не найден!"
    echo "Создайте .env из .env.example"
    exit 1
fi

# 2. Проверка прав доступа .env
PERMS=$(stat -c "%a" "$ENV_FILE" 2>/dev/null || stat -f "%Lp" "$ENV_FILE")
if [ "$PERMS" = "600" ]; then
    check "OK" "Права .env: 600 (только владелец)"
else
    check "FAIL" "Права .env: $PERMS (должно быть 600)"
    if [ "$FIX_MODE" = "--fix" ]; then
        chmod 600 "$ENV_FILE"
        echo -e "  ${GREEN}→ Исправлено${NC}"
    fi
fi

# 3. Проверка владельца
OWNER=$(stat -c "%U" "$ENV_FILE" 2>/dev/null || stat -f "%Su" "$ENV_FILE")
if [ "$OWNER" = "root" ] || [ "$OWNER" = "$(whoami)" ]; then
    check "OK" "Владелец .env: $OWNER"
else
    check "WARN" "Владелец .env: $OWNER (рекомендуется root или текущий пользователь)"
fi

# 4. Проверка .gitignore
echo ""
echo "--- Проверка Git безопасности ---"
cd "$PROJECT_DIR"

if [ -f ".gitignore" ]; then
    if grep -q "^\.env$" .gitignore || grep -q "^\.env\*" .gitignore; then
        check "OK" ".env в .gitignore"
    else
        check "FAIL" ".env НЕ в .gitignore!"
        if [ "$FIX_MODE" = "--fix" ]; then
            echo ".env" >> .gitignore
            echo -e "  ${GREEN}→ Добавлено в .gitignore${NC}"
        fi
    fi
else
    check "FAIL" ".gitignore не найден!"
fi

# 5. Проверка что .env не отслеживается git
if [ -d ".git" ]; then
    if git ls-files --error-unmatch .env >/dev/null 2>&1; then
        check "FAIL" ".env ОТСЛЕЖИВАЕТСЯ GIT! Критическая уязвимость!"
        echo -e "  ${RED}Выполните: git rm --cached .env${NC}"
    else
        check "OK" ".env не отслеживается git"
    fi
    
    # Проверка истории git на предмет секретов
    if git log --all --full-history -- .env 2>/dev/null | grep -q "commit"; then
        check "WARN" ".env был в истории git (рекомендуется ротация ключей)"
    fi
else
    check "WARN" "Git репозиторий не инициализирован"
fi

# 6. Проверка содержимого .env
echo ""
echo "--- Проверка содержимого .env ---"

# Проверка что ключи заполнены
while IFS='=' read -r key value; do
    # Пропускаем комментарии и пустые строки
    [[ "$key" =~ ^#.*$ ]] && continue
    [[ -z "$key" ]] && continue
    
    # Убираем кавычки из значения
    value=$(echo "$value" | tr -d '"' | tr -d "'")
    
    if [[ "$key" =~ (KEY|TOKEN|SECRET|PASSWORD) ]]; then
        if [ -z "$value" ] || [ "$value" = "your-key-here" ] || [ "$value" = "xxx" ]; then
            check "FAIL" "$key не заполнен или содержит placeholder"
        elif [ ${#value} -lt 20 ]; then
            check "WARN" "$key подозрительно короткий (${#value} символов)"
        else
            # Показываем только первые 4 символа
            masked="${value:0:4}***"
            check "OK" "$key заполнен ($masked)"
        fi
    fi
done < "$ENV_FILE"

# 7. Проверка других потенциальных утечек
echo ""
echo "--- Поиск других секретов ---"

# Поиск hardcoded секретов в Python файлах
LEAKED=$(grep -r -l -E "(sk-[a-zA-Z0-9]{20,}|ANTHROPIC_API_KEY\s*=\s*['\"][^'\"]+['\"])" \
    --include="*.py" "$PROJECT_DIR/src" 2>/dev/null || true)

if [ -n "$LEAKED" ]; then
    check "FAIL" "Найдены hardcoded секреты в файлах:"
    echo "$LEAKED" | while read -r file; do
        echo "  - $file"
    done
else
    check "OK" "Hardcoded секреты в коде не найдены"
fi

# Итоги
echo ""
echo "=========================================="
if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}КРИТИЧЕСКИЕ ОШИБКИ: $ERRORS${NC}"
    echo "Запустите с --fix для автоисправления"
    exit 1
elif [ $WARNINGS -gt 0 ]; then
    echo -e "${YELLOW}Предупреждения: $WARNINGS${NC}"
    echo "Рекомендуется проверить"
    exit 0
else
    echo -e "${GREEN}Все проверки пройдены!${NC}"
    exit 0
fi
