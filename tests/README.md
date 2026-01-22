# Test Suite for news-assistant-bot

## Directory Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── unit/                    # Unit tests
│   ├── test_deduplicator.py # Deduplicator tests (URL, fuzzy, hash)
│   ├── test_database.py     # Database and queue tests
│   └── test_post_generator.py # Post generation tests
├── golden_tests/            # Golden tests for prompts
│   ├── data/
│   │   └── golden_inputs.json # Test cases and anti-patterns
│   └── test_prompt_format.py  # Format validation tests
└── integration/             # Integration tests
    ├── test_full_pipeline.py  # End-to-end pipeline tests
    └── test_api_mocks.py      # API interaction tests
```

## Running Tests

### Install test dependencies

```bash
pip install pytest pytest-cov pytest-timeout
```

### Run all tests

```bash
pytest
```

### Run specific test categories

```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/ -m integration

# Golden tests only
pytest tests/golden_tests/ -m golden

# Skip slow tests
pytest -m "not slow"

# Skip tests requiring real API
pytest -m "not api"
```

### Run with coverage

```bash
# Run with coverage report
pytest --cov=src --cov-report=html --cov-report=term-missing

# Generate HTML coverage report
open htmlcov/index.html
```

### Run specific test file

```bash
pytest tests/unit/test_deduplicator.py -v
```

### Run specific test class or function

```bash
# Run specific class
pytest tests/unit/test_deduplicator.py::TestURLNormalization -v

# Run specific test
pytest tests/unit/test_deduplicator.py::TestURLNormalization::test_normalize_url_removes_protocol -v
```

## Test Markers

- `@pytest.mark.unit` - Unit tests (fast, isolated)
- `@pytest.mark.integration` - Integration tests (slower, test interactions)
- `@pytest.mark.golden` - Golden tests (prompt format validation)
- `@pytest.mark.slow` - Slow tests (database, multiple API calls)
- `@pytest.mark.api` - Tests requiring real API access (disabled by default)

## Key Fixtures

### Database fixtures

```python
@pytest.fixture
def test_database(temp_db_path):
    """Fresh database instance"""

@pytest.fixture
def populated_database(test_database):
    """Database with sample data"""
```

### Deduplicator fixtures

```python
@pytest.fixture
def deduplicator():
    """Fresh ContentDeduplicator"""

@pytest.fixture
def populated_deduplicator(deduplicator):
    """Deduplicator with sample titles"""
```

### Mock API fixtures

```python
@pytest.fixture
def mock_anthropic_client():
    """Mocked Anthropic client"""

@pytest.fixture
def mock_telegram_api():
    """Mocked Telegram API"""
```

### Sample data fixtures

```python
@pytest.fixture
def sample_articles():
    """List of sample articles"""

@pytest.fixture
def sample_relevant_article():
    """Article that should be classified as relevant"""

@pytest.fixture
def sample_irrelevant_article():
    """Article that should be filtered out"""
```

## Golden Tests

Golden tests validate prompt format without API calls:

1. **Anti-pattern detection** - Forbidden words/phrases
2. **Format validation** - Required sections for each post type
3. **Style checks** - Emoji count, sentence length, etc.

### Adding new golden test cases

Edit `tests/golden_tests/data/golden_inputs.json`:

```json
{
  "test_cases": [
    {
      "id": "new_test_case",
      "article": {
        "title": "...",
        "source": "...",
        "summary": "...",
        "link": "..."
      },
      "expected_classification": {
        "relevant": true,
        "min_confidence": 70,
        "expected_format": "ai_tool"
      }
    }
  ]
}
```

## Coverage Requirements

- **Minimum coverage**: 70%
- **Critical modules** (deduplicator, post_generator): 80%+

## CI Integration

Tests run automatically on:
- Every push to main
- Every pull request

Coverage reports are uploaded to the PR as comments.

## Troubleshooting

### ImportError: No module named 'src.xxx'

Make sure `pythonpath = src` is in pytest.ini or run:
```bash
PYTHONPATH=src pytest
```

### Tests hanging

Check for:
- Real API calls (should use mocks)
- Infinite loops in test code
- Missing fixtures

### Flaky tests

If tests pass/fail randomly:
- Check for state leakage between tests
- Use `@pytest.fixture` with `scope="function"` for isolation
- Clear global state in fixtures
