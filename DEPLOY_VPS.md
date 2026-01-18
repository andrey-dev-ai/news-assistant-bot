# Деплой на VPS (Hetzner / DigitalOcean)

## Что вам понадобится:

1. **VPS сервер** (рекомендую Hetzner за €4.15/мес)
2. **IP-адрес** сервера
3. **SSH доступ** (логин root + пароль)

---

## Шаг 1: Аренда VPS

### Вариант А: Hetzner (рекомендую)

1. Зайдите: https://www.hetzner.com/cloud
2. Зарегистрируйтесь
3. Создайте проект
4. "Add Server"
5. Выберите:
   - **Location**: Nuremberg (Германия) или Helsinki (Финляндия)
   - **Image**: Ubuntu 22.04 или 24.04
   - **Type**: CPX11 (2 vCPU, 4GB RAM) - €4.15/мес
   - **SSH Key**: можно позже, пока пароль
6. Создайте сервер
7. Скопируйте:
   - IP-адрес (типа 123.45.67.89)
   - Root пароль (придет на email)

### Вариант Б: DigitalOcean

1. https://www.digitalocean.com/
2. Sign Up (есть бонус $200 на 60 дней)
3. Create → Droplets
4. Выберите:
   - Ubuntu 22.04
   - Basic Plan - $6/мес (Regular Intel)
   - Datacenter: Frankfurt или Amsterdam
5. Создайте
6. Получите IP и пароль root

---

## Шаг 2: Подключение к серверу

### Windows (через PowerShell):

```powershell
ssh root@ВАШ_IP_АДРЕС
# Введите пароль когда попросит
```

### Если нет SSH:
Скачайте **PuTTY**: https://www.putty.org/
- Host Name: ваш IP
- Port: 22
- Connection Type: SSH
- Open → введите root и пароль

---

## Шаг 3: Настройка сервера

После подключения выполните команды по очереди:

```bash
# Обновить систему
apt update && apt upgrade -y

# Установить Python и зависимости
apt install python3 python3-pip python3-venv git -y

# Проверить версию Python (должно быть 3.8+)
python3 --version

# Создать папку для проектов
mkdir -p /opt/ai-bots
cd /opt/ai-bots
```

---

## Шаг 4: Загрузка кода на сервер

### Способ 1: Через Git (если будете использовать GitHub)

```bash
cd /opt/ai-bots
git clone https://github.com/ваш-репозиторий/news-assistant-bot.git
cd news-assistant-bot
```

### Способ 2: Загрузка файлов напрямую (проще для начала)

**На вашем компьютере:**

1. Скачайте и установите WinSCP: https://winscp.net/
2. Откройте WinSCP:
   - File protocol: SFTP
   - Host name: ваш IP
   - User name: root
   - Password: ваш пароль
3. Connect
4. Слева - ваш компьютер `D:\AI\news-assistant-bot`
5. Справа - сервер `/opt/ai-bots/`
6. Перетащите всю папку `news-assistant-bot` на сервер

---

## Шаг 5: Установка зависимостей

```bash
cd /opt/ai-bots/news-assistant-bot

# Создать виртуальное окружение
python3 -m venv venv

# Активировать
source venv/bin/activate

# Установить библиотеки
pip install -r requirements.txt
```

---

## Шаг 6: Настройка .env

```bash
# Создать .env файл
nano .env
```

Вставьте ваши ключи (Ctrl+Shift+V для вставки):

```env
ANTHROPIC_API_KEY=sk-ant-ваш-ключ-claude
TELEGRAM_BOT_TOKEN=ваш-токен-бота
TELEGRAM_USER_ID=ваш-telegram-id
DIGEST_TIMES=08:00
```

Сохраните: `Ctrl+O` → Enter → `Ctrl+X`

---

## Шаг 7: Тестовый запуск

```bash
# Убедитесь что вы в нужной папке
cd /opt/ai-bots/news-assistant-bot

# Активируйте виртуальное окружение
source venv/bin/activate

# Запустите
python main.py
```

Должен прийти дайджест в Telegram!

---

## Шаг 8: Автозапуск (работа 24/7)

Создадим systemd сервис, чтобы бот работал постоянно:

```bash
# Создать файл сервиса
nano /etc/systemd/system/ai-news-bot.service
```

Вставьте:

```ini
[Unit]
Description=AI News Assistant Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/ai-bots/news-assistant-bot
Environment="PATH=/opt/ai-bots/news-assistant-bot/venv/bin"
ExecStart=/opt/ai-bots/news-assistant-bot/venv/bin/python /opt/ai-bots/news-assistant-bot/scheduler.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Сохраните: `Ctrl+O` → Enter → `Ctrl+X`

Запустите сервис:

```bash
# Обновить systemd
systemctl daemon-reload

# Включить автозапуск
systemctl enable ai-news-bot

# Запустить сервис
systemctl start ai-news-bot

# Проверить статус
systemctl status ai-news-bot
```

Должно быть: **Active: active (running)**

---

## Шаг 9: Управление ботом

```bash
# Посмотреть логи в реальном времени
journalctl -u ai-news-bot -f

# Остановить бота
systemctl stop ai-news-bot

# Перезапустить
systemctl restart ai-news-bot

# Проверить статус
systemctl status ai-news-bot
```

---

## Обновление кода

Когда нужно обновить код:

```bash
# Остановить бота
systemctl stop ai-news-bot

# Перейти в папку
cd /opt/ai-bots/news-assistant-bot

# Обновить файлы (через WinSCP или git pull)

# Перезапустить
systemctl start ai-news-bot
```

---

## Проблемы и решения

### Бот не запускается

```bash
# Смотрим логи
journalctl -u ai-news-bot -n 50

# Проверяем .env файл
cat .env

# Тестируем вручную
cd /opt/ai-bots/news-assistant-bot
source venv/bin/activate
python main.py
```

### Изменить расписание

```bash
nano /opt/ai-bots/news-assistant-bot/.env
# Измените DIGEST_TIMES=08:00

# Перезапустите
systemctl restart ai-news-bot
```

### Проверить использование ресурсов

```bash
# CPU и память
htop

# Место на диске
df -h
```

---

## Безопасность (опционально, но рекомендуется)

```bash
# Создать отдельного пользователя
adduser aibot

# Поменять владельца файлов
chown -R aibot:aibot /opt/ai-bots/news-assistant-bot

# В файле сервиса изменить User=root на User=aibot
nano /etc/systemd/system/ai-news-bot.service

# Перезапустить
systemctl daemon-reload
systemctl restart ai-news-bot
```

---

## Готово!

Ваш бот работает 24/7 на сервере и будет отправлять дайджесты каждое утро в 08:00 по киевскому времени.

**Важно:** Сервер работает в UTC timezone. Для Украины (UTC+2/UTC+3) нужно учитывать разницу:
- Киев 08:00 = UTC 06:00 (зимой) или UTC 05:00 (летом)
- Либо настройте timezone на сервере: `timedatectl set-timezone Europe/Kyiv`
