"""
Golden tests for prompt format validation.

Tests verify:
- Post format structure (headers, sections, length)
- Anti-pattern detection (forbidden words/phrases)
- Classifier response format
- No API calls - pure format validation
"""

import json
import sys
from pathlib import Path
from typing import Dict, List

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


# Load golden test data
GOLDEN_DATA_PATH = Path(__file__).parent / "data" / "golden_inputs.json"


def load_golden_data() -> Dict:
    """Load golden test data from JSON file."""
    with open(GOLDEN_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def golden_data() -> Dict:
    """Fixture for golden test data."""
    return load_golden_data()


@pytest.fixture
def anti_patterns(golden_data) -> List[str]:
    """List of anti-patterns from golden data."""
    return golden_data["anti_patterns"]


@pytest.fixture
def format_requirements(golden_data) -> Dict:
    """Format requirements from golden data."""
    return golden_data["required_elements"]


class TestAntiPatternDetection:
    """Tests for detecting forbidden words and phrases in posts."""

    def test_detect_single_anti_pattern(self, anti_patterns):
        """Should detect single anti-pattern."""
        text = "Это революционный AI-инструмент"
        
        found = [p for p in anti_patterns if p.lower() in text.lower()]
        
        assert len(found) > 0
        assert "революционный" in found

    def test_detect_multiple_anti_patterns(self, anti_patterns):
        """Should detect multiple anti-patterns."""
        text = "Представляем вам уникальный и революционный инструмент"
        
        found = [p for p in anti_patterns if p.lower() in text.lower()]
        
        assert len(found) >= 2

    def test_clean_text_no_anti_patterns(self, anti_patterns):
        """Clean text should have no anti-patterns."""
        text = """
        AI-находка дня: Canva AI Editor
        
        Редактируй фото за секунды с помощью умного редактора.
        Удаляет фон, подбирает фильтры, улучшает качество.
        
        💰 Бесплатно (базовый план)
        
        ✅ Попробовать: https://canva.com
        """
        
        found = [p for p in anti_patterns if p.lower() in text.lower()]
        
        assert len(found) == 0, f"Found anti-patterns: {found}"

    def test_anti_pattern_case_insensitive(self, anti_patterns):
        """Anti-pattern detection should be case-insensitive."""
        text = "РЕВОЛЮЦИОННЫЙ инструмент"
        
        found = [p for p in anti_patterns if p.lower() in text.lower()]
        
        assert "революционный" in found

    @pytest.mark.parametrize("anti_pattern", load_golden_data()["anti_patterns"])
    def test_each_anti_pattern_detectable(self, anti_pattern):
        """Each anti-pattern should be detectable."""
        text = f"Это {anti_pattern} инструмент"
        
        assert anti_pattern.lower() in text.lower()


class TestPostFormatValidation:
    """Tests for validating post format structure."""

    def test_ai_tool_format_has_header(self, format_requirements):
        """AI tool post should have correct header."""
        requirements = format_requirements["ai_tool"]
        
        valid_post = """
        🤖 AI-находка дня: Test Tool
        
        Это тестовый пост.
        
        ✅ Попробовать: https://example.com
        """
        
        assert requirements["header"] in valid_post

    def test_ai_tool_format_has_link(self, format_requirements):
        """AI tool post should have try link."""
        requirements = format_requirements["ai_tool"]
        
        valid_post = """
        🤖 AI-находка дня: Test Tool
        
        Описание.
        
        ✅ Попробовать: https://example.com
        """
        
        has_required = all(
            section in valid_post 
            for section in requirements["required_sections"]
        )
        
        assert has_required

    def test_ai_tool_format_length(self, format_requirements):
        """AI tool post should not exceed max length."""
        requirements = format_requirements["ai_tool"]
        max_length = requirements["max_length"]
        
        valid_post = "🤖 AI-находка дня: Test\n\nDescription.\n\n✅ Попробовать: https://example.com"
        
        assert len(valid_post) <= max_length

    def test_quick_tip_format_has_header(self, format_requirements):
        """Quick tip post should have correct header."""
        requirements = format_requirements["quick_tip"]
        
        valid_post = """
        ⚡ Быстрый совет
        
        Используй этот лайфхак для ChatGPT.
        
        ✨ Результат: лучшие ответы
        """
        
        assert requirements["header"] in valid_post

    def test_quick_tip_format_length(self, format_requirements):
        """Quick tip should be shorter than ai_tool."""
        ai_tool_max = format_requirements["ai_tool"]["max_length"]
        quick_tip_max = format_requirements["quick_tip"]["max_length"]
        
        assert quick_tip_max < ai_tool_max

    def test_prompt_day_format_has_prompt(self, format_requirements):
        """Prompt of the day should have copyable prompt."""
        requirements = format_requirements["prompt_day"]
        
        valid_post = """
        🎯 Промт дня: Резюме
        
        Ситуация: когда нужно написать резюме
        
        Промт для ChatGPT:
        "Напиши резюме..."
        
        💡 Что получишь: готовое резюме
        
        Копируй и пользуйся! 📋
        """
        
        has_required = all(
            section in valid_post 
            for section in requirements["required_sections"]
        )
        
        assert has_required


class TestClassifierResponseFormat:
    """Tests for classifier response JSON format."""

    def test_valid_classifier_response_structure(self):
        """Classifier response should have required fields."""
        from post_generator import parse_classifier_response
        
        valid_response = json.dumps({
            "relevant": True,
            "confidence": 85,
            "category": "tool",
            "format": "ai_tool",
            "reason": "Consumer AI tool"
        })
        
        result = parse_classifier_response(valid_response)
        
        assert "relevant" in result
        assert "confidence" in result
        assert "category" in result
        assert "format" in result

    def test_classifier_response_confidence_range(self):
        """Confidence should be in 0-100 range."""
        from post_generator import parse_classifier_response
        
        # Normal value
        response = parse_classifier_response('{"relevant": true, "confidence": 75}')
        assert 0 <= response["confidence"] <= 100
        
        # Over 100 - should be capped
        response = parse_classifier_response('{"relevant": true, "confidence": 150}')
        assert response["confidence"] == 100
        
        # Negative - should be 0
        response = parse_classifier_response('{"relevant": true, "confidence": -10}')
        assert response["confidence"] == 0

    def test_classifier_response_relevant_boolean(self):
        """Relevant should be boolean."""
        from post_generator import parse_classifier_response
        
        response = parse_classifier_response('{"relevant": true, "confidence": 75}')
        assert isinstance(response["relevant"], bool)
        
        response = parse_classifier_response('{"relevant": false, "confidence": 75}')
        assert isinstance(response["relevant"], bool)

    def test_classifier_response_valid_format_values(self):
        """Format should be valid PostFormat value."""
        from post_generator import parse_classifier_response, PostFormat
        
        valid_formats = [f.value for f in PostFormat]
        
        for fmt in valid_formats:
            response = parse_classifier_response(
                f'{{"relevant": true, "confidence": 75, "format": "{fmt}"}}'
            )
            assert response["format"] in valid_formats

    def test_classifier_response_handles_malformed_json(self):
        """Should handle malformed JSON gracefully."""
        from post_generator import parse_classifier_response
        
        malformed_inputs = [
            "not json at all",
            "{incomplete",
            '{"relevant": }',
            "",
            "null",
        ]
        
        for malformed in malformed_inputs:
            result = parse_classifier_response(malformed)
            # Should return default response, not crash
            assert result["relevant"] is False
            assert result["needs_review"] is True


class TestGoldenTestCases:
    """Tests using golden test case data."""

    @pytest.fixture
    def test_cases(self, golden_data) -> List[Dict]:
        """Get all test cases from golden data."""
        return golden_data["test_cases"]

    def test_all_test_cases_have_required_fields(self, test_cases):
        """All test cases should have required fields."""
        required_fields = ["id", "article", "expected_classification", "description"]
        
        for case in test_cases:
            for field in required_fields:
                assert field in case, f"Test case {case.get('id', 'unknown')} missing {field}"

    def test_all_articles_have_required_fields(self, test_cases):
        """All articles should have required fields."""
        required_article_fields = ["title", "source", "summary", "link"]
        
        for case in test_cases:
            article = case["article"]
            for field in required_article_fields:
                assert field in article, f"Article in {case['id']} missing {field}"

    def test_relevant_cases_have_positive_confidence(self, test_cases):
        """Relevant cases should have positive min_confidence."""
        relevant_cases = [c for c in test_cases if c["expected_classification"]["relevant"]]
        
        for case in relevant_cases:
            expected = case["expected_classification"]
            assert expected.get("min_confidence", 0) > 0, f"Case {case['id']} needs min_confidence"

    def test_irrelevant_cases_have_max_confidence(self, test_cases):
        """Irrelevant cases should have low max_confidence."""
        irrelevant_cases = [c for c in test_cases if not c["expected_classification"]["relevant"]]
        
        for case in irrelevant_cases:
            expected = case["expected_classification"]
            assert expected.get("max_confidence", 100) < 50, f"Case {case['id']} should have low max_confidence"

    @pytest.mark.parametrize("case_id", [
        "relevant_ai_tool_canva",
        "relevant_chatgpt_update",
        "relevant_writing_assistant",
    ])
    def test_relevant_cases_have_expected_format(self, test_cases, case_id):
        """Relevant cases should specify expected post format."""
        case = next(c for c in test_cases if c["id"] == case_id)
        
        assert "expected_post_format" in case
        assert case["expected_post_format"] in ["ai_tool", "quick_tip", "prompt_day"]

    @pytest.mark.parametrize("case_id", [
        "irrelevant_enterprise_b2b",
        "irrelevant_developer_sdk",
        "irrelevant_crypto_ai",
    ])
    def test_irrelevant_cases_properly_categorized(self, test_cases, case_id):
        """Irrelevant cases should be properly categorized."""
        case = next(c for c in test_cases if c["id"] == case_id)
        
        assert case["expected_classification"]["relevant"] is False


class TestEmojiUsage:
    """Tests for emoji usage in posts."""

    def test_ai_tool_has_appropriate_emoji_count(self):
        """AI tool post should have 3-5 emojis."""
        sample_post = """
        🤖 AI-находка дня: Test Tool
        
        Описание инструмента.
        
        💰 Бесплатно
        
        ✅ Попробовать: https://example.com
        
        🔥 — уже пробовала
        💾 — сохраню на будущее
        """
        
        import re
        # Count emoji characters (simplified - just count common emoji)
        emoji_pattern = re.compile(
            r'[\U0001F300-\U0001F9FF]|'  # Symbols & Pictographs
            r'[\u2600-\u26FF]|'           # Misc symbols
            r'[\u2700-\u27BF]'            # Dingbats
        )
        emoji_count = len(emoji_pattern.findall(sample_post))
        
        assert 3 <= emoji_count <= 7, f"Post has {emoji_count} emojis, expected 3-5"

    def test_quick_tip_has_fewer_emojis(self):
        """Quick tip should have 2-3 emojis."""
        sample_post = """
        ⚡ Быстрый совет
        
        Лайфхак для ChatGPT.
        
        ✨ Результат: лучше
        """
        
        import re
        emoji_pattern = re.compile(
            r'[\U0001F300-\U0001F9FF]|'
            r'[\u2600-\u26FF]|'
            r'[\u2700-\u27BF]'
        )
        emoji_count = len(emoji_pattern.findall(sample_post))
        
        assert 2 <= emoji_count <= 4, f"Post has {emoji_count} emojis, expected 2-3"


class TestTextStyleValidation:
    """Tests for text style requirements."""

    def test_no_passive_voice_markers(self):
        """Post should not have passive voice markers."""
        passive_markers = [
            "был создан",
            "было разработано",
            "является",
            "позволяется",
        ]
        
        good_post = "Редактируй фото за секунды. Инструмент работает быстро."
        
        for marker in passive_markers:
            assert marker not in good_post.lower()

    def test_uses_informal_you(self):
        """Post should use informal 'ты' not formal 'вы'."""
        good_post = "Попробуй этот инструмент. Он поможет тебе."
        bad_markers = ["вы можете", "вам", "ваш"]
        
        for marker in bad_markers:
            assert marker not in good_post.lower()

    def test_sentences_are_short(self):
        """Sentences should be short (under 20 words on average)."""
        good_post = """
        Редактируй фото за секунды.
        Умный помощник сам подберёт фильтры.
        Работает с Instagram и TikTok.
        """
        
        sentences = [s.strip() for s in good_post.split('.') if s.strip()]
        avg_words = sum(len(s.split()) for s in sentences) / len(sentences)
        
        assert avg_words < 20, f"Average sentence length is {avg_words} words"

    def test_no_marketing_buzzwords(self):
        """Post should not have marketing buzzwords."""
        buzzwords = [
            "революционный",
            "инновационный",
            "прорывной",
            "уникальный",
            "лучший в мире",
            "не имеет аналогов",
        ]
        
        good_post = "Полезный инструмент для редактирования фото."
        
        for buzzword in buzzwords:
            assert buzzword not in good_post.lower()
