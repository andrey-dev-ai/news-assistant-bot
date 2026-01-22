-- ============================================
-- AI ДЛЯ ДОМА — Схема базы данных
-- SQLite 3.40+ с расширением sqlite-vec
-- ============================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- Основная таблица контента
CREATE TABLE IF NOT EXISTS content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Источник
    source_url TEXT UNIQUE NOT NULL,
    source_name TEXT NOT NULL,
    source_type TEXT CHECK(source_type IN ('rss', 'telegram', 'manual')) DEFAULT 'rss',

    -- Оригинальный контент
    original_title TEXT NOT NULL,
    original_content TEXT,
    original_language TEXT CHECK(original_language IN ('ru', 'en', 'other')) DEFAULT 'ru',

    -- Обработанный контент
    processed_title TEXT,
    processed_content TEXT,
    telegram_post TEXT,

    -- Метаданные
    content_hash TEXT NOT NULL,
    category TEXT CHECK(category IN ('kitchen', 'kids', 'home', 'finance', 'planning', 'other')),
    relevance_score REAL CHECK(relevance_score >= 0 AND relevance_score <= 10),
    complexity TEXT CHECK(complexity IN ('beginner', 'intermediate', 'advanced')) DEFAULT 'beginner',

    -- Изображения
    image_prompt TEXT,
    image_url TEXT,

    -- Партнёрские ссылки
    affiliate_links TEXT, -- JSON array

    -- Статусы и временные метки
    status TEXT CHECK(status IN (
        'pending',      -- Ожидает обработки
        'filtered',     -- Отфильтрован (низкий скор или дубликат)
        'processing',   -- В обработке
        'ready',        -- Готов к публикации
        'queued',       -- В очереди публикации
        'published',    -- Опубликован
        'failed'        -- Ошибка
    )) DEFAULT 'pending',

    filter_reason TEXT, -- Причина фильтрации

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    processed_at DATETIME,
    published_at DATETIME,

    -- Telegram
    telegram_message_id TEXT,
    telegram_views INTEGER DEFAULT 0,
    telegram_reactions INTEGER DEFAULT 0,

    -- Retry logic
    retry_count INTEGER DEFAULT 0,
    last_error TEXT
);

-- Векторная таблица для семантической дедупликации
-- Используется sqlite-vec расширение
-- CREATE VIRTUAL TABLE IF NOT EXISTS vec_content USING vec0(
--     content_embedding float[384]  -- all-MiniLM-L6-v2 dimensions
-- );

-- Таблица RSS-источников
CREATE TABLE IF NOT EXISTS rss_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    url TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,

    -- Категоризация
    language TEXT CHECK(language IN ('ru', 'en')) DEFAULT 'ru',
    primary_category TEXT,

    -- Настройки парсинга
    fetch_interval_minutes INTEGER DEFAULT 60,
    max_items_per_fetch INTEGER DEFAULT 10,

    -- Статус
    is_active BOOLEAN DEFAULT 1,
    last_fetched_at DATETIME,
    last_item_guid TEXT,

    -- Статистика
    total_items_fetched INTEGER DEFAULT 0,
    items_accepted INTEGER DEFAULT 0,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Очередь публикаций
CREATE TABLE IF NOT EXISTS publish_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    content_id INTEGER NOT NULL REFERENCES content(id) ON DELETE CASCADE,

    scheduled_time DATETIME NOT NULL,
    category TEXT,
    priority INTEGER DEFAULT 5 CHECK(priority >= 1 AND priority <= 10),

    status TEXT CHECK(status IN ('queued', 'publishing', 'published', 'failed')) DEFAULT 'queued',

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    published_at DATETIME
);

-- Аналитика постов
CREATE TABLE IF NOT EXISTS post_analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    content_id INTEGER NOT NULL REFERENCES content(id) ON DELETE CASCADE,

    -- Метрики Telegram
    views_1h INTEGER DEFAULT 0,
    views_24h INTEGER DEFAULT 0,
    views_total INTEGER DEFAULT 0,

    reactions_total INTEGER DEFAULT 0,
    forwards INTEGER DEFAULT 0,

    -- Вычисляемые метрики
    engagement_rate REAL,

    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Лог партнёрских кликов
CREATE TABLE IF NOT EXISTS affiliate_clicks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    content_id INTEGER REFERENCES content(id),
    affiliate_program TEXT NOT NULL,
    link_url TEXT NOT NULL,

    clicked_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- ИНДЕКСЫ
-- ============================================

CREATE INDEX IF NOT EXISTS idx_content_status ON content(status);
CREATE INDEX IF NOT EXISTS idx_content_category ON content(category);
CREATE INDEX IF NOT EXISTS idx_content_hash ON content(content_hash);
CREATE INDEX IF NOT EXISTS idx_content_created ON content(created_at);
CREATE INDEX IF NOT EXISTS idx_content_source ON content(source_name);

CREATE INDEX IF NOT EXISTS idx_rss_active ON rss_sources(is_active);
CREATE INDEX IF NOT EXISTS idx_rss_next_fetch ON rss_sources(last_fetched_at);

CREATE INDEX IF NOT EXISTS idx_queue_scheduled ON publish_queue(scheduled_time);
CREATE INDEX IF NOT EXISTS idx_queue_status ON publish_queue(status);

-- ============================================
-- ПРЕДСТАВЛЕНИЯ (Views)
-- ============================================

-- Готовый к публикации контент
CREATE VIEW IF NOT EXISTS v_ready_to_publish AS
SELECT
    c.id,
    c.processed_title,
    c.telegram_post,
    c.category,
    c.image_url,
    c.relevance_score
FROM content c
WHERE c.status = 'ready'
ORDER BY c.relevance_score DESC;

-- Статистика по источникам
CREATE VIEW IF NOT EXISTS v_source_stats AS
SELECT
    rs.name,
    rs.language,
    rs.total_items_fetched,
    rs.items_accepted,
    ROUND(rs.items_accepted * 100.0 / NULLIF(rs.total_items_fetched, 0), 1) as acceptance_rate,
    rs.last_fetched_at
FROM rss_sources rs
WHERE rs.is_active = 1
ORDER BY acceptance_rate DESC;

-- Ежедневная статистика
CREATE VIEW IF NOT EXISTS v_daily_stats AS
SELECT
    DATE(created_at) as date,
    COUNT(*) as total_collected,
    SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) as published,
    SUM(CASE WHEN status = 'filtered' THEN 1 ELSE 0 END) as filtered,
    AVG(relevance_score) as avg_relevance
FROM content
GROUP BY DATE(created_at)
ORDER BY date DESC;
