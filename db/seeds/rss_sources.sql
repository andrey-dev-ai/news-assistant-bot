-- ============================================
-- РУССКОЯЗЫЧНЫЕ ИСТОЧНИКИ
-- ============================================

INSERT OR IGNORE INTO rss_sources (url, name, language, primary_category, fetch_interval_minutes) VALUES

-- VC.ru
('https://vc.ru/rss/rubric/ai', 'VC.ru AI', 'ru', NULL, 30),

-- Хабр
('https://habr.com/ru/rss/hub/artificial_intelligence/all/', 'Хабр AI', 'ru', NULL, 60),

-- Tproger
('https://tproger.ru/feed/', 'Tproger', 'ru', NULL, 60);

-- ============================================
-- АНГЛОЯЗЫЧНЫЕ ИСТОЧНИКИ
-- ============================================

INSERT OR IGNORE INTO rss_sources (url, name, language, primary_category, fetch_interval_minutes) VALUES

-- The Verge AI
('https://www.theverge.com/rss/ai-artificial-intelligence/index.xml', 'The Verge AI', 'en', NULL, 60),

-- THE DECODER
('https://the-decoder.com/feed/', 'THE DECODER', 'en', NULL, 60),

-- TechCrunch AI
('https://techcrunch.com/category/artificial-intelligence/feed/', 'TechCrunch AI', 'en', NULL, 120),

-- Product Hunt (все продукты, фильтровать по AI)
('https://www.producthunt.com/feed', 'Product Hunt', 'en', NULL, 120),

-- MIT Technology Review AI
('https://www.technologyreview.com/topic/artificial-intelligence/feed', 'MIT Tech Review', 'en', NULL, 120),

-- VentureBeat AI
('https://venturebeat.com/category/ai/feed/', 'VentureBeat AI', 'en', NULL, 60),

-- AI News
('https://www.artificialintelligence-news.com/feed/', 'AI News', 'en', NULL, 60),

-- Last Week in AI
('https://lastweekin.ai/feed', 'Last Week in AI', 'en', NULL, 120);

-- ============================================
-- YOUTUBE КАНАЛЫ (RSS формат)
-- ============================================

INSERT OR IGNORE INTO rss_sources (url, name, language, primary_category, fetch_interval_minutes) VALUES

-- Matt Wolfe (Future Tools)
('https://www.youtube.com/feeds/videos.xml?channel_id=UCJIfeSCssxSC_Dhc5s7woww', 'Matt Wolfe', 'en', NULL, 360),

-- The AI Advantage
('https://www.youtube.com/feeds/videos.xml?channel_id=UCjq5_p9FKPuNrY0-YrNvxNA', 'The AI Advantage', 'en', NULL, 360),

-- AI Jason
('https://www.youtube.com/feeds/videos.xml?channel_id=UCfvG0JD0mJqLJpMpJQWyhWw', 'AI Jason', 'en', NULL, 360);
