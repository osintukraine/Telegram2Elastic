"""
LLM-based message classification for OSINT semantic enrichment.

This module provides spam detection, OSINT value scoring, and topic
classification using Together.ai LLM API with rule-based fallbacks.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any

from loguru import logger
from together import Together

# Spam detection patterns for rule-based filtering
SPAM_PATTERNS = {
    "card_numbers": r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
    "donation_keywords": r"\b(донат|donate|підтримайте|support us|поддержите|донатить)\b",
    "excessive_emojis": r"(💰|💳|🔥){3,}",
}

# Valid topic categories for classification
VALID_TOPICS = ["combat", "civilian", "diplomatic", "equipment", "general"]


@dataclass
class MessageClassification:
    """
    Results of message classification analysis.

    Attributes:
        is_spam: Whether message is classified as spam
        spam_reasons: List of detected spam patterns
        osint_value: Intelligence value score (0-100)
        topics: Classified message topics
        reasoning: LLM explanation of classification
        confidence: Confidence score of classification (0-1)
    """

    is_spam: bool
    spam_reasons: list[str] = field(default_factory=list)
    osint_value: int = 0
    topics: list[str] = field(default_factory=list)
    reasoning: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert classification to dictionary."""
        return {
            "is_spam": self.is_spam,
            "spam_reasons": self.spam_reasons,
            "osint_value": self.osint_value,
            "topics": self.topics,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
        }


class LLMClassifier:
    """
    LLM-based message classifier using Together.ai API.

    Provides spam detection using rule-based patterns and OSINT value
    scoring with topic classification using LLM inference.
    """

    def __init__(self, api_key: str, model: str = "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"):
        """
        Initialize LLM classifier.

        Args:
            api_key: Together.ai API key
            model: LLM model to use for classification
        """
        self.client = Together(api_key=api_key)
        self.model = model
        logger.info(f"Initialized LLMClassifier with model: {model}")

    def _detect_spam(self, text: str) -> tuple[bool, list[str]]:
        """
        Detect spam using rule-based pattern matching.

        Args:
            text: Message text to analyze

        Returns:
            Tuple of (is_spam, list of detected patterns)
        """
        detected_patterns = []

        for pattern_name, pattern_regex in SPAM_PATTERNS.items():
            if re.search(pattern_regex, text, re.IGNORECASE):
                detected_patterns.append(pattern_name)
                logger.debug(f"Detected spam pattern: {pattern_name}")

        is_spam = len(detected_patterns) > 0
        return is_spam, detected_patterns

    def _build_classification_prompt(self, text: str) -> str:
        """
        Build LLM prompt for OSINT value scoring and topic classification.

        Args:
            text: Message text to analyze

        Returns:
            Formatted prompt string
        """
        prompt = f"""Analyze this Telegram message from Ukraine war monitoring channels.

Message: {text}

Evaluate the OSINT (Open Source Intelligence) value of this message and classify its topics.

OSINT Value Guidelines:
- 90-100: Critical military intelligence (troop movements, casualties, strategic positions)
- 70-89: High value tactical information (equipment sightings, combat reports)
- 50-69: Moderate intelligence value (general updates, situational reports)
- 30-49: Low intelligence value (opinions, analysis, secondary sources)
- 0-29: Minimal/no intelligence value (spam, off-topic, promotional)

Topic Categories:
- combat: Direct combat operations, battles, strikes
- civilian: Civilian impact, casualties, humanitarian issues
- diplomatic: Political statements, negotiations, international relations
- equipment: Military equipment, vehicles, weapons
- general: General updates, news, other content

Return ONLY valid JSON (no markdown, no code blocks):
{{
  "osint_value": <0-100>,
  "topics": [<list of relevant topics from categories above>],
  "reasoning": "<brief 1-2 sentence explanation>"
}}"""
        return prompt

    def _parse_llm_response(self, response_text: str) -> dict[str, Any]:
        """
        Parse LLM JSON response with error handling.

        Args:
            response_text: Raw LLM response text

        Returns:
            Parsed JSON dictionary or default values on error
        """
        try:
            # Try to extract JSON from markdown code blocks if present
            if "```json" in response_text:
                json_match = re.search(r"```json\s*(\{.*?\})\s*```", response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)
            elif "```" in response_text:
                json_match = re.search(r"```\s*(\{.*?\})\s*```", response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)

            # Parse JSON
            data = json.loads(response_text.strip())

            # Validate and normalize
            osint_value = max(0, min(100, int(data.get("osint_value", 0))))
            topics = [t for t in data.get("topics", []) if t in VALID_TOPICS]
            if not topics:
                topics = ["general"]
            reasoning = str(data.get("reasoning", ""))[:500]  # Limit length

            return {
                "osint_value": osint_value,
                "topics": topics,
                "reasoning": reasoning,
            }

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            logger.debug(f"Raw response: {response_text}")
            # Return safe defaults
            return {
                "osint_value": 0,
                "topics": ["general"],
                "reasoning": "Failed to parse LLM response",
            }

    async def classify_message(self, text: str) -> MessageClassification:
        """
        Classify message for spam, OSINT value, and topics.

        Args:
            text: Message text to classify

        Returns:
            MessageClassification with analysis results
        """
        # Step 1: Rule-based spam detection
        is_spam, spam_reasons = self._detect_spam(text)

        # If spam detected, return early with low value
        if is_spam:
            logger.info(f"Message classified as spam: {spam_reasons}")
            return MessageClassification(
                is_spam=True,
                spam_reasons=spam_reasons,
                osint_value=0,
                topics=["general"],
                reasoning="Message flagged as spam by rule-based detection",
                confidence=1.0,
            )

        # Step 2: LLM classification for OSINT value and topics
        try:
            prompt = self._build_classification_prompt(text)

            logger.debug(f"Sending classification request to {self.model}")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.1,  # Low temperature for consistent classification
            )

            response_text = response.choices[0].message.content
            logger.debug(f"LLM response: {response_text}")

            # Parse LLM response
            llm_result = self._parse_llm_response(response_text)

            return MessageClassification(
                is_spam=False,
                spam_reasons=[],
                osint_value=llm_result["osint_value"],
                topics=llm_result["topics"],
                reasoning=llm_result["reasoning"],
                confidence=0.8,  # Default confidence for successful LLM call
            )

        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            # Return safe defaults on error
            return MessageClassification(
                is_spam=False,
                spam_reasons=[],
                osint_value=0,
                topics=["general"],
                reasoning=f"Classification error: {str(e)[:100]}",
                confidence=0.0,
            )

    def classify_message_sync(self, text: str) -> MessageClassification:
        """
        Synchronous version of classify_message.

        Args:
            text: Message text to classify

        Returns:
            MessageClassification with analysis results
        """
        # Step 1: Rule-based spam detection
        is_spam, spam_reasons = self._detect_spam(text)

        # If spam detected, return early with low value
        if is_spam:
            logger.info(f"Message classified as spam: {spam_reasons}")
            return MessageClassification(
                is_spam=True,
                spam_reasons=spam_reasons,
                osint_value=0,
                topics=["general"],
                reasoning="Message flagged as spam by rule-based detection",
                confidence=1.0,
            )

        # Step 2: LLM classification for OSINT value and topics
        try:
            prompt = self._build_classification_prompt(text)

            logger.debug(f"Sending classification request to {self.model}")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.1,  # Low temperature for consistent classification
            )

            response_text = response.choices[0].message.content
            logger.debug(f"LLM response: {response_text}")

            # Parse LLM response
            llm_result = self._parse_llm_response(response_text)

            return MessageClassification(
                is_spam=False,
                spam_reasons=[],
                osint_value=llm_result["osint_value"],
                topics=llm_result["topics"],
                reasoning=llm_result["reasoning"],
                confidence=0.8,  # Default confidence for successful LLM call
            )

        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            # Return safe defaults on error
            return MessageClassification(
                is_spam=False,
                spam_reasons=[],
                osint_value=0,
                topics=["general"],
                reasoning=f"Classification error: {str(e)[:100]}",
                confidence=0.0,
            )
