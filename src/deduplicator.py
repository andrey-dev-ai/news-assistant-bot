"""Content deduplication with exact and fuzzy matching for @ai_dlya_doma channel."""

import hashlib
import re
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

from logger import get_logger

logger = get_logger("news_bot.deduplicator")


@dataclass
class DuplicateResult:
    """Result of duplicate check."""

    is_duplicate: bool
    reason: str
    similarity_score: Optional[float] = None
    matched_title: Optional[str] = None


class ContentDeduplicator:
    """
    Deduplicator with exact match (hash) and fuzzy match (n-gram similarity).

    Uses Jaccard coefficient on character n-grams for fuzzy matching.
    This catches similar headlines like:
    - "10 AI Tools for Writing" vs "Top 10 AI Writing Tools"
    - "ChatGPT Update" vs "ChatGPT Gets New Update"
    """

    # Stop words to remove for normalization (English + Russian)
    STOP_WORDS = {
        # English
        "the",
        "a",
        "an",
        "is",
        "are",
        "for",
        "to",
        "of",
        "and",
        "in",
        "on",
        "with",
        "best",
        "top",
        "new",
        "how",
        "what",
        "why",
        "this",
        "that",
        "your",
        "you",
        "can",
        "will",
        # Russian
        "как",
        "что",
        "это",
        "для",
        "на",
        "по",
        "из",
        "от",
        "за",
        "до",
        "при",
        "без",
        "под",
        "над",
        "или",
        "но",
        "да",
        "не",
        "же",
        "ли",
        "бы",
        "вот",
        "все",
        "уже",
        "еще",
        "так",
        "там",
        "тут",
        "тоже",
        "очень",
        "только",
        "можно",
        "нужно",
        "лучший",
        "лучшие",
        "новый",
        "новые",
        "топ",
    }

    def __init__(
        self,
        similarity_threshold: float = 0.65,
        ngram_size: int = 3,
        max_history: int = 10000,
    ):
        """
        Initialize deduplicator.

        Args:
            similarity_threshold: Minimum Jaccard similarity to consider as duplicate (0.0-1.0)
            ngram_size: Size of character n-grams for fuzzy matching
            max_history: Maximum number of items to keep in memory
        """
        self.similarity_threshold = similarity_threshold
        self.ngram_size = ngram_size
        self.max_history = max_history

        self.seen_hashes: Set[str] = set()
        self.seen_urls: Set[str] = set()
        self.seen_titles: List[Tuple[str, str]] = []  # (original, normalized)

        logger.info(
            f"Deduplicator initialized: threshold={similarity_threshold}, "
            f"ngram_size={ngram_size}, max_history={max_history}"
        )

    def normalize_text(self, text: str) -> str:
        """
        Normalize text for comparison.

        - Lowercase
        - Remove punctuation
        - Remove stop words
        - Collapse whitespace
        """
        if not text:
            return ""

        # Lowercase
        text = text.lower()

        # Remove punctuation and special characters
        text = re.sub(r"[^\w\s]", "", text)

        # Remove numbers (they often differ in similar articles)
        text = re.sub(r"\d+", "", text)

        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()

        # Remove stop words
        words = [w for w in text.split() if w not in self.STOP_WORDS and len(w) > 2]

        return " ".join(words)

    def normalize_url(self, url: str) -> str:
        """Normalize URL for comparison."""
        if not url:
            return ""

        url = url.lower().strip()

        # Remove protocol
        url = re.sub(r"^https?://", "", url)

        # Remove www.
        url = re.sub(r"^www\.", "", url)

        # Remove trailing slash
        url = url.rstrip("/")

        # Remove common tracking parameters
        url = re.sub(r"\?utm_[^&]+(&utm_[^&]+)*", "", url)
        url = re.sub(r"\?ref=[^&]+", "", url)
        url = re.sub(r"[?&]$", "", url)

        return url

    def get_ngrams(self, text: str) -> Set[str]:
        """Generate character n-grams from text."""
        normalized = self.normalize_text(text)
        if len(normalized) < self.ngram_size:
            return {normalized} if normalized else set()

        return {
            normalized[i : i + self.ngram_size]
            for i in range(len(normalized) - self.ngram_size + 1)
        }

    def jaccard_similarity(self, set1: Set[str], set2: Set[str]) -> float:
        """Calculate Jaccard similarity coefficient between two sets."""
        if not set1 or not set2:
            return 0.0

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0

    def compute_hash(
        self, title: str, url: str, content: Optional[str] = None
    ) -> str:
        """Compute SHA-256 hash for exact matching."""
        hash_input = f"{title}|{url}"
        if content:
            hash_input += f"|{content[:500]}"

        return hashlib.sha256(hash_input.encode()).hexdigest()

    def check_duplicate(
        self,
        title: str,
        url: str,
        content: Optional[str] = None,
    ) -> DuplicateResult:
        """
        Check if content is a duplicate.

        Performs three levels of checking:
        1. Exact URL match
        2. Exact hash match (title + url + content)
        3. Fuzzy title match using n-gram similarity

        Args:
            title: Article title
            url: Article URL
            content: Optional article content/description

        Returns:
            DuplicateResult with is_duplicate, reason, and similarity score
        """
        # 1. Exact URL match
        url_normalized = self.normalize_url(url)
        if url_normalized and url_normalized in self.seen_urls:
            logger.debug(f"Exact URL match: {url_normalized}")
            return DuplicateResult(
                is_duplicate=True,
                reason="exact_url_match",
                similarity_score=1.0,
            )

        # 2. Exact hash match
        content_hash = self.compute_hash(title, url, content)
        if content_hash in self.seen_hashes:
            logger.debug(f"Exact hash match for: {title[:50]}...")
            return DuplicateResult(
                is_duplicate=True,
                reason="exact_hash_match",
                similarity_score=1.0,
            )

        # 3. Fuzzy title match
        title_ngrams = self.get_ngrams(title)
        if title_ngrams:
            for original_title, normalized_title in self.seen_titles:
                seen_ngrams = self.get_ngrams(original_title)
                similarity = self.jaccard_similarity(title_ngrams, seen_ngrams)

                if similarity >= self.similarity_threshold:
                    logger.info(
                        f"Fuzzy match ({similarity:.2f}): "
                        f"'{title[:40]}...' ~ '{original_title[:40]}...'"
                    )
                    return DuplicateResult(
                        is_duplicate=True,
                        reason="fuzzy_title_match",
                        similarity_score=similarity,
                        matched_title=original_title,
                    )

        # Not a duplicate - save for future checks
        self._add_to_history(title, url, url_normalized, content_hash)

        return DuplicateResult(
            is_duplicate=False,
            reason="unique",
        )

    def _add_to_history(
        self, title: str, url: str, url_normalized: str, content_hash: str
    ):
        """Add item to history, respecting max_history limit."""
        if url_normalized:
            self.seen_urls.add(url_normalized)

        self.seen_hashes.add(content_hash)

        normalized_title = self.normalize_text(title)
        self.seen_titles.append((title, normalized_title))

        # Trim history if needed
        if len(self.seen_titles) > self.max_history:
            # Keep the most recent half
            keep_count = self.max_history // 2
            self.seen_titles = self.seen_titles[-keep_count:]
            logger.info(f"Trimmed title history to {keep_count} items")

    def add_existing(
        self, title: str, url: str, content: Optional[str] = None
    ):
        """
        Add an existing item to the deduplicator without checking.
        Useful for loading existing posts from database.
        """
        url_normalized = self.normalize_url(url)
        content_hash = self.compute_hash(title, url, content)
        self._add_to_history(title, url, url_normalized, content_hash)

    def get_stats(self) -> dict:
        """Get deduplicator statistics."""
        return {
            "unique_urls": len(self.seen_urls),
            "unique_hashes": len(self.seen_hashes),
            "tracked_titles": len(self.seen_titles),
            "similarity_threshold": self.similarity_threshold,
            "ngram_size": self.ngram_size,
            "max_history": self.max_history,
        }

    def clear(self):
        """Clear all history."""
        self.seen_hashes.clear()
        self.seen_urls.clear()
        self.seen_titles.clear()
        logger.info("Deduplicator history cleared")


# Global instance for use across modules
_deduplicator: Optional[ContentDeduplicator] = None


def get_deduplicator(
    similarity_threshold: float = 0.65,
    ngram_size: int = 3,
    max_history: int = 10000,
) -> ContentDeduplicator:
    """Get or create the global deduplicator instance."""
    global _deduplicator
    if _deduplicator is None:
        _deduplicator = ContentDeduplicator(
            similarity_threshold=similarity_threshold,
            ngram_size=ngram_size,
            max_history=max_history,
        )
    return _deduplicator


if __name__ == "__main__":
    # Test the deduplicator
    dedup = ContentDeduplicator(similarity_threshold=0.65)

    # Test cases
    test_cases = [
        ("10 AI Tools for Writing", "https://example.com/1"),
        ("Top 10 AI Writing Tools", "https://example.com/2"),  # Fuzzy match
        ("Best AI Writing Tools 2024", "https://example.com/3"),  # Fuzzy match
        ("ChatGPT Gets Major Update", "https://example.com/4"),
        ("New ChatGPT Update Released", "https://example.com/5"),  # Fuzzy match
        ("Canva Launches AI Photo Editor", "https://example.com/6"),
        ("How to Use Python for Data Science", "https://example.com/7"),  # Different
    ]

    print("Testing deduplicator:\n")
    for title, url in test_cases:
        result = dedup.check_duplicate(title, url)
        status = "DUPLICATE" if result.is_duplicate else "UNIQUE"
        score = f" ({result.similarity_score:.2f})" if result.similarity_score else ""
        matched = f" -> '{result.matched_title[:30]}...'" if result.matched_title else ""
        print(f"[{status}] {title[:50]}{score}{matched}")

    print(f"\nStats: {dedup.get_stats()}")
