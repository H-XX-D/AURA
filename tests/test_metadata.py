#!/usr/bin/env python3
"""
Comprehensive tests for metadata.py
Tests metadata extraction, classification, security screening, and routing
"""
import pytest
from aura_compression.metadata import (
    MetadataKind,
    MetadataEntry,
    ExtractedMetadata,
    MetadataExtractor,
    FastPathClassifier,
    SecurityScreener,
    MetadataRouter,
)


class TestMetadataKind:
    """Test MetadataKind enum"""

    def test_enum_values(self):
        """Test enum values match expected"""
        assert MetadataKind.TEMPLATE.value == 0x01
        assert MetadataKind.LZ77.value == 0x02
        assert MetadataKind.SEMANTIC.value == 0x03
        assert MetadataKind.LITERAL.value == 0x04
        assert MetadataKind.FALLBACK.value == 0x05

    def test_enum_names(self):
        """Test enum names"""
        assert MetadataKind.TEMPLATE.name == "TEMPLATE"
        assert MetadataKind.LZ77.name == "LZ77"
        assert MetadataKind.SEMANTIC.name == "SEMANTIC"
        assert MetadataKind.LITERAL.name == "LITERAL"
        assert MetadataKind.FALLBACK.name == "FALLBACK"


class TestMetadataEntry:
    """Test MetadataEntry dataclass"""

    def test_init(self):
        """Test MetadataEntry initialization"""
        entry = MetadataEntry(
            kind=MetadataKind.TEMPLATE,
            token_index=123,
            value=456,
            flags=7
        )

        assert entry.kind == MetadataKind.TEMPLATE
        assert entry.token_index == 123
        assert entry.value == 456
        assert entry.flags == 7

    def test_from_bytes_valid(self):
        """Test parsing valid 6-byte metadata entry"""
        data = bytes([0x01, 0x00, 0x7B, 0x01, 0xC8, 0x07])  # TEMPLATE, token_index=123, value=456, flags=7

        entry = MetadataEntry.from_bytes(data)

        assert entry.kind == MetadataKind.TEMPLATE
        assert entry.token_index == 123
        assert entry.value == 456
        assert entry.flags == 7

    def test_from_bytes_unknown_kind(self):
        """Test parsing with unknown kind defaults to LITERAL"""
        data = bytes([0xFF, 0x00, 0x01, 0x00, 0x02, 0x03])  # Unknown kind, token_index=1, value=2, flags=3

        entry = MetadataEntry.from_bytes(data)

        assert entry.kind == MetadataKind.LITERAL
        assert entry.token_index == 1
        assert entry.value == 2
        assert entry.flags == 3

    def test_from_bytes_wrong_length(self):
        """Test parsing with wrong length raises ValueError"""
        data = bytes([0x01, 0x00, 0x01])  # Only 3 bytes

        with pytest.raises(ValueError, match="Metadata entry must be 6 bytes"):
            MetadataEntry.from_bytes(data)

    def test_from_bytes_all_kinds(self):
        """Test parsing all known metadata kinds"""
        test_cases = [
            (0x01, MetadataKind.TEMPLATE),
            (0x02, MetadataKind.LZ77),
            (0x03, MetadataKind.SEMANTIC),
            (0x04, MetadataKind.LITERAL),
            (0x05, MetadataKind.FALLBACK),
        ]

        for kind_byte, expected_kind in test_cases:
            data = bytes([kind_byte, 0x00, 0x01, 0x00, 0x02, 0x03])
            entry = MetadataEntry.from_bytes(data)
            assert entry.kind == expected_kind


class TestExtractedMetadata:
    """Test ExtractedMetadata dataclass"""

    def test_init_minimal(self):
        """Test ExtractedMetadata with minimal initialization"""
        metadata = ExtractedMetadata(compression_method="brio")

        assert metadata.compression_method == "brio"
        assert metadata.original_size is None
        assert metadata.compressed_size is None
        assert metadata.fast_path_candidate is False

    def test_init_full(self):
        """Test ExtractedMetadata with full initialization"""
        metadata = ExtractedMetadata(
            compression_method="brio",
            original_size=1000,
            compressed_size=500,
            plain_token_length=100,
            rans_payload_length=400,
            metadata_entry_count=10,
            template_ids=[1, 2, 3],
            has_lz77_matches=True,
            has_literals=False,
            has_semantic_tokens=True,
            fast_path_candidate=True
        )

        assert metadata.compression_method == "brio"
        assert metadata.original_size == 1000
        assert metadata.compressed_size == 500
        assert metadata.plain_token_length == 100
        assert metadata.rans_payload_length == 400
        assert metadata.metadata_entry_count == 10
        assert metadata.template_ids == [1, 2, 3]
        assert metadata.has_lz77_matches is True
        assert metadata.has_literals is False
        assert metadata.has_semantic_tokens is True
        assert metadata.fast_path_candidate is True

    def test_to_dict(self):
        """Test conversion to dictionary"""
        metadata = ExtractedMetadata(
            compression_method="brio",
            original_size=1000,
            compressed_size=500,
            template_ids=[1, 2],
            has_lz77_matches=True,
            fast_path_candidate=True
        )

        result = metadata.to_dict()

        expected = {
            'compression_method': 'brio',
            'original_size': 1000,
            'compressed_size': 500,
            'plain_token_length': None,
            'rans_payload_length': None,
            'metadata_entry_count': None,
            'template_ids': [1, 2],
            'has_lz77_matches': True,
            'has_literals': False,
            'has_semantic_tokens': False,
            'fast_path_candidate': True,
        }

        assert result == expected


class TestMetadataExtractor:
    """Test MetadataExtractor functionality"""

    def test_extract_empty_data(self):
        """Test extraction with empty data raises ValueError"""
        with pytest.raises(ValueError, match="Empty compressed data"):
            MetadataExtractor.extract(b"")

    def test_extract_unknown_method(self):
        """Test extraction with unknown compression method"""
        data = bytes([0x99, 0x01, 0x02])  # Unknown method byte

        with pytest.raises(ValueError, match="Unknown compression method"):
            MetadataExtractor.extract(data)

    def test_extract_binary_semantic_minimal(self):
        """Test binary semantic extraction with minimal data"""
        data = bytes([0x00, 0x01, 0x02])  # BINARY_SEMANTIC method, template_id=1, slot_count=2

        metadata = MetadataExtractor.extract(data)

        assert metadata.compression_method == "binary_semantic"
        assert metadata.compressed_size == 2
        assert metadata.template_ids == [1]
        assert metadata.fast_path_candidate is True

    def test_extract_binary_semantic_full(self):
        """Test binary semantic extraction with full data"""
        data = bytes([0x00, 0x0A, 0x03])  # BINARY_SEMANTIC, template_id=10, slot_count=3

        metadata = MetadataExtractor.extract(data)

        assert metadata.compression_method == "binary_semantic"
        assert metadata.compressed_size == 2
        assert metadata.template_ids == [10]
        assert metadata.fast_path_candidate is True

    def test_extract_brio_minimal(self):
        """Test BRIO extraction with minimal data"""
        data = bytes([0x01, 0x01, 0x02])  # BRIO method

        metadata = MetadataExtractor.extract(data)

        assert metadata.compression_method == "brio"
        assert metadata.compressed_size == 2
        assert metadata.fast_path_candidate is False

    def test_extract_brio_invalid_magic(self):
        """Test BRIO extraction with invalid magic bytes"""
        data = bytes([0x01]) + b"INVALID" + b"\x00" * 10  # BRIO method, invalid magic

        metadata = MetadataExtractor.extract(data)

        assert metadata.compression_method == "brio"
        assert metadata.fast_path_candidate is False

    def test_extract_brio_full(self):
        """Test BRIO extraction with full valid data"""
        # Create valid BRIO data structure
        magic = b"AURA"
        version = b"\x01"
        plain_token_len = (100).to_bytes(4, 'big')
        rans_payload_len = (400).to_bytes(4, 'big')
        metadata_count = (3).to_bytes(2, 'big')
        freq_table = b"\x00\x01" * 256  # 512 bytes

        # Three metadata entries
        entry1 = bytes([0x01, 0x00, 0x01, 0x00, 0x0A, 0x00])  # TEMPLATE, token=1, value=10
        entry2 = bytes([0x03, 0x00, 0x02, 0x00, 0x14, 0x01])  # SEMANTIC, token=2, value=20, flags=1
        entry3 = bytes([0x02, 0x00, 0x03, 0x00, 0x1E, 0x00])  # LZ77, token=3, value=30

        data = bytes([0x01]) + magic + version + plain_token_len + rans_payload_len + metadata_count + freq_table + entry1 + entry2 + entry3

        metadata = MetadataExtractor.extract(data)

        assert metadata.compression_method == "brio"
        assert metadata.plain_token_length == 100
        assert metadata.rans_payload_length == 400
        assert metadata.metadata_entry_count == 3
        assert len(metadata.metadata_entries) == 3
        assert metadata.template_ids == [10]
        assert metadata.has_lz77_matches is True
        assert metadata.has_literals is False
        assert metadata.has_semantic_tokens is True
        assert metadata.fast_path_candidate is True

    def test_extract_auralite_minimal(self):
        """Test Auralite extraction with minimal data"""
        data = bytes([0x03, 0x01, 0x02])  # Legacy AuraLite method byte

        metadata = MetadataExtractor.extract(data)

        assert metadata.compression_method == "auralite"
        assert metadata.compressed_size == 2

    def test_extract_auralite_invalid_magic(self):
        """Test Auralite extraction with invalid magic"""
        data = bytes([0x03]) + b"INVALID" + b"\x00" * 5  # Legacy tag, invalid magic

        metadata = MetadataExtractor.extract(data)

        assert metadata.compression_method == "auralite"

    def test_extract_auralite_with_templates(self):
        """Test Auralite extraction with template tokens"""
        # AUL1 magic + version + unused + token_len + unused + tokens
        magic = b"AUL1"
        version = b"\x01"
        unused1 = b"\x00"  # 1 byte
        token_len = (16).to_bytes(4, 'big')  # 16 bytes of tokens
        unused2 = b"\x00"  # 1 byte
        tokens = bytes([
            0x00,  # template token
            0x05,  # template_id=5
            0x02,  # slot_count=2
            0x00, 0x03, 0xAA, 0xBB, 0xCC,  # slot 1: len=3, data=AAA BB CC
            0x00, 0x02, 0xDD, 0xEE,       # slot 2: len=2, data=DD EE
            0x03, 0x05,                    # literal run: len=5
            0x01, 0x02,                    # dictionary token
        ])

        data = bytes([0x03]) + magic + version + unused1 + token_len + unused2 + tokens

        metadata = MetadataExtractor.extract(data)

        assert metadata.compression_method == "auralite"
        assert metadata.template_ids == [5]
        assert metadata.has_literals is True
        assert metadata.has_semantic_tokens is True
        assert metadata.fast_path_candidate is True

    def test_extract_uncompressed(self):
        """Test uncompressed data extraction"""
        data = bytes([0xFF, 0x01, 0x02, 0x03, 0x04])  # UNCOMPRESSED method

        metadata = MetadataExtractor.extract(data)

        assert metadata.compression_method == "uncompressed"
        assert metadata.original_size == 4
        assert metadata.compressed_size == 4
        assert metadata.fast_path_candidate is False


class TestFastPathClassifier:
    """Test FastPathClassifier functionality"""

    def test_init_default(self):
        """Test classifier initialization with defaults"""
        classifier = FastPathClassifier()

        assert len(classifier.template_intents) > 0
        assert classifier.template_intents[0] == "limitation"
        assert classifier.template_intents[10] == "fact"

    def test_init_custom(self):
        """Test classifier initialization with custom intents"""
        custom_intents = {1: "custom", 2: "intent"}
        classifier = FastPathClassifier(custom_intents)

        assert classifier.template_intents == custom_intents

    def test_classify_with_template(self):
        """Test classification with template present"""
        classifier = FastPathClassifier({5: "test_intent"})

        # Binary semantic data with template_id=5
        data = bytes([0x00, 0x05, 0x01])

        result = classifier.classify(data)

        assert result == "test_intent"

    def test_classify_no_template(self):
        """Test classification without template returns None"""
        classifier = FastPathClassifier()

        # BRIO data without templates
        data = bytes([0x01, 0x01, 0x02])

        result = classifier.classify(data)

        assert result is None

    def test_classify_unknown_template(self):
        """Test classification with unknown template"""
        classifier = FastPathClassifier({})

        # Binary semantic data with template_id=99 (not in intents)
        data = bytes([0x00, 0x63, 0x01])  # 0x63 = 99

        result = classifier.classify(data)

        assert result == "unknown"

    def test_classify_invalid_data(self):
        """Test classification with invalid data returns None"""
        classifier = FastPathClassifier()

        data = b""  # Empty data

        result = classifier.classify(data)

        assert result is None


class TestSecurityScreener:
    """Test SecurityScreener functionality"""

    def test_init_default(self):
        """Test screener initialization with defaults"""
        screener = SecurityScreener()

        assert len(screener.safe_template_ids) > 0
        assert 0 in screener.safe_template_ids
        assert 120 in screener.safe_template_ids

    def test_init_custom(self):
        """Test screener initialization with custom whitelist"""
        custom_safe = [1, 2, 3]
        screener = SecurityScreener(custom_safe)

        assert screener.safe_template_ids == set(custom_safe)

    def test_is_safe_fast_path_safe_template(self):
        """Test safety check with safe template"""
        screener = SecurityScreener([5])

        # Binary semantic data with template_id=5
        data = bytes([0x00, 0x05, 0x01])

        result = screener.is_safe_fast_path(data)

        assert result is True

    def test_is_safe_fast_path_unsafe_template(self):
        """Test safety check with unsafe template"""
        screener = SecurityScreener([1, 2, 3])  # 5 not in whitelist

        # Binary semantic data with template_id=5
        data = bytes([0x00, 0x05, 0x01])

        result = screener.is_safe_fast_path(data)

        assert result is False

    def test_is_safe_fast_path_multiple_templates_safe(self):
        """Test safety check with multiple safe templates"""
        screener = SecurityScreener([1, 2, 5])

        # Aura-Lite data with template_id=5
        data = bytes([0x03]) + b"AUL1\x01\x00\x00\x00\x05\x00\x00\x00\x05" + bytes([0x00, 0x05, 0x01])

        result = screener.is_safe_fast_path(data)

        assert result is True

    def test_is_safe_fast_path_multiple_templates_unsafe(self):
        """Test safety check with mixed safe/unsafe templates"""
        screener = SecurityScreener([1, 2])  # 5 not safe

        # Aura-Lite data with template_id=5
        data = bytes([0x03]) + b"AUL1\x01\x00\x00\x00\x05\x00\x00\x00\x05" + bytes([0x00, 0x05, 0x01])

        result = screener.is_safe_fast_path(data)

        assert result is False

    def test_is_safe_fast_path_no_templates(self):
        """Test safety check without templates returns False"""
        screener = SecurityScreener([1, 2, 3])

        # BRIO data without templates
        data = bytes([0x01, 0x01, 0x02])

        result = screener.is_safe_fast_path(data)

        assert result is False

    def test_is_safe_fast_path_invalid_data(self):
        """Test safety check with invalid data returns False"""
        screener = SecurityScreener()

        data = b""  # Empty data

        result = screener.is_safe_fast_path(data)

        assert result is False


class TestMetadataRouter:
    """Test MetadataRouter functionality"""

    def test_init_default(self):
        """Test router initialization with defaults"""
        router = MetadataRouter()

        assert router.template_routes == {}

    def test_init_custom(self):
        """Test router initialization with custom routes"""
        custom_routes = {1: "handler1", 2: "handler2"}
        router = MetadataRouter(custom_routes)

        assert router.template_routes == custom_routes

    def test_route_with_template(self):
        """Test routing with template present"""
        router = MetadataRouter({5: "test_handler"})

        # Binary semantic data with template_id=5
        data = bytes([0x00, 0x05, 0x01])

        result = router.route(data)

        assert result == "test_handler"

    def test_route_no_template(self):
        """Test routing without template returns None"""
        router = MetadataRouter({1: "handler1"})

        # BRIO data without templates
        data = bytes([0x01, 0x01, 0x02])

        result = router.route(data)

        assert result is None

    def test_route_unknown_template(self):
        """Test routing with unknown template returns None"""
        router = MetadataRouter({1: "handler1"})

        # Binary semantic data with template_id=99 (not routed)
        data = bytes([0x00, 0x63, 0x01])  # 0x63 = 99

        result = router.route(data)

        assert result is None

    def test_route_invalid_data(self):
        """Test routing with invalid data returns None"""
        router = MetadataRouter()

        data = b""  # Empty data

        result = router.route(data)

        assert result is None


class TestIntegration:
    """Integration tests for metadata pipeline"""

    def test_full_pipeline_binary_semantic(self):
        """Test full pipeline with binary semantic data"""
        # Create binary semantic data
        data = bytes([0x00, 0x0A, 0x02])  # template_id=10, slot_count=2

        # Extract metadata
        metadata = MetadataExtractor.extract(data)
        assert metadata.template_ids == [10]

        # Classify intent
        classifier = FastPathClassifier({10: "fact"})
        intent = classifier.classify(data)
        assert intent == "fact"

        # Check security
        screener = SecurityScreener([10])
        is_safe = screener.is_safe_fast_path(data)
        assert is_safe is True

        # Route message
        router = MetadataRouter({10: "fact_handler"})
        route = router.route(data)
        assert route == "fact_handler"

    def test_full_pipeline_brio_with_templates(self):
        """Test full pipeline with BRIO data containing templates"""
        # Create BRIO data with template metadata
        magic = b"AURA\x01"
        plain_token_len = (50).to_bytes(4, 'big')
        rans_payload_len = (200).to_bytes(4, 'big')
        metadata_count = (1).to_bytes(2, 'big')
        freq_table = b"\x00\x01" * 256
        entry = bytes([0x01, 0x00, 0x05, 0x00, 0x14, 0x00])  # TEMPLATE, value=20

        data = bytes([0x01]) + magic + plain_token_len + rans_payload_len + metadata_count + freq_table + entry

        # Extract metadata
        metadata = MetadataExtractor.extract(data)
        assert metadata.template_ids == [20]
        assert metadata.fast_path_candidate is True

        # Classify intent
        classifier = FastPathClassifier({20: "definition"})
        intent = classifier.classify(data)
        assert intent == "definition"

        # Check security
        screener = SecurityScreener([20])
        is_safe = screener.is_safe_fast_path(data)
        assert is_safe is True

        # Route message
        router = MetadataRouter({20: "definition_handler"})
        route = router.route(data)
        assert route == "definition_handler"

    def test_pipeline_no_fast_path(self):
        """Test pipeline when fast path is not available"""
        # BRIO data without templates
        data = bytes([0x01, 0x01, 0x02, 0x03])

        # Extract metadata
        metadata = MetadataExtractor.extract(data)
        assert metadata.fast_path_candidate is False

        # Classification should return None
        classifier = FastPathClassifier()
        intent = classifier.classify(data)
        assert intent is None

        # Security check should return False
        screener = SecurityScreener()
        is_safe = screener.is_safe_fast_path(data)
        assert is_safe is False

        # Routing should return None
        router = MetadataRouter()
        route = router.route(data)
        assert route is None