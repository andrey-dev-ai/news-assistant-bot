# 🚀 Инструкция по деплою News Bot на ваш VPS

## Шаг 1: Подключитесь к серверу

Откройте **PowerShell** и подключитесь к вашему VPS (так же, как делали для Grand Pellets):

```powershell
ssh root@ВАШ_IP_АДРЕС
# Введите пароль
```

> **Не помните IP?** Он должен быть в email от Contabo или в личном кабинете my.contabo.com

---

## Шаг 2: Проверьте, что сервер готов

После подключения выполните:

```bash
# Проверка Python
python3 --version

# Если Python не установлен:
apt update && apt install -y python3 python3-pip python3-venv
```

---

## Шаг 3: Скопируйте и выполните скрипт деплоя

Скопируйте эту команду целиком и вставьте в терминал (Ctrl+Shift+V):

```bash
# Создаём папку для бота
mkdir -p /opt/ai-bots/news-assistant-bot
cd /opt/ai-bots/news-assistant-bot

# Создаём виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Создаём requirements.txt
cat > requirements.txt << 'EOF'
feedparser==6.0.11
anthropic==0.34.2
python-telegram-bot==21.7
python-dotenv==1.0.1
schedule==1.2.2
requests==2.32.3
EOF

# Устанавливаем зависимости
pip install -r requirements.txt

# Создаём .env файл с вашими ключами
cat > .env << 'EOF'
ANTHROPIC_API_KEY=your-anthropic-api-key-here
TELEGRAM_BOT_TOKEN=8423032550:AAHqwMmqi-dVF9g8YmEk5HYGjWKP5J8A0oU
TELEGRAM_USER_ID=5260209994
DIGEST_TIMES=08:00
EOF

# Создаём папки
mkdir -p data logs config src

# Создаём RSS feeds конфигурацию
cat > config/rss_feeds.json << 'EOF'
[
  {
    "name": "TechCrunch AI",
    "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "enabled": true
  },
  {
    "name": "VentureBeat AI",
    "url": "https://venturebeat.com/category/ai/feed/",
    "enabled": true
  },
  {
    "name": "MIT Technology Review AI",
    "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed",
    "enabled": true
  },
  {
    "name": "The Verge AI",
    "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "enabled": true
  },
  {
    "name": "Ars Technica AI",
    "url": "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "enabled": true
  },
  {
    "name": "AI News",
    "url": "https://www.artificialintelligence-news.com/feed/",
    "enabled": true
  }
]
EOF

echo "✅ Конфигурация создана!"
```

---

## Шаг 4: Загрузите файлы кода

Теперь нужно загрузить Python файлы бота. Два способа:

### Способ А: Через nano (прямо на сервере)

Создайте каждый файл командой `nano filename.py`, вставьте код и сохраните (Ctrl+O, Enter, Ctrl+X):

#### 4.1 Создайте src/rss_parser.py

```bash
nano src/rss_parser.py
```

Откройте файл `D:\AI\news-assistant-bot\src\rss_parser.py` на компьютере, скопируйте содержимое и вставьте в nano.

#### 4.2 Создайте src/ai_processor.py

```bash
nano src/ai_processor.py
```

Откройте `D:\AI\news-assistant-bot\src\ai_processor.py`, скопируйте и вставьте.

#### 4.3 Создайте src/telegram_bot.py

```bash
nano src/telegram_bot.py
```

Откройте `D:\AI\news-assistant-bot\src\telegram_bot.py`, скопируйте и вставьте.

#### 4.4 Создайте src/database.py

```bash
nano src/database.py
```

Откройте `D:\AI\news-assistant-bot\src\database.py`, скопируйте и вставьте.

#### 4.5 Создайте main.py

```bash
nano main.py
```

Откройте `D:\AI\news-assistant-bot\main.py`, скопируйте и вставьте.

#### 4.6 Создайте scheduler.py

```bash
nano scheduler.py
```

Откройте `D:\AI\news-assistant-bot\scheduler.py`, скопируйте и вставьте.

### Способ Б: Через WinSCP (проще)

1. Скачайте WinSCP: https://winscp.net/
2. Подключитесь к серверу (IP, root, пароль)
3. Перейдите в `/opt/ai-bots/news-assistant-bot/`
4. Перетащите файлы из `D:\AI\news-assistant-bot\`:
   - `main.py`
   - `scheduler.py`
   - Всю папку `src/`

---

## Шаг 5: Тестовый запуск

```bash
cd /opt/ai-bots/news-assistant-bot
source venv/bin/activate
python main.py
```

Если всё работает - дайджест должен прийти в Telegram!

---

## Шаг 6: Настройка автозапуска (работа 24/7)

Создайте systemd сервис:

```bash
cat > /etc/systemd/system/ai-news-bot.service << 'EOF'
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
EOF

# Запустите сервис
systemctl daemon-reload
systemctl enable ai-news-bot
systemctl start ai-news-bot

# Проверьте статус
systemctl status ai-news-bot
```

Должно быть: **Active: active (running)** 🟢

---

## Шаг 7: Управление ботом

```bash
# Смотреть логи в реальном времени
journalctl -u ai-news-bot -f

# Перезапустить бота
systemctl restart ai-news-bot

# Остановить бота
systemctl stop ai-news-bot

# Статус
systemctl status ai-news-bot
```

---

## ✅ Готово!

Бот работает 24/7 и будет отправлять дайджесты каждый день в 08:00 по киевскому времени!

---

## 🔧 Настройка timezone (опционально)

Если хотите, чтобы время было точно киевское:

```bash
timedatectl set-timezone Europe/Kyiv
systemctl restart ai-news-bot
```

---

## 📊 Проверка ресурсов

```bash
# Сколько занимает бот
du -sh /opt/ai-bots/news-assistant-bot

# Память
free -h

# Все запущенные сервисы
systemctl list-units --type=service --state=running | grep bot
```

---

## 🆘 Если что-то не работает

1. Проверьте логи: `journalctl -u ai-news-bot -n 50`
2. Проверьте .env: `cat .env`
3. Тест вручную: `cd /opt/ai-bots/news-assistant-bot && source venv/bin/activate && python main.py`
4. Убедитесь, что нажали Start у бота в Telegram: https://t.me/TMAINewsBot
