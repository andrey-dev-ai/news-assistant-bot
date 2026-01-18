"""AI processor using Claude API for news summarization and translation."""

import os
from anthropic import Anthropic
from typing import List, Dict


class AIProcessor:
    """Process news articles using Claude AI."""

    def __init__(self, api_key: str = None):
        """Initialize Claude AI client."""
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")

        self.client = Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-20250514"

    def create_digest(self, articles: List[Dict], max_articles: int = 20) -> str:
        """
        Create a digest from news articles.

        Args:
            articles: List of news articles
            max_articles: Maximum number of articles to process

        Returns:
            Formatted digest in Russian
        """
        if not articles:
            return "Нет новых статей за указанный период."

        # Prepare articles text
        articles_text = self._format_articles_for_prompt(articles[:max_articles])

        # Create prompt
        prompt = f"""Ты - AI-ассистент, который помогает предпринимателю быть в курсе всех трендов и событий в области искусственного интеллекта.

Вот список статей о AI за последние 24 часа:

{articles_text}

Твоя задача:
1. Проанализируй ВСЕ эти статьи
2. Выбери 8-12 самых важных новостей для формирования ПОЛНОЙ КАРТИНЫ происходящего в AI

ПРИОРИТЕТЫ (распредели примерно 70/30):

🎯 **70% - ПРАКТИКА И БИЗНЕС** (топ-приоритет):
- Новые AI-инструменты, продукты, API (что можно использовать прямо сейчас)
- Инвестиции в AI-стартапы и успешные кейсы
- Бизнес-применения AI (что можно внедрить и монетизировать)
- Технологические прорывы с практической ценностью
- Тренды, которые влияют на бизнес

📰 **30% - КОНТЕКСТ И ПОВЕСТКА** (чтобы быть в теме):
- Регулирование AI (новые законы, ограничения, политика)
- Важные академические исследования (если меняют индустрию)
- Этика и безопасность AI (крупные дискуссии и события)
- Макротренды и стратегические прогнозы

3. Для каждой новости создай краткую выжимку (2-3 предложения) на русском
4. Переведи заголовок на русский
5. Добавь соответствующую иконку в начале (🚀💰💡🏛️🔬⚖️ и т.д.)
6. Укажи ссылку на оригинал

Формат ответа:

🚀 **[Заголовок на русском]**
[Краткое описание - почему это важно, что это значит для бизнеса/индустрии]
🔗 [Ссылка]

---

ВАЖНО:
- Пиши живым понятным языком
- Фокусируйся на том, ЧТО можно сделать с этой информацией
- НЕ упускай важные политические/регулятивные новости - они влияют на бизнес
- Убери только откровенно рекламные статьи и дубликаты
- Давай ПОЛНУЮ картину дня в AI-индустрии"""

        try:
            # Call Claude API
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0.7,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Extract response
            digest = message.content[0].text

            # Add header
            from datetime import datetime
            date_str = datetime.now().strftime("%d.%m.%Y")
            header = f"🤖 **AI News Digest - {date_str}**\n\n"

            return header + digest

        except Exception as e:
            print(f"Error calling Claude API: {e}")
            return f"Ошибка при создании дайджеста: {e}"

    def _format_articles_for_prompt(self, articles: List[Dict]) -> str:
        """Format articles for Claude prompt."""
        formatted = []
        for i, article in enumerate(articles, 1):
            text = f"{i}. **{article['title']}**\n"
            text += f"   Источник: {article['source']}\n"
            if article.get('summary'):
                # Clean HTML from summary
                summary = article['summary'].replace('<p>', '').replace('</p>', '')
                text += f"   Описание: {summary[:300]}...\n"
            text += f"   Ссылка: {article['link']}\n"
            formatted.append(text)

        return "\n".join(formatted)


if __name__ == "__main__":
    # Test the processor (requires API key in environment)
    from dotenv import load_dotenv
    load_dotenv()

    processor = AIProcessor()

    # Test with dummy articles
    test_articles = [
        {
            'title': 'OpenAI releases GPT-5',
            'source': 'TechCrunch',
            'summary': 'OpenAI announced the release of GPT-5 with major improvements.',
            'link': 'https://example.com/gpt5'
        },
        {
            'title': 'Google invests $100M in AI startup',
            'source': 'VentureBeat',
            'summary': 'Google announces major investment in promising AI company.',
            'link': 'https://example.com/investment'
        }
    ]

    print("Testing AI Processor...\n")
    digest = processor.create_digest(test_articles)
    print(digest)
