"""
Basic entity extraction for OSINT semantic enrichment.

This module provides regex-based named entity recognition focused on
military units, locations, and military-related entities for the PoC.
For production, this should be replaced with spaCy or LLM-based NER.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

# Military unit patterns (English and Ukrainian)
MILITARY_UNIT_PATTERNS = [
    # English brigade/battalion/regiment patterns
    r'\b\d{1,3}(?:st|nd|rd|th)?\s+(?:Brigade|Battalion|Regiment|Division)\b',
    r'\b\d{1,3}(?:st|nd|rd|th)?\s+(?:Mechanized|Airborne|Infantry|Tank|Artillery)\s+(?:Brigade|Battalion|Regiment|Division)\b',
    # Ukrainian brigade notation (e.g., "93 ОМБр")
    r'\b\d{1,3}\s*ОМБр\b',  # Окрема механізована бригада (Separate Mechanized Brigade)
    r'\b\d{1,3}\s*ОШБр\b',  # Окрема штурмова бригада (Separate Assault Brigade)
    r'\b\d{1,3}\s*ОДШБр\b',  # Окрема десантно-штурмова бригада (Separate Air Assault Brigade)
    # Named military groups
    r'\bWagner\s+Group\b',
    r'\bAzov\s+(?:Battalion|Regiment|Brigade)\b',
    r'\bKraken\s+(?:Battalion|Regiment|Unit)\b',
    # Military force abbreviations
    r'\b(?:AFU|Armed Forces of Ukraine|UAF)\b',
    r'\bЗСУ\b',  # Збройні Сили України (Armed Forces of Ukraine)
    r'\b(?:RF|Russian Forces|Armed Forces of Russia)\b',
    r'\bВС\s+РФ\b',  # Вооруженные Силы РФ (Armed Forces of Russia)
]

# Location patterns (major Ukraine cities and regions)
# Note: Ukrainian patterns include common case endings and stem changes
# (Ukrainian nouns change stems in different grammatical cases)
LOCATION_PATTERNS = [
    # Major cities (case-insensitive matching with Ukrainian case endings)
    r'\bBakhmut\w*\b',
    r'\bБахмут[іуа]?\b',
    r'\b(?:Kyiv|Kiev)\w*\b',
    r'\bКи[їі]в[іуа]?\b',  # Київ, Києві, Києву
    r'\bKharkiv\w*\b',
    r'\bХарк[іо]в[іуа]?\b',  # Харків, Харкові, Харкову (stem vowel changes і/о)
    r'\bMariupol\w*\b',
    r'\bМаріупол[ьіюя]?\b',
    r'\bDonetsk\w*\b',
    r'\bДонецьк[уа]?\b',
    r'\bLuhansk\w*\b',
    r'\bЛуганськ[уа]?\b',
    r'\bDnipro\w*\b',
    r'\bДніпр[оуа]?\b',
    r'\b(?:Odesa|Odessa)\w*\b',
    r'\bОдес[іуа]?\b',
    r'\bZaporizhzhia\w*\b',
    r'\bЗапоріжж[яі]?\b',
    r'\bKherson\w*\b',
    r'\bХерсон[іуа]?\b',
    r'\bMykolaiv\w*\b',
    r'\bМиколаїв[іуа]?\b',
    r'\bLviv\w*\b',
    r'\bЛьвів[іуа]?\b',
    r'\bSeverodonetsk\w*\b',
    r'\bСєвєродонецьк[уа]?\b',
    r'\bLysychansk\w*\b',
    r'\bЛисичанськ[уа]?\b',
    r'\bAvdiivka\w*\b',
    r'\bАвдіївк[іа]?\b',
    r'\bVuhledar\w*\b',
    r'\bВугледар[уа]?\b',
    r'\bChasiv\s+Yar\w*\b',
    r'\bЧасів\s+Яр[уа]?\b',
    r'\bSoledar\w*\b',
    r'\bСоледар[уа]?\b',
]

# Direction patterns (front lines, directions)
DIRECTION_PATTERNS = [
    r'\b(Eastern\s+Front|Східний\s+фронт)\b',
    r'\b(Southern\s+Front|Південний\s+фронт)\b',
    r'\b(Northern\s+Front|Північний\s+фронт)\b',
    r'\b(Donbas|Донбас)\b',
    r'\b(Crimea|Крим)\b',
]


@dataclass
class ExtractedEntity:
    """
    Represents a single extracted entity with metadata.

    Attributes:
        text: The exact text of the entity as found in the message
        type: Entity type (MILITARY_UNIT, LOCATION, DIRECTION)
        confidence: Confidence score (0.0-1.0)
        position_start: Start position in text
        position_end: End position in text
    """

    text: str
    type: str
    confidence: float = 1.0
    position_start: int = 0
    position_end: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert entity to dictionary."""
        return {
            "text": self.text,
            "type": self.type,
            "confidence": self.confidence,
            "position_start": self.position_start,
            "position_end": self.position_end,
        }


@dataclass
class ExtractedEntities:
    """
    Results of entity extraction analysis.

    Attributes:
        military_units: List of military unit names found
        locations: List of location names found
        directions: List of direction/front names found
        all_entities: List of all extracted entities with metadata
    """

    military_units: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    directions: list[str] = field(default_factory=list)
    all_entities: list[ExtractedEntity] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert extraction results to dictionary."""
        return {
            "military_units": self.military_units,
            "locations": self.locations,
            "directions": self.directions,
            "all_entities": [entity.to_dict() for entity in self.all_entities],
        }


class EntityExtractor:
    """
    Regex-based entity extractor for military-focused OSINT analysis.

    This is a simplified PoC implementation using regex patterns.
    For production, consider using spaCy NER or LLM-based extraction.
    """

    def __init__(self):
        """Initialize entity extractor with compiled regex patterns."""
        # Compile patterns for performance
        self.military_patterns = [re.compile(p, re.IGNORECASE) for p in MILITARY_UNIT_PATTERNS]
        self.location_patterns = [re.compile(p, re.IGNORECASE) for p in LOCATION_PATTERNS]
        self.direction_patterns = [re.compile(p, re.IGNORECASE) for p in DIRECTION_PATTERNS]

        logger.info("Initialized EntityExtractor with regex patterns")

    def _extract_by_patterns(
        self, text: str, patterns: list[re.Pattern], entity_type: str, confidence: float = 0.9
    ) -> list[ExtractedEntity]:
        """
        Extract entities using regex patterns.

        Args:
            text: Text to extract entities from
            patterns: List of compiled regex patterns
            entity_type: Type of entity being extracted
            confidence: Confidence score for regex matches

        Returns:
            List of extracted entities with metadata
        """
        entities = []
        seen_texts = set()  # Avoid duplicates

        for pattern in patterns:
            for match in pattern.finditer(text):
                entity_text = match.group(0)
                normalized_text = entity_text.strip()

                # Skip if we've already seen this exact text
                if normalized_text.lower() in seen_texts:
                    continue

                seen_texts.add(normalized_text.lower())

                entities.append(
                    ExtractedEntity(
                        text=normalized_text,
                        type=entity_type,
                        confidence=confidence,
                        position_start=match.start(),
                        position_end=match.end(),
                    )
                )

        return entities

    def extract_entities(self, text: str) -> ExtractedEntities:
        """
        Extract all entities from text.

        Args:
            text: Message text to analyze

        Returns:
            ExtractedEntities with all found entities
        """
        if not text:
            logger.debug("Empty text provided for entity extraction")
            return ExtractedEntities()

        # Extract each entity type
        military_entities = self._extract_by_patterns(
            text, self.military_patterns, "MILITARY_UNIT", confidence=0.9
        )
        location_entities = self._extract_by_patterns(
            text, self.location_patterns, "LOCATION", confidence=0.95
        )
        direction_entities = self._extract_by_patterns(
            text, self.direction_patterns, "DIRECTION", confidence=0.85
        )

        # Combine all entities
        all_entities = military_entities + location_entities + direction_entities

        # Sort by position in text
        all_entities.sort(key=lambda e: e.position_start)

        # Build result
        result = ExtractedEntities(
            military_units=[e.text for e in military_entities],
            locations=[e.text for e in location_entities],
            directions=[e.text for e in direction_entities],
            all_entities=all_entities,
        )

        logger.info(
            f"Extracted {len(result.all_entities)} entities: "
            f"{len(result.military_units)} military units, "
            f"{len(result.locations)} locations, "
            f"{len(result.directions)} directions"
        )

        return result
