#!/bin/bash
# Скрипт деплоя AI News Bot на VPS

echo "🚀 Начинаем деплой AI News Bot..."

# 1. Создаём папку для бота
echo "📁 Создание директории..."
mkdir -p /opt/ai-bots/news-assistant-bot
cd /opt/ai-bots/news-assistant-bot

# 2. Создаём виртуальное окружение
echo "🐍 Настройка Python окружения..."
python3 -m venv venv
source venv/bin/activate

# 3. Устанавливаем зависимости
echo "📦 Установка зависимостей..."
cat > requirements.txt << 'EOF'
feedparser==6.0.11
anthropic==0.34.2
python-telegram-bot==21.7
python-dotenv==1.0.1
schedule==1.2.2
requests==2.32.3
EOF

pip install -r requirements.txt

# 4. Создаём .env файл
echo "🔐 Создание конфигурации..."
cat > .env << 'EOF'
ANTHROPIC_API_KEY=your-anthropic-api-key-here
TELEGRAM_BOT_TOKEN=8423032550:AAHqwMmqi-dVF9g8YmEk5HYGjWKP5J8A0oU
TELEGRAM_USER_ID=5260209994
DIGEST_TIMES=08:00
EOF

# 5. Создаём папки
mkdir -p data logs config/

# 6. Создаём RSS feeds конфигурацию
echo "📰 Настройка RSS фидов..."
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
echo ""
echo "Теперь нужно загрузить файлы кода бота..."
echo "Используйте WinSCP или продолжите следующими командами"
