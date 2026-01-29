# Security Checklist для VPS с Telegram-ботом

## Информация о сервере

| Параметр | Значение |
|----------|----------|
| **Hostname** | vps-ec36a417.vps.ovh.net |
| **Provider** | OVH |
| **Location** | Amsterdam, Netherlands |
| **IP** | 141.227.152.143 |
| **IPv6** | 2001:41d0:ab02::4::184 |
| **OS** | Ubuntu 25.04 |
| **CPU** | 4 vCores |
| **RAM** | 8 GB |
| **Storage** | 75 GB SSD |

---

## Быстрая проверка (выполнять регулярно)

```bash
# Одной командой - базовая проверка
./scripts/check-secrets.sh && \
fail2ban-client status sshd && \
ufw status && \
df -h | head -5 && \
systemctl is-active news-bot
```

---

## 1. Управление секретами

### ✅ Первоначальная настройка

- [ ] `.env` файл создан из `.env.example`
- [ ] Права доступа: `chmod 600 .env`
- [ ] Владелец: `chown root:root .env`
- [ ] `.env` добавлен в `.gitignore`
- [ ] Проверка: `./scripts/check-secrets.sh`

### ✅ Регулярные проверки

- [ ] Ежедневная проверка через cron настроена
- [ ] Нет hardcoded ключей в коде
- [ ] Ротация ключей каждые 90 дней

### Команды
```bash
# Установка прав
chmod 600 /opt/news-assistant-bot/.env
chown root:root /opt/news-assistant-bot/.env

# Проверка что .env не в git
git ls-files --error-unmatch .env  # Должна быть ошибка!

# Ротация ключей
sudo ./scripts/rotate-keys.sh all
```

---

## 2. Бэкапы

### ✅ Настройка

- [ ] `backup.sh` скрипт установлен
- [ ] Директория `/opt/news-assistant-bot/backups/db` создана
- [ ] Crontab настроен (каждые 6 часов)
- [ ] `restore.sh` протестирован
- [ ] (Опционально) S3 бэкапы настроены

### ✅ Проверки

- [ ] Бэкапы создаются по расписанию
- [ ] Retention policy работает (7 дней)
- [ ] Чексуммы создаются
- [ ] Тестовое восстановление проведено

### Команды
```bash
# Ручной бэкап
./scripts/backup.sh

# Список бэкапов
ls -lht /opt/news-assistant-bot/backups/db/

# Проверка cron логов
tail -50 /opt/news-assistant-bot/logs/backup-cron.log

# Тестовое восстановление (на отдельном сервере!)
./scripts/restore.sh latest
```

---

## 3. Firewall (UFW)

### ✅ Настройка

- [ ] UFW установлен и включен
- [ ] Политика по умолчанию: deny incoming, allow outgoing
- [ ] SSH разрешен (порт 22 или кастомный)
- [ ] Только необходимые порты открыты

### Минимальные правила для Telegram-бота (polling)
```bash
# Проверка статуса
sudo ufw status verbose

# Должно быть:
# Default: deny (incoming), allow (outgoing)
# 22/tcp ALLOW IN Anywhere (SSH)
```

### Команды
```bash
# Настройка
sudo ./security/ufw-setup.sh

# Проверка
sudo ufw status numbered
```

---

## 4. Fail2ban

### ✅ Настройка

- [ ] Fail2ban установлен и запущен
- [ ] SSH jail активен
- [ ] Агрессивный режим для повторных нарушителей
- [ ] (Опционально) portscan jail настроен

### Команды
```bash
# Настройка
sudo ./security/fail2ban-setup.sh

# Проверка статуса
sudo fail2ban-client status
sudo fail2ban-client status sshd

# Просмотр забаненных
sudo fail2ban-client banned

# Разбан IP
sudo fail2ban-client set sshd unbanip 1.2.3.4
```

---

## 5. SSH Hardening

### ✅ Рекомендуемые настройки `/etc/ssh/sshd_config`

```bash
# Отключить root логин по паролю
PermitRootLogin prohibit-password

# Только ключевая аутентификация
PasswordAuthentication no
PubkeyAuthentication yes

# Ограничить пользователей
AllowUsers your_username

# Таймауты
ClientAliveInterval 300
ClientAliveCountMax 2

# Отключить X11
X11Forwarding no
```

### Команды
```bash
# Проверка конфига
sudo sshd -t

# Применение
sudo systemctl reload sshd

# ВАЖНО: Не закрывайте текущую сессию до проверки нового подключения!
```

---

## 6. Системные обновления

### ✅ Регулярные действия

- [ ] Автоматические security updates включены
- [ ] Полное обновление системы раз в неделю/месяц

### Команды
```bash
# Настройка автообновлений безопасности
sudo apt install unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades

# Ручное обновление
sudo apt update && sudo apt upgrade -y

# Проверка pending security updates
sudo apt list --upgradable 2>/dev/null | grep -i security
```

---

## 7. Мониторинг

### ✅ Базовый мониторинг

- [ ] Логи бота проверяются
- [ ] Дисковое пространство мониторится
- [ ] Cron health check настроен

### Команды
```bash
# Логи бота
sudo journalctl -u news-bot -f

# Дисковое пространство
df -h

# Память
free -h

# Процессы бота
ps aux | grep -E "python|news"

# Последние логины
last -10
lastb -10  # неудачные попытки
```

---

## 8. Экстренные процедуры

### При компрометации ключей
```bash
# 1. Остановить бота
sudo systemctl stop news-bot

# 2. Ротировать ВСЕ ключи
sudo ./scripts/rotate-keys.sh all

# 3. Проверить логи на подозрительную активность
sudo journalctl -u news-bot --since "1 week ago" | grep -i error

# 4. Запустить бота
sudo systemctl start news-bot
```

### При взломе сервера
```bash
# 1. Отключить от сети (через панель хостинга)

# 2. Сделать snapshot/image диска для анализа

# 3. Поднять новый сервер из чистого образа

# 4. Восстановить данные из бэкапа
./scripts/restore.sh latest

# 5. ОБЯЗАТЕЛЬНО ротировать ВСЕ ключи
```

---

## Расписание проверок

| Частота | Что проверять |
|---------|--------------|
| Ежедневно | Автоматически через cron (check-secrets.sh) |
| Еженедельно | Логи fail2ban, статус бэкапов |
| Ежемесячно | Обновления системы, ротация ключей |
| Ежеквартально | Полный аудит, тестовое восстановление |

---

## Полезные алиасы для `.bashrc`

```bash
# Добавьте в ~/.bashrc
alias bot-status='systemctl status news-bot'
alias bot-logs='journalctl -u news-bot -f'
alias bot-restart='sudo systemctl restart news-bot'
alias bot-backup='sudo /opt/news-assistant-bot/scripts/backup.sh'
alias bot-security='sudo /opt/news-assistant-bot/scripts/check-secrets.sh'
alias banned='sudo fail2ban-client banned'
```
