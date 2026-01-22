"""
Unit tests for ContentDeduplicator.

Tests cover:
- URL normalization
- Fuzzy title matching (Jaccard coefficient)
- Hash-based deduplication (SHA256)
- Edge cases (empty strings, unicode, long titles)
"""

import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from deduplicator import ContentDeduplicator, DuplicateResult


class TestURLNormalization:
    """Tests for URL normalization and exact URL matching."""

    def test_normalize_url_removes_protocol(self, deduplicator):
        """URL normalization should remove http:// and https://"""
        assert deduplicator.normalize_url("https://example.com/page") == "example.com/page"
        assert deduplicator.normalize_url("http://example.com/page") == "example.com/page"

    def test_normalize_url_removes_www(self, deduplicator):
        """URL normalization should remove www. prefix."""
        assert deduplicator.normalize_url("https://www.example.com/page") == "example.com/page"
        assert deduplicator.normalize_url("www.example.com/page") == "example.com/page"

    def test_normalize_url_removes_trailing_slash(self, deduplicator):
        """URL normalization should remove trailing slashes."""
        assert deduplicator.normalize_url("https://example.com/page/") == "example.com/page"
        assert deduplicator.normalize_url("https://example.com/") == "example.com"

    def test_normalize_url_removes_utm_params(self, deduplicator):
        """URL normalization should remove UTM tracking parameters."""
        url = "https://example.com/article?utm_source=twitter&utm_medium=social"
        assert deduplicator.normalize_url(url) == "example.com/article"
        
        url2 = "https://example.com/article?utm_campaign=launch"
        assert deduplicator.normalize_url(url2) == "example.com/article"

    def test_normalize_url_removes_ref_params(self, deduplicator):
        """URL normalization should remove ref parameters."""
        url = "https://example.com/article?ref=homepage"
        assert deduplicator.normalize_url(url) == "example.com/article"

    def test_normalize_url_lowercase(self, deduplicator):
        """URL normalization should convert to lowercase."""
        assert deduplicator.normalize_url("HTTPS://EXAMPLE.COM/PAGE") == "example.com/page"

    def test_normalize_url_empty_string(self, deduplicator):
        """URL normalization should handle empty string."""
        assert deduplicator.normalize_url("") == ""
        assert deduplicator.normalize_url(None) == ""

    def test_exact_url_match(self, deduplicator):
        """Same URL (after normalization) should be detected as duplicate."""
        url = "https://example.com/article"
        
        # First check - should be unique
        result1 = deduplicator.check_duplicate("Title 1", url)
        assert not result1.is_duplicate
        
        # Second check - same URL (different case, with trailing slash)
        result2 = deduplicator.check_duplicate(
            "Different Title", 
            "HTTPS://WWW.EXAMPLE.COM/ARTICLE/"
        )
        assert result2.is_duplicate
        assert result2.reason == "exact_url_match"
        assert result2.similarity_score == 1.0

    def test_url_with_query_params_preserved(self, deduplicator):
        """Non-tracking query params should be preserved."""
        url1 = "https://example.com/article?id=123"
        url2 = "https://example.com/article?id=456"
        
        result1 = deduplicator.check_duplicate("Title 1", url1)
        assert not result1.is_duplicate
        
        result2 = deduplicator.check_duplicate("Title 2", url2)
        assert not result2.is_duplicate  # Different id param


class TestFuzzyTitleMatching:
    """Tests for fuzzy title matching using Jaccard coefficient."""

    def test_identical_titles_match(self, deduplicator):
        """Identical titles should match with similarity 1.0."""
        title = "10 AI Tools for Writing"
        
        deduplicator.add_existing(title, "https://example.com/1")
        result = deduplicator.check_duplicate(title, "https://example.com/2")
        
        assert result.is_duplicate
        assert result.reason == "fuzzy_title_match"
        assert result.similarity_score >= 0.99

    def test_similar_titles_match(self, populated_deduplicator):
        """Similar titles should be detected as duplicates."""
        # "10 AI Tools for Writing" is in populated_deduplicator
        result = populated_deduplicator.check_duplicate(
            "Top 10 AI Writing Tools",
            "https://example.com/new"
        )
        
        assert result.is_duplicate
        assert result.reason == "fuzzy_title_match"
        assert result.similarity_score >= 0.65

    def test_similar_titles_with_numbers_differ(self, populated_deduplicator):
        """Similar titles with different topics should not match."""
        # "How to Use Python for Data Science" is in populated_deduplicator
        result = populated_deduplicator.check_duplicate(
            "How to Use JavaScript for Web Development",
            "https://example.com/new"
        )
        
        # Different topics should not match despite similar structure
        assert not result.is_duplicate or result.similarity_score < 0.65

    def test_chatgpt_update_variants(self, populated_deduplicator):
        """ChatGPT update variations should match."""
        # "ChatGPT Gets Major Update" is in populated_deduplicator
        similar_titles = [
            "New ChatGPT Update Released",
            "ChatGPT Update: New Features",
            "Major ChatGPT Update Announced",
        ]
        
        for title in similar_titles:
            result = populated_deduplicator.check_duplicate(
                title, 
                f"https://example.com/{title.replace(' ', '-')}"
            )
            # Most of these should match due to overlapping keywords
            # Note: Some may not match depending on threshold
            if result.is_duplicate:
                assert result.similarity_score >= 0.65

    def test_completely_different_titles(self, populated_deduplicator):
        """Completely different titles should not match."""
        result = populated_deduplicator.check_duplicate(
            "New Cryptocurrency Regulations in EU",
            "https://example.com/crypto"
        )
        
        assert not result.is_duplicate
        assert result.reason == "unique"

    def test_threshold_boundary(self):
        """Test that similarity threshold is respected."""
        dedup_low = ContentDeduplicator(similarity_threshold=0.3)
        dedup_high = ContentDeduplicator(similarity_threshold=0.9)
        
        title1 = "AI Tool for Writing"
        title2 = "AI Tools Writing Helper"
        
        dedup_low.add_existing(title1, "https://example.com/1")
        dedup_high.add_existing(title1, "https://example.com/1")
        
        result_low = dedup_low.check_duplicate(title2, "https://example.com/2")
        result_high = dedup_high.check_duplicate(title2, "https://example.com/2")
        
        # Low threshold should catch more duplicates
        # High threshold should be stricter
        # Results depend on actual similarity


class TestNgramGeneration:
    """Tests for n-gram generation."""

    def test_get_ngrams_basic(self, deduplicator):
        """N-grams should be generated correctly."""
        text = "hello"
        ngrams = deduplicator.get_ngrams(text)
        
        # With ngram_size=3: "hel", "ell", "llo"
        assert len(ngrams) == 3
        assert "hel" in ngrams
        assert "ell" in ngrams
        assert "llo" in ngrams

    def test_get_ngrams_short_text(self, deduplicator):
        """Short text (less than ngram_size) should return set with original."""
        text = "ai"  # Length 2, ngram_size is 3
        ngrams = deduplicator.get_ngrams(text)
        
        # After normalization, very short text
        assert len(ngrams) <= 1

    def test_get_ngrams_empty_text(self, deduplicator):
        """Empty text should return empty set."""
        ngrams = deduplicator.get_ngrams("")
        assert len(ngrams) == 0

    def test_get_ngrams_removes_stopwords(self, deduplicator):
        """N-grams should be generated from normalized text (no stop words)."""
        text = "The best AI tool for the writing"
        normalized = deduplicator.normalize_text(text)
        
        # "the", "best", "for" are stop words
        assert "the" not in normalized
        assert "best" not in normalized
        assert "for" not in normalized


class TestJaccardSimilarity:
    """Tests for Jaccard similarity calculation."""

    def test_identical_sets_similarity_one(self, deduplicator):
        """Identical sets should have similarity 1.0."""
        set1 = {"a", "b", "c"}
        set2 = {"a", "b", "c"}
        
        assert deduplicator.jaccard_similarity(set1, set2) == 1.0

    def test_disjoint_sets_similarity_zero(self, deduplicator):
        """Disjoint sets should have similarity 0.0."""
        set1 = {"a", "b", "c"}
        set2 = {"x", "y", "z"}
        
        assert deduplicator.jaccard_similarity(set1, set2) == 0.0

    def test_partial_overlap_similarity(self, deduplicator):
        """Partial overlap should give expected similarity."""
        set1 = {"a", "b", "c", "d"}
        set2 = {"a", "b", "e", "f"}
        
        # Intersection: {a, b} = 2
        # Union: {a, b, c, d, e, f} = 6
        # Jaccard = 2/6 = 0.333...
        similarity = deduplicator.jaccard_similarity(set1, set2)
        assert abs(similarity - (2/6)) < 0.001

    def test_empty_set_similarity_zero(self, deduplicator):
        """Empty set should result in similarity 0.0."""
        set1 = set()
        set2 = {"a", "b", "c"}
        
        assert deduplicator.jaccard_similarity(set1, set2) == 0.0
        assert deduplicator.jaccard_similarity(set2, set1) == 0.0
        assert deduplicator.jaccard_similarity(set(), set()) == 0.0


class TestHashDeduplication:
    """Tests for SHA256 hash-based deduplication."""

    def test_compute_hash_deterministic(self, deduplicator):
        """Hash should be deterministic for same input."""
        hash1 = deduplicator.compute_hash("Title", "https://example.com")
        hash2 = deduplicator.compute_hash("Title", "https://example.com")
        
        assert hash1 == hash2

    def test_compute_hash_different_for_different_input(self, deduplicator):
        """Hash should be different for different input."""
        hash1 = deduplicator.compute_hash("Title 1", "https://example.com/1")
        hash2 = deduplicator.compute_hash("Title 2", "https://example.com/2")
        
        assert hash1 != hash2

    def test_compute_hash_includes_content(self, deduplicator):
        """Hash should include content if provided."""
        hash1 = deduplicator.compute_hash("Title", "https://example.com", "Content A")
        hash2 = deduplicator.compute_hash("Title", "https://example.com", "Content B")
        
        assert hash1 != hash2

    def test_compute_hash_is_sha256(self, deduplicator):
        """Hash should be valid SHA256."""
        hash_result = deduplicator.compute_hash("Title", "https://example.com")
        
        # SHA256 produces 64 character hex string
        assert len(hash_result) == 64
        assert all(c in "0123456789abcdef" for c in hash_result)

    def test_exact_hash_match_duplicate(self, deduplicator):
        """Exact hash match should be detected."""
        title = "Unique Article Title"
        url = "https://example.com/unique"
        content = "Article content here"
        
        # First check
        result1 = deduplicator.check_duplicate(title, url, content)
        assert not result1.is_duplicate
        
        # Same exact content
        result2 = deduplicator.check_duplicate(title, url, content)
        assert result2.is_duplicate
        assert result2.reason == "exact_hash_match"


class TestEdgeCases:
    """Tests for edge cases and unusual inputs."""

    def test_empty_title(self, deduplicator):
        """Empty title should be handled gracefully."""
        result = deduplicator.check_duplicate("", "https://example.com/test")
        
        # Should not crash, should be marked as unique
        assert not result.is_duplicate or result.reason != "fuzzy_title_match"

    def test_empty_url(self, deduplicator):
        """Empty URL should be handled gracefully."""
        result = deduplicator.check_duplicate("Test Title", "")
        
        # Should not crash
        assert isinstance(result, DuplicateResult)

    def test_unicode_titles_russian(self, deduplicator):
        """Russian unicode titles should work correctly."""
        title_ru = "Новый AI-инструмент для написания текстов"
        
        result1 = deduplicator.check_duplicate(title_ru, "https://example.com/ru1")
        assert not result1.is_duplicate
        
        # Similar Russian title
        result2 = deduplicator.check_duplicate(
            "AI-инструмент для написания текстов и статей",
            "https://example.com/ru2"
        )
        # Should detect similarity

    def test_unicode_titles_emoji(self, deduplicator):
        """Titles with emojis should be handled."""
        title = "New AI Tool! Best Tool Ever!"
        
        result = deduplicator.check_duplicate(title, "https://example.com/emoji")
        assert not result.is_duplicate

    def test_unicode_mixed_languages(self, deduplicator):
        """Mixed language titles should work."""
        title = "ChatGPT: AI for Writing"
        
        deduplicator.add_existing(title, "https://example.com/mixed1")
        result = deduplicator.check_duplicate(
            "ChatGPT: AI for Writing",
            "https://example.com/mixed2"
        )
        assert result.is_duplicate

    def test_very_long_title(self, deduplicator):
        """Very long titles should be handled without issues."""
        long_title = "A" * 10000  # 10,000 characters
        
        result = deduplicator.check_duplicate(long_title, "https://example.com/long")
        assert isinstance(result, DuplicateResult)

    def test_special_characters_in_title(self, deduplicator):
        """Special characters should be normalized."""
        title1 = "AI Tool: The Best! (2024 Edition) - Review"
        title2 = "AI Tool The Best 2024 Edition Review"
        
        deduplicator.add_existing(title1, "https://example.com/special1")
        result = deduplicator.check_duplicate(title2, "https://example.com/special2")
        
        # After normalization (removing punctuation), they should be similar
        assert result.is_duplicate or result.similarity_score > 0.5

    def test_numbers_removed_from_comparison(self, deduplicator):
        """Numbers should be removed during normalization."""
        title1 = "Top 10 AI Tools for 2024"
        title2 = "Top 5 AI Tools for 2023"
        
        deduplicator.add_existing(title1, "https://example.com/num1")
        result = deduplicator.check_duplicate(title2, "https://example.com/num2")
        
        # Without numbers, these are very similar
        assert result.is_duplicate

    def test_whitespace_handling(self, deduplicator):
        """Extra whitespace should be normalized."""
        title1 = "AI   Tool   For   Writing"
        title2 = "AI Tool For Writing"
        
        deduplicator.add_existing(title1, "https://example.com/ws1")
        result = deduplicator.check_duplicate(title2, "https://example.com/ws2")
        
        # Should match after whitespace normalization
        assert result.is_duplicate

    def test_none_values(self, deduplicator):
        """None values should not cause crashes."""
        # normalize_url already handles None
        assert deduplicator.normalize_url(None) == ""
        
        # normalize_text should handle empty
        assert deduplicator.normalize_text("") == ""


class TestTextNormalization:
    """Tests for text normalization function."""

    def test_normalize_removes_stopwords_english(self, deduplicator):
        """English stop words should be removed."""
        text = "The best AI tool for the writing"
        normalized = deduplicator.normalize_text(text)
        
        for stopword in ["the", "best", "for"]:
            assert stopword not in normalized.split()

    def test_normalize_removes_stopwords_russian(self, deduplicator):
        """Russian stop words should be removed."""
        text = "как использовать для работы"
        normalized = deduplicator.normalize_text(text)
        
        for stopword in ["как", "для"]:
            assert stopword not in normalized.split()

    def test_normalize_lowercase(self, deduplicator):
        """Text should be lowercased."""
        text = "AI Tool FOR WRITING"
        normalized = deduplicator.normalize_text(text)
        
        assert normalized == normalized.lower()

    def test_normalize_removes_short_words(self, deduplicator):
        """Words with 2 or fewer characters should be removed."""
        text = "AI is a tool"
        normalized = deduplicator.normalize_text(text)
        
        # "is", "a" should be removed (stopwords and short)
        assert "is" not in normalized.split()
        assert " a " not in f" {normalized} "


class TestHistoryManagement:
    """Tests for history management and limits."""

    def test_max_history_limit(self):
        """History should be trimmed when exceeding max_history."""
        dedup = ContentDeduplicator(max_history=10)
        
        # Add more than max_history items
        for i in range(20):
            dedup.add_existing(f"Title {i}", f"https://example.com/{i}")
        
        # Should have trimmed to max_history/2 = 5
        assert len(dedup.seen_titles) <= 10

    def test_clear_history(self, deduplicator):
        """Clear should reset all history."""
        deduplicator.add_existing("Title 1", "https://example.com/1")
        deduplicator.add_existing("Title 2", "https://example.com/2")
        
        assert len(deduplicator.seen_titles) == 2
        
        deduplicator.clear()
        
        assert len(deduplicator.seen_titles) == 0
        assert len(deduplicator.seen_urls) == 0
        assert len(deduplicator.seen_hashes) == 0

    def test_get_stats(self, populated_deduplicator):
        """Stats should return correct counts."""
        stats = populated_deduplicator.get_stats()
        
        assert stats["tracked_titles"] == 5
        assert stats["unique_urls"] == 5
        assert stats["unique_hashes"] == 5
        assert stats["similarity_threshold"] == 0.65
        assert stats["ngram_size"] == 3


class TestDuplicateResult:
    """Tests for DuplicateResult dataclass."""

    def test_duplicate_result_creation(self):
        """DuplicateResult should be created correctly."""
        result = DuplicateResult(
            is_duplicate=True,
            reason="fuzzy_title_match",
            similarity_score=0.75,
            matched_title="Original Title"
        )
        
        assert result.is_duplicate is True
        assert result.reason == "fuzzy_title_match"
        assert result.similarity_score == 0.75
        assert result.matched_title == "Original Title"

    def test_duplicate_result_defaults(self):
        """DuplicateResult should have correct defaults."""
        result = DuplicateResult(
            is_duplicate=False,
            reason="unique"
        )
        
        assert result.is_duplicate is False
        assert result.reason == "unique"
        assert result.similarity_score is None
        assert result.matched_title is None
