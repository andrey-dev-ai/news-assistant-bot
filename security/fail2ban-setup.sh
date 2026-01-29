#!/bin/bash
#===============================================================================
# fail2ban-setup.sh - Базовая настройка fail2ban
# Использование: sudo ./fail2ban-setup.sh
#===============================================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "  Настройка Fail2ban"
echo "=========================================="
echo ""

# Проверка root
if [ "$EUID" -ne 0 ]; then 
    echo "Запустите от root: sudo ./fail2ban-setup.sh"
    exit 1
fi

# Установка
if ! command -v fail2ban-client &> /dev/null; then
    echo "Установка fail2ban..."
    apt-get update && apt-get install -y fail2ban
fi

# Создание локальной конфигурации
echo "Создание конфигурации..."

cat > /etc/fail2ban/jail.local << 'EOF'
# Fail2ban конфигурация для Telegram-бота VPS
# /etc/fail2ban/jail.local

[DEFAULT]
# Игнорировать localhost
ignoreip = 127.0.0.1/8 ::1

# Время бана (10 минут)
bantime = 10m

# Окно поиска (10 минут)
findtime = 10m

# Количество попыток до бана
maxretry = 5

# Бэкенд для мониторинга логов
backend = systemd

# Email уведомления (опционально)
# destemail = admin@example.com
# sender = fail2ban@example.com
# mta = sendmail

# Действие по умолчанию (бан IP)
banaction = iptables-multiport

#===============================================
# SSH защита - ОБЯЗАТЕЛЬНО
#===============================================
[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 1h
findtime = 10m

# Агрессивный режим для повторных нарушителей
[sshd-aggressive]
enabled = true
port = ssh
filter = sshd[mode=aggressive]
logpath = /var/log/auth.log
maxretry = 2
bantime = 24h
findtime = 1h

#===============================================
# Защита от сканирования портов
#===============================================
[portscan]
enabled = true
filter = portscan
logpath = /var/log/syslog
maxretry = 3
bantime = 24h
findtime = 1h
banaction = iptables-allports

EOF

# Создание фильтра для сканирования портов
cat > /etc/fail2ban/filter.d/portscan.conf << 'EOF'
# Fail2ban filter for port scanning
[Definition]
failregex = UFW BLOCK.* SRC=<HOST>
ignoreregex =
EOF

# Проверка конфигурации
echo "Проверка конфигурации..."
if fail2ban-client -t; then
    echo -e "${GREEN}[✓]${NC} Конфигурация валидна"
else
    echo "Ошибка в конфигурации!"
    exit 1
fi

# Перезапуск сервиса
echo "Перезапуск fail2ban..."
systemctl restart fail2ban
systemctl enable fail2ban

# Статус
echo ""
echo "=========================================="
echo "Статус fail2ban:"
echo "=========================================="
fail2ban-client status

echo ""
echo "=========================================="
echo "Статус SSH jail:"
echo "=========================================="
fail2ban-client status sshd

echo ""
echo -e "${GREEN}[✓]${NC} Fail2ban настроен"
echo ""
echo "Полезные команды:"
echo "  fail2ban-client status              - общий статус"
echo "  fail2ban-client status sshd         - статус SSH jail"
echo "  fail2ban-client set sshd unbanip IP - разбанить IP"
echo "  fail2ban-client banned              - список забаненных"
echo "  tail -f /var/log/fail2ban.log       - лог fail2ban"
echo "=========================================="
