"""
Tests for entity extractor module.

Test coverage:
- Military unit detection (English and Ukrainian)
- Location detection (major Ukrainian cities)
- Direction/front detection
- Confidence scoring
- Empty text handling
- Duplicate entity handling
"""

import pytest

from src.enrichment.entity_extractor import EntityExtractor, ExtractedEntities


class TestEntityExtractor:
    """Test cases for EntityExtractor class."""

    @pytest.fixture
    def extractor(self):
        """Create entity extractor instance for tests."""
        return EntityExtractor()

    def test_military_unit_english(self, extractor):
        """Test extraction of English military unit names."""
        text = "The 93rd Mechanized Brigade engaged the 47th Brigade near the front."

        result = extractor.extract_entities(text)

        assert len(result.military_units) == 2
        assert "93rd Mechanized Brigade" in result.military_units
        assert "47th Brigade" in result.military_units
        assert all(e.type == "MILITARY_UNIT" for e in result.all_entities if e.text in result.military_units)

    def test_military_unit_ukrainian(self, extractor):
        """Test extraction of Ukrainian military unit notation."""
        text = "Бійці 93 ОМБр та 25 ОДШБр продовжують наступ."

        result = extractor.extract_entities(text)

        assert len(result.military_units) == 2
        assert "93 ОМБр" in result.military_units
        assert "25 ОДШБр" in result.military_units

    def test_military_unit_named_groups(self, extractor):
        """Test extraction of named military groups."""
        text = "Wagner Group forces and Azov Battalion are engaged in combat."

        result = extractor.extract_entities(text)

        assert len(result.military_units) == 2
        assert "Wagner Group" in result.military_units
        assert "Azov Battalion" in result.military_units

    def test_military_unit_abbreviations(self, extractor):
        """Test extraction of military force abbreviations."""
        text = "AFU forces and ЗСУ units repelled the attack."

        result = extractor.extract_entities(text)

        assert len(result.military_units) >= 2
        assert "AFU" in result.military_units
        assert "ЗСУ" in result.military_units

    def test_location_detection_english(self, extractor):
        """Test extraction of major Ukrainian cities (English)."""
        text = "Fighting continues in Bakhmut and Mariupol. Kharkiv remains under bombardment."

        result = extractor.extract_entities(text)

        assert len(result.locations) == 3
        assert "Bakhmut" in result.locations
        assert "Mariupol" in result.locations
        assert "Kharkiv" in result.locations
        assert all(e.type == "LOCATION" for e in result.all_entities if e.text in result.locations)

    def test_location_detection_ukrainian(self, extractor):
        """Test extraction of Ukrainian city names in Cyrillic."""
        text = "Бої тривають у Бахмуті та Харкові."

        result = extractor.extract_entities(text)

        assert len(result.locations) == 2
        # Pattern matches with case endings and stem changes
        # (Ukrainian case system changes stems: Харків -> Харкові, Бахмут -> Бахмуті)
        bakhmut_found = any("Бахмут" in loc for loc in result.locations)
        kharkiv_found = any("Харк" in loc for loc in result.locations)  # Common root
        assert bakhmut_found, f"Expected Bakhmut variant, got: {result.locations}"
        assert kharkiv_found, f"Expected Kharkiv variant, got: {result.locations}"

    def test_location_kiev_variants(self, extractor):
        """Test that both Kiev and Kyiv spelling variants are detected."""
        text1 = "Reports from Kyiv indicate heavy shelling."
        text2 = "Reports from Kiev indicate heavy shelling."

        result1 = extractor.extract_entities(text1)
        result2 = extractor.extract_entities(text2)

        assert len(result1.locations) == 1
        assert len(result2.locations) == 1
        assert "Kyiv" in result1.locations or "Kiev" in result1.locations
        assert "Kyiv" in result2.locations or "Kiev" in result2.locations

    def test_direction_detection(self, extractor):
        """Test extraction of front/direction names."""
        text = "Activity on the Eastern Front and in Donbas region continues."

        result = extractor.extract_entities(text)

        assert len(result.directions) >= 2
        assert "Eastern Front" in result.directions
        assert "Donbas" in result.directions
        assert all(e.type == "DIRECTION" for e in result.all_entities if e.text in result.directions)

    def test_mixed_entities(self, extractor):
        """Test extraction with mixed entity types in one message."""
        text = """
        The 93rd Mechanized Brigade and AFU forces advanced near Bakhmut.
        Wagner Group retreated from positions in Donbas.
        """

        result = extractor.extract_entities(text)

        # Should have all entity types
        assert len(result.military_units) >= 2
        assert len(result.locations) >= 1
        assert len(result.directions) >= 1

        # Check all_entities combines everything
        total_entities = len(result.military_units) + len(result.locations) + len(result.directions)
        assert len(result.all_entities) == total_entities

    def test_confidence_scoring(self, extractor):
        """Test that entities have appropriate confidence scores."""
        text = "The 93rd Brigade is positioned near Bakhmut on the Eastern Front."

        result = extractor.extract_entities(text)

        # All regex matches should have high confidence
        for entity in result.all_entities:
            assert entity.confidence >= 0.8
            assert entity.confidence <= 1.0

        # Military units should have ~0.9 confidence
        military_entities = [e for e in result.all_entities if e.type == "MILITARY_UNIT"]
        for entity in military_entities:
            assert entity.confidence == 0.9

        # Locations should have ~0.95 confidence
        location_entities = [e for e in result.all_entities if e.type == "LOCATION"]
        for entity in location_entities:
            assert entity.confidence == 0.95

        # Directions should have ~0.85 confidence
        direction_entities = [e for e in result.all_entities if e.type == "DIRECTION"]
        for entity in direction_entities:
            assert entity.confidence == 0.85

    def test_entity_positions(self, extractor):
        """Test that entity positions are tracked correctly."""
        text = "93rd Brigade near Bakhmut"

        result = extractor.extract_entities(text)

        assert len(result.all_entities) >= 2

        # Entities should be sorted by position
        positions = [e.position_start for e in result.all_entities]
        assert positions == sorted(positions)

        # All positions should be valid
        for entity in result.all_entities:
            assert entity.position_start >= 0
            assert entity.position_end > entity.position_start
            assert entity.position_end <= len(text)

            # Verify the position matches the text
            extracted_text = text[entity.position_start : entity.position_end].strip()
            assert entity.text.lower() in extracted_text.lower()

    def test_empty_text(self, extractor):
        """Test handling of empty text input."""
        result = extractor.extract_entities("")

        assert result.military_units == []
        assert result.locations == []
        assert result.directions == []
        assert result.all_entities == []

    def test_none_text(self, extractor):
        """Test handling of None text input."""
        result = extractor.extract_entities(None)

        assert result.military_units == []
        assert result.locations == []
        assert result.directions == []
        assert result.all_entities == []

    def test_no_entities(self, extractor):
        """Test text with no recognizable entities."""
        text = "This is a generic message with no specific military or location information."

        result = extractor.extract_entities(text)

        assert result.military_units == []
        assert result.locations == []
        assert result.directions == []
        assert result.all_entities == []

    def test_duplicate_entity_handling(self, extractor):
        """Test that duplicate entities are not repeated."""
        text = "Bakhmut fighting continues. Heavy shelling in Bakhmut area. Bakhmut defenders hold."

        result = extractor.extract_entities(text)

        # Should only have one instance of Bakhmut
        assert len(result.locations) == 1
        assert "Bakhmut" in result.locations

    def test_case_insensitive_matching(self, extractor):
        """Test that pattern matching is case-insensitive."""
        text1 = "BAKHMUT under heavy fire"
        text2 = "bakhmut under heavy fire"
        text3 = "Bakhmut under heavy fire"

        result1 = extractor.extract_entities(text1)
        result2 = extractor.extract_entities(text2)
        result3 = extractor.extract_entities(text3)

        # All should detect Bakhmut
        assert len(result1.locations) == 1
        assert len(result2.locations) == 1
        assert len(result3.locations) == 1

    def test_to_dict_conversion(self, extractor):
        """Test conversion of results to dictionary format."""
        text = "93rd Brigade fighting in Bakhmut on Eastern Front."

        result = extractor.extract_entities(text)
        result_dict = result.to_dict()

        # Check structure
        assert "military_units" in result_dict
        assert "locations" in result_dict
        assert "directions" in result_dict
        assert "all_entities" in result_dict

        # Check types
        assert isinstance(result_dict["military_units"], list)
        assert isinstance(result_dict["locations"], list)
        assert isinstance(result_dict["directions"], list)
        assert isinstance(result_dict["all_entities"], list)

        # Check entity structure
        for entity_dict in result_dict["all_entities"]:
            assert "text" in entity_dict
            assert "type" in entity_dict
            assert "confidence" in entity_dict
            assert "position_start" in entity_dict
            assert "position_end" in entity_dict

    def test_real_world_message_example(self, extractor):
        """Test extraction from realistic message example."""
        text = """
        ⚡️ BREAKING: AFU 93rd Mechanized Brigade reports successful counteroffensive near Bakhmut.

        Wagner Group forces have withdrawn from positions in the Donbas region.
        Fighting continues in Mariupol and Kharkiv.

        The Eastern Front remains active with intense artillery exchanges.
        ЗСУ forces maintain defensive positions around Kyiv.
        """

        result = extractor.extract_entities(text)

        # Should detect multiple military units
        assert len(result.military_units) >= 3
        assert any("93rd" in unit for unit in result.military_units)
        assert any("Wagner" in unit for unit in result.military_units)
        assert any("AFU" in unit or "ЗСУ" in unit for unit in result.military_units)

        # Should detect multiple locations
        assert len(result.locations) >= 4
        assert any("Bakhmut" in loc for loc in result.locations)
        assert any("Mariupol" in loc for loc in result.locations)
        assert any("Kharkiv" in loc for loc in result.locations)
        assert any("Kyiv" in loc or "Kiev" in loc for loc in result.locations)

        # Should detect directions
        assert len(result.directions) >= 2
        assert any("Eastern Front" in dir for dir in result.directions)
        assert any("Donbas" in dir for dir in result.directions)

        # All entities should be in all_entities list
        total_entities = len(result.military_units) + len(result.locations) + len(result.directions)
        assert len(result.all_entities) == total_entities
