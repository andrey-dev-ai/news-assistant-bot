#!/bin/bash
#===============================================================================
# ssh-hardening.sh - Hardening SSH на VPS (запускать НА СЕРВЕРЕ)
# Использование: sudo ./ssh-hardening.sh
#===============================================================================

set -e

# === Конфигурация сервера ===
# VPS: vps-ec36a417.vps.ovh.net (OVH Amsterdam)
# IP: 141.227.152.143
# OS: Ubuntu 25.04 | 4 vCores | 8GB RAM | 75GB SSD

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

SSHD_CONFIG="/etc/ssh/sshd_config"
BACKUP_CONFIG="/etc/ssh/sshd_config.backup.$(date +%Y%m%d_%H%M%S)"

echo "=========================================="
echo "  SSH Hardening для VPS"
echo "  vps-ec36a417.vps.ovh.net"
echo "=========================================="
echo ""

# Проверка root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Запустите от root: sudo ./ssh-hardening.sh${NC}"
    exit 1
fi

# Проверка что есть хотя бы один ключ
if [ ! -f /root/.ssh/authorized_keys ] || [ ! -s /root/.ssh/authorized_keys ]; then
    echo -e "${RED}СТОП! Нет SSH ключей в /root/.ssh/authorized_keys${NC}"
    echo "Сначала добавьте SSH ключ, иначе потеряете доступ!"
    echo ""
    echo "На локальной машине выполните:"
    echo "  ssh-copy-id root@141.227.152.143"
    exit 1
fi

KEY_COUNT=$(wc -l < /root/.ssh/authorized_keys)
echo -e "${GREEN}[✓]${NC} Найдено SSH ключей: $KEY_COUNT"
echo ""

# Бэкап конфига
cp "$SSHD_CONFIG" "$BACKUP_CONFIG"
echo -e "${GREEN}[✓]${NC} Бэкап: $BACKUP_CONFIG"

# Функция для установки параметра
set_ssh_param() {
    local param=$1
    local value=$2
    
    if grep -q "^${param}" "$SSHD_CONFIG"; then
        sed -i "s/^${param}.*/${param} ${value}/" "$SSHD_CONFIG"
    elif grep -q "^#${param}" "$SSHD_CONFIG"; then
        sed -i "s/^#${param}.*/${param} ${value}/" "$SSHD_CONFIG"
    else
        echo "${param} ${value}" >> "$SSHD_CONFIG"
    fi
}

echo ""
echo -e "${CYAN}Применение настроек...${NC}"
echo ""

# Основные настройки безопасности
set_ssh_param "PermitRootLogin" "prohibit-password"
echo -e "${GREEN}[✓]${NC} PermitRootLogin prohibit-password"

set_ssh_param "PasswordAuthentication" "no"
echo -e "${GREEN}[✓]${NC} PasswordAuthentication no"

set_ssh_param "PubkeyAuthentication" "yes"
echo -e "${GREEN}[✓]${NC} PubkeyAuthentication yes"

set_ssh_param "AuthorizedKeysFile" ".ssh/authorized_keys"
echo -e "${GREEN}[✓]${NC} AuthorizedKeysFile .ssh/authorized_keys"

set_ssh_param "ChallengeResponseAuthentication" "no"
echo -e "${GREEN}[✓]${NC} ChallengeResponseAuthentication no"

set_ssh_param "UsePAM" "yes"
echo -e "${GREEN}[✓]${NC} UsePAM yes"

# Дополнительная безопасность
set_ssh_param "X11Forwarding" "no"
echo -e "${GREEN}[✓]${NC} X11Forwarding no"

set_ssh_param "PrintMotd" "no"
echo -e "${GREEN}[✓]${NC} PrintMotd no"

set_ssh_param "PermitEmptyPasswords" "no"
echo -e "${GREEN}[✓]${NC} PermitEmptyPasswords no"

set_ssh_param "MaxAuthTries" "3"
echo -e "${GREEN}[✓]${NC} MaxAuthTries 3"

set_ssh_param "LoginGraceTime" "60"
echo -e "${GREEN}[✓]${NC} LoginGraceTime 60"

set_ssh_param "ClientAliveInterval" "300"
echo -e "${GREEN}[✓]${NC} ClientAliveInterval 300"

set_ssh_param "ClientAliveCountMax" "2"
echo -e "${GREEN}[✓]${NC} ClientAliveCountMax 2"

# Проверка конфигурации
echo ""
echo -e "${CYAN}Проверка конфигурации...${NC}"
if sshd -t; then
    echo -e "${GREEN}[✓]${NC} Конфигурация валидна"
else
    echo -e "${RED}[!]${NC} Ошибка в конфигурации! Откат..."
    cp "$BACKUP_CONFIG" "$SSHD_CONFIG"
    exit 1
fi

# Предупреждение
echo ""
echo "=========================================="
echo -e "${YELLOW}ВАЖНО! Перед перезагрузкой SSH:${NC}"
echo "=========================================="
echo ""
echo "1. НЕ закрывайте это окно терминала"
echo "2. Откройте НОВОЕ окно и проверьте подключение:"
echo ""
echo -e "   ${WHITE}ssh root@141.227.152.143${NC}"
echo ""
echo "3. Если новое подключение работает - применяем"
echo "4. Если нет - откатываем из этого окна"
echo ""
echo "Применить изменения? (yes/no)"
read -r APPLY

if [ "$APPLY" = "yes" ]; then
    echo ""
    echo "Перезагрузка SSH..."
    systemctl reload sshd
    
    echo ""
    echo -e "${GREEN}[✓]${NC} SSH перезагружен"
    echo ""
    echo "Проверьте подключение в НОВОМ терминале!"
    echo "Если не работает, выполните здесь:"
    echo ""
    echo "  cp $BACKUP_CONFIG $SSHD_CONFIG"
    echo "  systemctl reload sshd"
    echo ""
else
    echo ""
    echo "Отменено. Откат к предыдущей конфигурации..."
    cp "$BACKUP_CONFIG" "$SSHD_CONFIG"
    echo -e "${GREEN}[✓]${NC} Откат выполнен"
fi

# Вывод текущих настроек
echo ""
echo "=========================================="
echo "  Текущие настройки SSH"
echo "=========================================="
grep -E "^(PermitRootLogin|PasswordAuthentication|PubkeyAuthentication|MaxAuthTries)" "$SSHD_CONFIG"
