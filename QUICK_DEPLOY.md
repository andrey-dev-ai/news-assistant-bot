# ⚡ Быстрый деплой на VPS

**IP:** 141.227.152.143
**Пароль:** 3wgcLtVvpMWW

---

## 🚀 Шаг 1: Подключитесь к серверу

Откройте **PowerShell** и выполните:

```powershell
ssh root@141.227.152.143
# Введите пароль: 3wgcLtVvpMWW
```

---

## 📦 Шаг 2: Скопируйте и выполните весь блок

Скопируйте **ВСЁ** (от `mkdir` до последнего `EOF`) и вставьте в терминал одной командой:

```bash
mkdir -p /opt/ai-bots/news-assistant-bot && cd /opt/ai-bots/news-assistant-bot && python3 -m venv venv && source venv/bin/activate && cat > requirements.txt << 'REQUIREMENTS_EOF'
feedparser==6.0.11
anthropic==0.34.2
python-telegram-bot==21.7
python-dotenv==1.0.1
schedule==1.2.2
requests==2.32.3
REQUIREMENTS_EOF
pip install --upgrade pip && pip install -r requirements.txt && cat > .env << 'ENV_EOF'
ANTHROPIC_API_KEY=your-anthropic-api-key-here
TELEGRAM_BOT_TOKEN=8423032550:AAHqwMmqi-dVF9g8YmEk5HYGjWKP5J8A0oU
TELEGRAM_USER_ID=5260209994
DIGEST_TIMES=08:00
ENV_EOF
mkdir -p data logs config src && cat > config/rss_feeds.json << 'RSS_EOF'
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
RSS_EOF
echo "✅ Базовая настройка завершена!"
```

Дождитесь сообщения: **✅ Базовая настройка завершена!**

---

## 📝 Шаг 3: Загрузка Python файлов

Теперь нужно загрузить код бота. **Два способа:**

### Способ А: WinSCP (Рекомендуется - проще)

1. Скачайте WinSCP: https://winscp.net/eng/download.php
2. Запустите WinSCP
3. Подключитесь:
   - **Host:** 141.227.152.143
   - **User:** root
   - **Password:** 3wgcLtVvpMWW
4. В правой панели перейдите в: `/opt/ai-bots/news-assistant-bot`
5. Перетащите эти файлы из `D:\AI\news-assistant-bot`:
   - `main.py`
   - `scheduler.py`
   - Всю папку `src` (4 файла внутри)

### Способ Б: Через nano (дольше)

Создайте каждый файл вручную командой `nano`:

#### 3.1 Создайте src/database.py

```bash
nano src/database.py
```

Откройте файл `D:\AI\news-assistant-bot\src\database.py`, скопируйте весь код и вставьте в nano (правой кнопкой мыши).
Сохраните: **Ctrl+O** → Enter → **Ctrl+X**

#### 3.2 Создайте src/rss_parser.py

```bash
nano src/rss_parser.py
```

Скопируйте содержимое `D:\AI\news-assistant-bot\src\rss_parser.py` и вставьте.
Сохраните: **Ctrl+O** → Enter → **Ctrl+X**

#### 3.3 Создайте src/ai_processor.py

```bash
nano src/ai_processor.py
```

Скопируйте содержимое `D:\AI\news-assistant-bot\src\ai_processor.py` и вставьте.
Сохраните: **Ctrl+O** → Enter → **Ctrl+X**

#### 3.4 Создайте src/telegram_bot.py

```bash
nano src/telegram_bot.py
```

Скопируйте содержимое `D:\AI\news-assistant-bot\src\telegram_bot.py` и вставьте.
Сохраните: **Ctrl+O** → Enter → **Ctrl+X**

#### 3.5 Создайте main.py

```bash
nano main.py
```

Скопируйте содержимое `D:\AI\news-assistant-bot\main.py` и вставьте.
Сохраните: **Ctrl+O** → Enter → **Ctrl+X**

#### 3.6 Создайте scheduler.py

```bash
nano scheduler.py
```

Скопируйте содержимое `D:\AI\news-assistant-bot\scheduler.py` и вставьте.
Сохраните: **Ctrl+O** → Enter → **Ctrl+X**

---

## ✅ Шаг 4: Тестовый запуск

```bash
cd /opt/ai-bots/news-assistant-bot
source venv/bin/activate
python main.py
```

Если всё работает - дайджест должен **сразу прийти** в Telegram! 🎉

---

## 🔄 Шаг 5: Настройка автозапуска (24/7)

Создайте systemd сервис (скопируйте весь блок целиком):

```bash
cat > /etc/systemd/system/ai-news-bot.service << 'SERVICE_EOF'
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
SERVICE_EOF

systemctl daemon-reload
systemctl enable ai-news-bot
systemctl start ai-news-bot
systemctl status ai-news-bot
```

Должно показать: **Active: active (running)** 🟢

---

## 📊 Управление ботом

```bash
# Просмотр логов в реальном времени
journalctl -u ai-news-bot -f

# Перезапуск
systemctl restart ai-news-bot

# Остановка
systemctl stop ai-news-bot

# Статус
systemctl status ai-news-bot
```

---

## ✅ Готово!

Бот теперь работает **24/7** и будет отправлять дайджесты каждое утро в **08:00** по киевскому времени!

**Следующий дайджест:** Завтра в 08:00 🎯
