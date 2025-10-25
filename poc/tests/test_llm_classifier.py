"""
Tests for LLM-based message classification.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.enrichment.llm_classifier import (
    SPAM_PATTERNS,
    VALID_TOPICS,
    LLMClassifier,
    MessageClassification,
)


class TestMessageClassification:
    """Test MessageClassification dataclass."""

    def test_message_classification_creation(self):
        """Test creating MessageClassification instance."""
        classification = MessageClassification(
            is_spam=False,
            osint_value=75,
            topics=["combat", "equipment"],
            reasoning="High value tactical report",
            confidence=0.9,
        )

        assert classification.is_spam is False
        assert classification.osint_value == 75
        assert classification.topics == ["combat", "equipment"]
        assert classification.reasoning == "High value tactical report"
        assert classification.confidence == 0.9
        assert classification.spam_reasons == []

    def test_message_classification_to_dict(self):
        """Test converting classification to dictionary."""
        classification = MessageClassification(
            is_spam=True,
            spam_reasons=["card_numbers"],
            osint_value=0,
            topics=["general"],
            reasoning="Spam detected",
            confidence=1.0,
        )

        result = classification.to_dict()

        assert result == {
            "is_spam": True,
            "spam_reasons": ["card_numbers"],
            "osint_value": 0,
            "topics": ["general"],
            "reasoning": "Spam detected",
            "confidence": 1.0,
        }


class TestSpamDetection:
    """Test spam detection patterns."""

    def test_detect_card_numbers(self):
        """Test detection of credit card numbers."""
        classifier = LLMClassifier(api_key="test-key")

        # Test with card number
        is_spam, patterns = classifier._detect_spam("Support us: 1234 5678 9012 3456")
        assert is_spam is True
        assert "card_numbers" in patterns

        # Test with hyphenated card number
        is_spam, patterns = classifier._detect_spam("Card: 1234-5678-9012-3456")
        assert is_spam is True
        assert "card_numbers" in patterns

        # Test without card number
        is_spam, patterns = classifier._detect_spam("No card here")
        assert "card_numbers" not in patterns

    def test_detect_donation_keywords(self):
        """Test detection of donation/donation keywords."""
        classifier = LLMClassifier(api_key="test-key")

        test_cases = [
            ("Donate to our cause", True),
            ("донат на карту", True),
            ("підтримайте нас", True),
            ("support us please", True),
            ("поддержите проект", True),
            ("Regular message", False),
        ]

        for text, should_detect in test_cases:
            is_spam, patterns = classifier._detect_spam(text)
            if should_detect:
                assert "donation_keywords" in patterns, f"Failed to detect in: {text}"
            else:
                assert "donation_keywords" not in patterns, f"False positive in: {text}"

    def test_detect_excessive_emojis(self):
        """Test detection of excessive monetary emojis."""
        classifier = LLMClassifier(api_key="test-key")

        # Test with excessive emojis
        is_spam, patterns = classifier._detect_spam("Help us! 💰💰💰💰")
        assert is_spam is True
        assert "excessive_emojis" in patterns

        # Test with fire emojis
        is_spam, patterns = classifier._detect_spam("Hot deal 🔥🔥🔥")
        assert is_spam is True
        assert "excessive_emojis" in patterns

        # Test with few emojis (not spam)
        is_spam, patterns = classifier._detect_spam("Good news 🔥")
        assert "excessive_emojis" not in patterns

    def test_multiple_spam_patterns(self):
        """Test message with multiple spam indicators."""
        classifier = LLMClassifier(api_key="test-key")

        text = "Donate 💰💰💰 to card 1234-5678-9012-3456"
        is_spam, patterns = classifier._detect_spam(text)

        assert is_spam is True
        assert len(patterns) >= 2
        assert "card_numbers" in patterns
        assert "excessive_emojis" in patterns


class TestLLMClassifier:
    """Test LLM classifier functionality."""

    def test_classifier_initialization(self):
        """Test classifier initialization."""
        classifier = LLMClassifier(api_key="test-key-123", model="test-model")

        assert classifier.model == "test-model"
        assert classifier.client is not None

    def test_build_classification_prompt(self):
        """Test building classification prompt."""
        classifier = LLMClassifier(api_key="test-key")

        text = "Russian forces attacked Kharkiv today"
        prompt = classifier._build_classification_prompt(text)

        assert text in prompt
        assert "OSINT" in prompt
        assert "90-100" in prompt  # Value guidelines
        assert "combat" in prompt  # Topics
        assert "civilian" in prompt
        assert "JSON" in prompt

    def test_parse_llm_response_valid_json(self):
        """Test parsing valid LLM JSON response."""
        classifier = LLMClassifier(api_key="test-key")

        response = """{
            "osint_value": 85,
            "topics": ["combat", "equipment"],
            "reasoning": "Reports enemy equipment destruction"
        }"""

        result = classifier._parse_llm_response(response)

        assert result["osint_value"] == 85
        assert result["topics"] == ["combat", "equipment"]
        assert "equipment destruction" in result["reasoning"]

    def test_parse_llm_response_with_markdown(self):
        """Test parsing LLM response wrapped in markdown code blocks."""
        classifier = LLMClassifier(api_key="test-key")

        response = """```json
{
    "osint_value": 70,
    "topics": ["civilian"],
    "reasoning": "Civilian casualties reported"
}
```"""

        result = classifier._parse_llm_response(response)

        assert result["osint_value"] == 70
        assert result["topics"] == ["civilian"]

    def test_parse_llm_response_invalid_topics(self):
        """Test parsing response with invalid topics filters them out."""
        classifier = LLMClassifier(api_key="test-key")

        response = """{
            "osint_value": 50,
            "topics": ["combat", "invalid_topic", "diplomatic"],
            "reasoning": "Mixed content"
        }"""

        result = classifier._parse_llm_response(response)

        assert result["osint_value"] == 50
        assert "invalid_topic" not in result["topics"]
        assert "combat" in result["topics"]
        assert "diplomatic" in result["topics"]

    def test_parse_llm_response_no_valid_topics(self):
        """Test parsing response with no valid topics defaults to general."""
        classifier = LLMClassifier(api_key="test-key")

        response = """{
            "osint_value": 30,
            "topics": ["invalid1", "invalid2"],
            "reasoning": "Off-topic"
        }"""

        result = classifier._parse_llm_response(response)

        assert result["topics"] == ["general"]

    def test_parse_llm_response_value_clamping(self):
        """Test OSINT value is clamped to 0-100 range."""
        classifier = LLMClassifier(api_key="test-key")

        # Test over 100
        response_high = """{
            "osint_value": 150,
            "topics": ["combat"],
            "reasoning": "Test"
        }"""
        result = classifier._parse_llm_response(response_high)
        assert result["osint_value"] == 100

        # Test under 0
        response_low = """{
            "osint_value": -50,
            "topics": ["general"],
            "reasoning": "Test"
        }"""
        result = classifier._parse_llm_response(response_low)
        assert result["osint_value"] == 0

    def test_parse_llm_response_invalid_json(self):
        """Test parsing invalid JSON returns safe defaults."""
        classifier = LLMClassifier(api_key="test-key")

        response = "This is not JSON at all"
        result = classifier._parse_llm_response(response)

        assert result["osint_value"] == 0
        assert result["topics"] == ["general"]
        assert "Failed to parse" in result["reasoning"]

    def test_parse_llm_response_malformed_json(self):
        """Test parsing malformed JSON returns safe defaults."""
        classifier = LLMClassifier(api_key="test-key")

        response = '{"osint_value": 50, "topics": ['
        result = classifier._parse_llm_response(response)

        assert result["osint_value"] == 0
        assert result["topics"] == ["general"]

    @patch("src.enrichment.llm_classifier.Together")
    def test_classify_message_sync_spam(self, mock_together_class):
        """Test synchronous classification of spam message."""
        classifier = LLMClassifier(api_key="test-key")

        # Spam message should not call LLM
        text = "Donate now! 💰💰💰 Card: 1234-5678-9012-3456"
        result = classifier.classify_message_sync(text)

        assert result.is_spam is True
        assert len(result.spam_reasons) >= 2
        assert result.osint_value == 0
        assert result.confidence == 1.0

    @patch("src.enrichment.llm_classifier.Together")
    def test_classify_message_sync_legitimate(self, mock_together_class):
        """Test synchronous classification of legitimate message."""
        # Mock Together API response
        mock_client = MagicMock()
        mock_together_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(
            {
                "osint_value": 85,
                "topics": ["combat", "equipment"],
                "reasoning": "Enemy tank destroyed near Bakhmut",
            }
        )
        mock_client.chat.completions.create.return_value = mock_response

        classifier = LLMClassifier(api_key="test-key")

        text = "Ukrainian forces destroyed enemy tank near Bakhmut today"
        result = classifier.classify_message_sync(text)

        assert result.is_spam is False
        assert result.spam_reasons == []
        assert result.osint_value == 85
        assert "combat" in result.topics
        assert "equipment" in result.topics
        assert result.confidence == 0.8

        # Verify LLM was called
        mock_client.chat.completions.create.assert_called_once()

    @patch("src.enrichment.llm_classifier.Together")
    def test_classify_message_sync_llm_error(self, mock_together_class):
        """Test classification when LLM API fails."""
        # Mock Together API to raise exception
        mock_client = MagicMock()
        mock_together_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        classifier = LLMClassifier(api_key="test-key")

        text = "Legitimate message"
        result = classifier.classify_message_sync(text)

        assert result.is_spam is False
        assert result.osint_value == 0
        assert result.topics == ["general"]
        assert "Classification error" in result.reasoning
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    @patch("src.enrichment.llm_classifier.Together")
    async def test_classify_message_async(self, mock_together_class):
        """Test async classification of message."""
        # Mock Together API response
        mock_client = MagicMock()
        mock_together_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(
            {
                "osint_value": 65,
                "topics": ["diplomatic"],
                "reasoning": "Diplomatic statement on negotiations",
            }
        )
        mock_client.chat.completions.create.return_value = mock_response

        classifier = LLMClassifier(api_key="test-key")

        text = "President discusses peace negotiations"
        result = await classifier.classify_message(text)

        assert result.is_spam is False
        assert result.osint_value == 65
        assert "diplomatic" in result.topics
        assert result.confidence == 0.8

    @pytest.mark.asyncio
    @patch("src.enrichment.llm_classifier.Together")
    async def test_classify_message_async_spam(self, mock_together_class):
        """Test async classification detects spam without calling LLM."""
        classifier = LLMClassifier(api_key="test-key")

        text = "підтримайте донатом! 💰💰💰"
        result = await classifier.classify_message(text)

        assert result.is_spam is True
        assert result.osint_value == 0


class TestConstants:
    """Test module constants."""

    def test_spam_patterns_defined(self):
        """Test spam patterns are properly defined."""
        assert "card_numbers" in SPAM_PATTERNS
        assert "donation_keywords" in SPAM_PATTERNS
        assert "excessive_emojis" in SPAM_PATTERNS

        # Test patterns are valid regex
        for _pattern_name, pattern_regex in SPAM_PATTERNS.items():
            import re

            # Should not raise exception
            re.compile(pattern_regex)

    def test_valid_topics_defined(self):
        """Test valid topics are defined."""
        assert "combat" in VALID_TOPICS
        assert "civilian" in VALID_TOPICS
        assert "diplomatic" in VALID_TOPICS
        assert "equipment" in VALID_TOPICS
        assert "general" in VALID_TOPICS
        assert len(VALID_TOPICS) == 5
