#!/bin/bash
# Автоматический деплой AI News Bot на VPS

set -e

echo "🚀 Деплой AI News Bot на VPS 141.227.152.143"
echo "================================================"

# Создаём папку для бота
echo "📁 Создание директории..."
mkdir -p /opt/ai-bots/news-assistant-bot
cd /opt/ai-bots/news-assistant-bot

# Проверка Python
echo "🐍 Проверка Python..."
python3 --version || (echo "❌ Python не установлен!" && exit 1)

# Создаём виртуальное окружение
echo "📦 Создание виртуального окружения..."
python3 -m venv venv
source venv/bin/activate

# Создаём requirements.txt
echo "📝 Создание requirements.txt..."
cat > requirements.txt << 'REQUIREMENTS_EOF'
feedparser==6.0.11
anthropic==0.34.2
python-telegram-bot==21.7
python-dotenv==1.0.1
schedule==1.2.2
requests==2.32.3
REQUIREMENTS_EOF

# Устанавливаем зависимости
echo "⬇️  Установка зависимостей..."
pip install --upgrade pip
pip install -r requirements.txt

# Создаём .env файл
echo "🔐 Создание конфигурации..."
cat > .env << 'ENV_EOF'
ANTHROPIC_API_KEY=your-anthropic-api-key-here
TELEGRAM_BOT_TOKEN=8423032550:AAHqwMmqi-dVF9g8YmEk5HYGjWKP5J8A0oU
TELEGRAM_USER_ID=5260209994
DIGEST_TIMES=08:00
ENV_EOF

# Создаём структуру папок
echo "📂 Создание структуры папок..."
mkdir -p data logs config src

# Создаём RSS feeds конфигурацию
echo "📰 Создание конфигурации RSS..."
cat > config/rss_feeds.json << 'RSS_EOF'
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

echo ""
echo "✅ Базовая настройка завершена!"
echo "📍 Путь: /opt/ai-bots/news-assistant-bot"
echo ""
echo "Теперь нужно загрузить Python файлы..."
