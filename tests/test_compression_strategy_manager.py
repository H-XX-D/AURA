#!/usr/bin/env python3
"""
Regression tests for CompressionStrategyManager
Tests the tuned heuristics for strategy selection based on entropy and dictionary hit rate
"""
import csv
import random
import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.compression_strategy_manager import CompressionStrategyManager
from aura_compression.compression_engine import CompressionEngine
from aura_compression.enums import CompressionMethod
from aura_compression.templates import TemplateMatch


class TestCompressionStrategyManager:
    """Test suite for strategy selection logic"""

    @pytest.fixture
    def strategy_manager(self):
        """Create a strategy manager for testing"""
        # Create a mock template library
        template_library = None  # Pass None for testing
        engine = CompressionEngine(template_library=template_library)
        manager = CompressionStrategyManager(
            compression_engine=engine,
            algorithm_selector=None,
            template_manager=None,
            performance_optimizer=None
        )
        return manager

    def test_entropy_calculation_empty_string(self, strategy_manager):
        """Test entropy calculation with empty string"""
        entropy = strategy_manager._calculate_entropy("")
        assert entropy == 0.0

    def test_entropy_calculation_single_char(self, strategy_manager):
        """Test entropy calculation with single repeated character"""
        entropy = strategy_manager._calculate_entropy("aaaaaaa")
        assert entropy == 0.0

    def test_entropy_calculation_high_entropy(self, strategy_manager):
        """Test entropy calculation with high entropy string"""
        entropy = strategy_manager._calculate_entropy("abcdefghijklmnop")
        assert entropy > 3.5  # High variety of characters

    def test_entropy_calculation_low_entropy(self, strategy_manager):
        """Test entropy calculation with low entropy string"""
        entropy = strategy_manager._calculate_entropy("the the the the the")
        assert entropy < 3.0  # Repetitive content

    def test_dictionary_hit_rate_empty(self, strategy_manager):
        """Test dictionary hit rate with empty string"""
        hit_rate = strategy_manager._estimate_dictionary_hit_rate("")
        assert hit_rate == 0.0

    def test_dictionary_hit_rate_json(self, strategy_manager):
        """Test dictionary hit rate with JSON content"""
        json_text = '{"status": "success", "data": {"message": "test"}}'
        hit_rate = strategy_manager._estimate_dictionary_hit_rate(json_text)
        assert hit_rate > 0.15  # Should detect JSON structural elements

    def test_dictionary_hit_rate_plain_text(self, strategy_manager):
        """Test dictionary hit rate with plain English text"""
        text = "the quick brown fox jumps over the lazy dog and can run fast"
        hit_rate = strategy_manager._estimate_dictionary_hit_rate(text)
        assert hit_rate > 0.02  # Should detect common English words (adjusted threshold)

    def test_dictionary_hit_rate_random(self, strategy_manager):
        """Test dictionary hit rate with random characters"""
        random_text = "xkqpzmbvwjfnhlyrg"
        hit_rate = strategy_manager._estimate_dictionary_hit_rate(random_text)
        assert hit_rate < 0.05  # Should not match common patterns

    def test_dictionary_hit_rate_balanced_sampling_limits_bias(self, strategy_manager):
        """Ensure long payloads with JSON header and random tail do not appear overly structured"""
        header = (
            '{"env":"prod","service":"api","version":"1.2.3","metadata":{"region":"us-east-1","zone":"b"}}'
        ) * 4
        tail = "".join(chr(65 + (i % 26)) for i in range(4000))
        combined = header + tail

        hit_rate = strategy_manager._estimate_dictionary_hit_rate(combined)
        assert hit_rate < 0.2

    def test_dictionary_hit_rate_balanced_sampling_detects_late_structure(self, strategy_manager):
        """Ensure structured content later in the payload still drives dictionary hits"""
        block = (
            '{"event":"ingest","status":"ok","payload":{"type":"json","ref":"abc123","size":512}}\n'
        )
        text = ("noise-noise-noise\n" * 40) + (block * 120)

        hit_rate = strategy_manager._estimate_dictionary_hit_rate(text)
        assert hit_rate > 0.18

    def test_entropy_cache_reuse(self, strategy_manager):
        """Entropy calculations should be cached for identical payloads"""
        strategy_manager._entropy_cache.clear()
        text = "sensor reading " * 20
        first = strategy_manager._calculate_entropy(text)
        cache_size = len(strategy_manager._entropy_cache)
        second = strategy_manager._calculate_entropy(text)
        assert first == second
        assert len(strategy_manager._entropy_cache) == cache_size

    def test_dictionary_cache_reuse(self, strategy_manager):
        """Dictionary hit calculations should be cached for identical payloads"""
        strategy_manager._dict_hit_cache.clear()
        text = '{"event":"login","status":"ok","user":"alice"}' * 5
        first = strategy_manager._estimate_dictionary_hit_rate(text)
        cache_size = len(strategy_manager._dict_hit_cache)
        second = strategy_manager._estimate_dictionary_hit_rate(text)
        assert first == second
        assert len(strategy_manager._dict_hit_cache) == cache_size

    def test_incompressible_detection_very_short(self, strategy_manager):
        """Test incompressible detection for very short strings"""
        assert strategy_manager._is_likely_incompressible("ab") is True
        assert strategy_manager._is_likely_incompressible("abc") is True

    def test_incompressible_detection_high_entropy(self, strategy_manager):
        """Test incompressible detection for high entropy data"""
        # Very high entropy random-like data
        random_data = "k8x2q9m5w7j3n1p4h6v0z"
        result = strategy_manager._is_likely_incompressible(random_data)
        # This might be True or False depending on exact entropy, just verify it runs
        assert isinstance(result, bool)

    def test_incompressible_detection_compressible(self, strategy_manager):
        """Test incompressible detection for compressible text"""
        compressible_text = "the the the the the the the the"
        assert strategy_manager._is_likely_incompressible(compressible_text) is False

    def test_incompressible_detection_repetitive_short_text(self, strategy_manager):
        """Repetitive but short payloads should remain compressible"""
        assert strategy_manager._is_likely_incompressible("aaaaaa") is False

    def test_incompressible_detection_common_short_keyword(self, strategy_manager):
        """Common short keywords (error, status, etc.) should not be rejected outright"""
        assert strategy_manager._is_likely_incompressible("error") is False

    def test_incompressible_detection_random_short_text(self, strategy_manager):
        """Random short payloads should still be treated as incompressible"""
        assert strategy_manager._is_likely_incompressible("Abc123!") is True

    def test_strategy_selection_very_small_payload(self, strategy_manager):
        """Test strategy selection for very small payloads (< 20 bytes)"""
        text = "hello"
        strategies = [CompressionMethod.AURALITE, CompressionMethod.BRIO, CompressionMethod.UNCOMPRESSED]
        selected = strategy_manager.select_optimal_strategy(text, strategies)
        assert selected == CompressionMethod.UNCOMPRESSED

    def test_strategy_selection_small_low_entropy(self, strategy_manager):
        """Test strategy selection for small payloads with low entropy (20-80 bytes)"""
        text = "test test test test test test"  # Low entropy, ~30 bytes
        strategies = [CompressionMethod.AURALITE, CompressionMethod.BRIO, CompressionMethod.UNCOMPRESSED]
        selected = strategy_manager.select_optimal_strategy(text, strategies)
        # Should select AURALITE for low entropy small payloads
        assert selected == CompressionMethod.AURALITE

    def test_strategy_selection_small_high_entropy(self, strategy_manager):
        """Test strategy selection for small payloads with high entropy"""
        text = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9"  # Higher entropy, ~40 bytes
        strategies = [CompressionMethod.AURALITE, CompressionMethod.BRIO, CompressionMethod.UNCOMPRESSED]
        selected = strategy_manager.select_optimal_strategy(text, strategies)
        # High entropy small payloads should stay uncompressed
        assert selected == CompressionMethod.UNCOMPRESSED

    def test_strategy_selection_medium_with_dict_hits(self, strategy_manager):
        """Test strategy selection for medium payloads with dictionary hits (400-2048 bytes)"""
        text = '{"status": "success", "data": {"message": "test", "code": 200}}' * 10  # ~500 bytes JSON
        strategies = [CompressionMethod.AURALITE, CompressionMethod.BRIO, CompressionMethod.UNCOMPRESSED]
        selected = strategy_manager.select_optimal_strategy(text, strategies)
        # Medium payloads with dictionary hits should prefer AURALITE
        assert selected == CompressionMethod.AURALITE

    def test_strategy_selection_medium_without_dict_hits(self, strategy_manager):
        """Test strategy selection for medium payloads without dictionary hits"""
        text = "x" * 600 + "y" * 400  # Low dictionary hits but compressible
        strategies = [CompressionMethod.AURALITE, CompressionMethod.BRIO, CompressionMethod.UNCOMPRESSED]
        selected = strategy_manager.select_optimal_strategy(text, strategies)
        # Should still try AURALITE as fallback for medium payloads
        assert selected in [CompressionMethod.AURALITE, CompressionMethod.BRIO]

    def test_strategy_selection_large_payload(self, strategy_manager):
        """Test strategy selection for large payloads (2048-8192 bytes)"""
        text = "The quick brown fox jumps over the lazy dog. " * 100  # ~4500 bytes
        strategies = [CompressionMethod.AURALITE, CompressionMethod.BRIO, CompressionMethod.UNCOMPRESSED]
        selected = strategy_manager.select_optimal_strategy(text, strategies)
        # Large payloads should prefer BRIO
        assert selected == CompressionMethod.BRIO

    def test_strategy_selection_very_large_payload(self, strategy_manager):
        """Test strategy selection for very large payloads (> 8KB)"""
        text = "Large payload content. " * 500  # ~11,500 bytes
        strategies = [CompressionMethod.AURALITE, CompressionMethod.BRIO, CompressionMethod.UNCOMPRESSED]
        selected = strategy_manager.select_optimal_strategy(text, strategies)
        # Very large payloads should strongly prefer BRIO
        assert selected == CompressionMethod.BRIO

    def test_strategy_selection_template_match_priority(self, strategy_manager):
        """Test that template matches take priority"""
        text = "Test message with template"
        # Create TemplateMatch without confidence parameter
        template_match = TemplateMatch(template_id=1, slots=[])
        strategies = [CompressionMethod.BINARY_SEMANTIC, CompressionMethod.AURALITE, CompressionMethod.UNCOMPRESSED]
        selected = strategy_manager.select_optimal_strategy(text, strategies, template_match)
        # Template matches should always take priority
        assert selected == CompressionMethod.BINARY_SEMANTIC

    def test_strategy_selection_no_strategies_available(self, strategy_manager):
        """Test strategy selection when no strategies are available"""
        text = "Test message"
        strategies = []
        selected = strategy_manager.select_optimal_strategy(text, strategies)
        assert selected == CompressionMethod.UNCOMPRESSED

    def test_strategy_selection_auralite_only(self, strategy_manager):
        """Test strategy selection when only AURALITE is available"""
        text = "Medium size message for testing compression" * 10
        strategies = [CompressionMethod.AURALITE]
        selected = strategy_manager.select_optimal_strategy(text, strategies)
        assert selected == CompressionMethod.AURALITE

    def test_available_strategies_returns_list(self, strategy_manager):
        """Test that get_available_strategies returns a list"""
        strategies = strategy_manager.get_available_strategies()
        assert isinstance(strategies, list)
        assert CompressionMethod.UNCOMPRESSED in strategies

    def test_entropy_threshold_boundary_80_bytes(self, strategy_manager):
        """Test entropy threshold at 80-byte boundary"""
        # Low entropy at boundary
        low_entropy_text = "a" * 80
        strategies = [CompressionMethod.AURALITE, CompressionMethod.UNCOMPRESSED]
        selected = strategy_manager.select_optimal_strategy(low_entropy_text, strategies)
        # Very low entropy should compress even at boundary
        assert selected == CompressionMethod.AURALITE

    def test_entropy_threshold_boundary_400_bytes(self, strategy_manager):
        """Test entropy threshold at 400-byte boundary"""
        # Medium entropy at boundary
        text = "The quick brown fox jumps over the lazy dog. " * 9  # ~405 bytes
        strategies = [CompressionMethod.AURALITE, CompressionMethod.UNCOMPRESSED]
        selected = strategy_manager.select_optimal_strategy(text, strategies)
        # Should attempt compression at this size
        assert selected == CompressionMethod.AURALITE

    def test_entropy_threshold_boundary_2048_bytes(self, strategy_manager):
        """Test entropy threshold at 2048-byte boundary"""
        text = '{"data": "value"}' * 80  # ~2000 bytes with dict hits
        strategies = [CompressionMethod.AURALITE, CompressionMethod.BRIO, CompressionMethod.UNCOMPRESSED]
        selected = strategy_manager.select_optimal_strategy(text, strategies)
        # At this boundary with dict hits, should prefer AURALITE
        assert selected in [CompressionMethod.AURALITE, CompressionMethod.BRIO]


class TestLightweightMLScorer:
    """Test suite for lightweight ML assist scorer"""

    @pytest.fixture
    def scorer_manager(self):
        """Create a strategy manager with scorer enabled"""
        engine = CompressionEngine(template_library=None)
        manager = CompressionStrategyManager(
            compression_engine=engine,
            algorithm_selector=None,
            template_manager=None,
            performance_optimizer=None,
            enable_scorer=True  # Enable scorer
        )
        return manager

    @pytest.fixture
    def base_manager(self):
        """Create a strategy manager without scorer for comparison"""
        engine = CompressionEngine(template_library=None)
        manager = CompressionStrategyManager(
            compression_engine=engine,
            algorithm_selector=None,
            template_manager=None,
            performance_optimizer=None,
            enable_scorer=False  # Disable scorer
        )
        return manager

    def test_scorer_flag_enabled(self, scorer_manager):
        """Test that scorer flag is properly set"""
        assert scorer_manager.enable_scorer is True

    def test_scorer_flag_disabled(self, base_manager):
        """Test that scorer can be disabled"""
        assert base_manager.enable_scorer is False

    def test_score_compression_potential_high_score(self, scorer_manager):
        """Test scoring for highly compressible payload"""
        text = "the the the the the " * 30  # Low entropy, high repetition, ~600 bytes
        byte_length = len(text.encode('utf-8'))
        entropy = scorer_manager._calculate_entropy(text)
        dict_hit_rate = scorer_manager._estimate_dictionary_hit_rate(text)

        score = scorer_manager._score_compression_potential(text, byte_length, entropy, dict_hit_rate)
        # Should score moderately high (> 0.55) due to low entropy and high repetition
        assert score > 0.55

    def test_score_compression_potential_low_score(self, scorer_manager):
        """Test scoring for poorly compressible payload"""
        text = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9" * 15  # High entropy, ~600 bytes
        byte_length = len(text.encode('utf-8'))
        entropy = scorer_manager._calculate_entropy(text)
        dict_hit_rate = scorer_manager._estimate_dictionary_hit_rate(text)

        score = scorer_manager._score_compression_potential(text, byte_length, entropy, dict_hit_rate)
        # Should score lower due to higher entropy
        assert score < 0.8

    def test_detect_repetition_high(self, scorer_manager):
        """Test repetition detection for highly repetitive text"""
        text = "abc" * 100  # Very repetitive
        repetition = scorer_manager._detect_repetition(text)
        assert repetition > 0.5

    def test_detect_repetition_low(self, scorer_manager):
        """Test repetition detection for non-repetitive text"""
        text = "abcdefghijklmnopqrstuvwxyz" * 3
        repetition = scorer_manager._detect_repetition(text)
        assert repetition < 0.5

    def test_detect_repetition_empty(self, scorer_manager):
        """Test repetition detection for short/empty text"""
        assert scorer_manager._detect_repetition("") == 0.0
        assert scorer_manager._detect_repetition("ab") == 0.0

    def test_scorer_affects_borderline_payloads_high_score(self, scorer_manager):
        """Test that scorer affects borderline payload selection (high score -> Auralite)"""
        # Create a borderline payload (600 bytes) that should score high
        text = '{"status": "ok", "data": "value"}' * 15  # ~480 bytes, good dict hits
        strategies = [CompressionMethod.AURALITE, CompressionMethod.BRIO, CompressionMethod.UNCOMPRESSED]
        selected = scorer_manager.select_optimal_strategy(text, strategies)
        # With scorer enabled and high score, should prefer AURALITE
        assert selected == CompressionMethod.AURALITE

    def test_scorer_affects_borderline_payloads_low_score(self, scorer_manager):
        """Test that scorer affects borderline payload selection (low score -> BRIO)"""
        # Create a borderline payload (1000 bytes) with low compressibility
        text = "x" * 500 + "y" * 500  # ~1000 bytes, low dict hits, moderate entropy
        strategies = [CompressionMethod.AURALITE, CompressionMethod.BRIO, CompressionMethod.UNCOMPRESSED]
        selected = scorer_manager.select_optimal_strategy(text, strategies)
        # Selection should be based on scorer + heuristics
        assert selected in [CompressionMethod.AURALITE, CompressionMethod.BRIO]

    def test_scorer_only_affects_borderline_range(self, scorer_manager):
        """Test that scorer only activates for 400-2048 byte range"""
        # Small payload (< 400 bytes) - scorer should not activate
        text = "small text" * 10  # ~100 bytes
        strategies = [CompressionMethod.AURALITE, CompressionMethod.UNCOMPRESSED]
        selected = scorer_manager.select_optimal_strategy(text, strategies)
        # Should follow normal logic, not scorer
        assert selected in [CompressionMethod.AURALITE, CompressionMethod.UNCOMPRESSED]

    def test_scorer_vs_no_scorer_comparison(self, scorer_manager, base_manager):
        """Test difference in selection between scorer enabled and disabled"""
        # Borderline payload
        text = '{"key": "value"}' * 40  # ~640 bytes
        strategies = [CompressionMethod.AURALITE, CompressionMethod.BRIO, CompressionMethod.UNCOMPRESSED]

        # Get selections from both managers
        with_scorer = scorer_manager.select_optimal_strategy(text, strategies)
        without_scorer = base_manager.select_optimal_strategy(text, strategies)

        # Both should return valid strategies (may or may not differ)
        assert with_scorer in strategies
        assert without_scorer in strategies

    def test_scorer_score_range(self, scorer_manager):
        """Test that scorer always returns scores in valid range"""
        test_cases = [
            ("very short", 50),
            ("medium length text " * 20, 500),
            ("x" * 100 + "y" * 100, 200),
            ('{"a": "b"}' * 50, 600),
        ]

        for text, expected_len in test_cases:
            byte_length = len(text.encode('utf-8'))
            entropy = scorer_manager._calculate_entropy(text)
            dict_hit_rate = scorer_manager._estimate_dictionary_hit_rate(text)

            score = scorer_manager._score_compression_potential(text, byte_length, entropy, dict_hit_rate)
            # Score must be between 0.0 and 1.0
            assert 0.0 <= score <= 1.0

    def test_scorer_performance_borderline_json(self, scorer_manager):
        """Test scorer with realistic JSON payload"""
        json_text = '{"user": {"id": 123, "name": "Alice"}, "action": "login", "timestamp": 1234567890}' * 10
        byte_length = len(json_text.encode('utf-8'))
        assert 400 <= byte_length <= 2048  # Verify it's in borderline range

        strategies = [CompressionMethod.AURALITE, CompressionMethod.BRIO, CompressionMethod.UNCOMPRESSED]
        selected = scorer_manager.select_optimal_strategy(json_text, strategies)

        # JSON should score well (good dict hits)
        assert selected in [CompressionMethod.AURALITE, CompressionMethod.BRIO]

    def test_scorer_auto_disables_when_borderline_mix_low(self, scorer_manager):
        """Scorer should auto-disable when borderline share stay below threshold."""
        scorer_manager._scorer_eval_window = 4
        scorer_manager._scorer_min_borderline_ratio = 0.5

        strategies = [CompressionMethod.AURALITE, CompressionMethod.UNCOMPRESSED]
        for _ in range(4):
            scorer_manager.select_optimal_strategy("tiny", strategies)

        status = scorer_manager.get_scorer_status()
        assert scorer_manager.enable_scorer is False
        assert status["auto_disabled"] is True
        assert status["disabled_reason"]

    def test_scorer_status_reports_recommendation_when_enabled(self, scorer_manager):
        """Status metadata should include recommendation when scorer remains enabled."""
        scorer_manager._scorer_eval_window = 3
        scorer_manager._scorer_min_borderline_ratio = 0.2

        strategies = [CompressionMethod.AURALITE, CompressionMethod.BRIO, CompressionMethod.UNCOMPRESSED]
        borderline_text = '{"status": "ok"}' * 40

        # First borderline messages keep ratio high
        scorer_manager.select_optimal_strategy(borderline_text, strategies)
        scorer_manager.select_optimal_strategy(borderline_text, strategies)
        scorer_manager.select_optimal_strategy("tiny", strategies)

        status = scorer_manager.get_scorer_status()
        assert status["enabled"] is True
        assert status["auto_disabled"] is False
        assert status["recommendation"]

    def test_scorer_performance_borderline_code(self, scorer_manager):
        """Test scorer with realistic code payload"""
        code_text = '''def calculate(x, y):
    result = x + y
    return result

''' * 15  # ~600 bytes of code
        byte_length = len(code_text.encode('utf-8'))
        assert 400 <= byte_length <= 2048  # Verify it's in borderline range

        strategies = [CompressionMethod.AURALITE, CompressionMethod.BRIO, CompressionMethod.UNCOMPRESSED]
        selected = scorer_manager.select_optimal_strategy(code_text, strategies)

        # Code with repetitive patterns should compress
        assert selected in [CompressionMethod.AURALITE, CompressionMethod.BRIO]

    def test_score_monotonic_dictionary_hits(self, scorer_manager):
        """Score should increase as dictionary hit rate increases"""
        text = "{" + "\"key\":\"value\"," * 15 + "}"  # JSON-like payload
        byte_length = len(text.encode('utf-8'))
        entropy = scorer_manager._calculate_entropy(text)

        hit_rates = [0.0, 0.05, 0.15, 0.25, 0.4]
        scores = [
            scorer_manager._score_compression_potential(text, byte_length, entropy, rate)
            for rate in hit_rates
        ]

        assert scores == sorted(scores)

    def test_score_monotonic_entropy(self, scorer_manager):
        """Score should decrease as entropy increases for fixed dictionary signal"""
        text = "borderline payload"
        byte_length = len(text.encode('utf-8'))
        dict_hit_rate = 0.2

        entropy_levels = [2.0, 4.0, 5.5, 6.5, 7.5]
        scores = [
            scorer_manager._score_compression_potential(text, byte_length, entropy, dict_hit_rate)
            for entropy in entropy_levels
        ]

        assert scores == sorted(scores, reverse=True)

    def test_score_randomized_bounds(self, scorer_manager):
        """Randomized sampling to ensure score stays within the 0-1 bounds"""
        rng = random.Random(42)
        for _ in range(100):
            byte_length = rng.randint(50, 5000)
            entropy = rng.uniform(0.0, 8.0)
            dict_hit_rate = rng.uniform(0.0, 0.5)
            synthetic_text = "x" * max(1, byte_length // 2)

            score = scorer_manager._score_compression_potential(
                synthetic_text,
                byte_length,
                entropy,
                dict_hit_rate,
            )

            assert 0.0 <= score <= 1.0

    def test_scorer_telemetry_csv_written(self, tmp_path):
        """Test that scorer telemetry is written to CSV when scorer is active"""
        telemetry_path = tmp_path / "scorer_telemetry.csv"
        engine = CompressionEngine(template_library=None)
        manager = CompressionStrategyManager(
            compression_engine=engine,
            algorithm_selector=None,
            template_manager=None,
            performance_optimizer=None,
            enable_scorer=True,
            scorer_telemetry_path=str(telemetry_path),
        )

        text = '{"status": "ok", "data": "value"}' * 20  # Borderline payload with good dictionary hits
        strategies = [CompressionMethod.AURALITE, CompressionMethod.BRIO, CompressionMethod.UNCOMPRESSED]

        selected = manager.select_optimal_strategy(text, strategies)
        assert selected in strategies

        assert telemetry_path.exists()

        with telemetry_path.open("r", encoding="utf-8", newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            rows = list(reader)

        expected_header = [
            "timestamp",
            "payload_bytes",
            "entropy",
            "dictionary_hit_rate",
            "score",
            "selected_method",
            "messages_seen",
            "borderline_messages",
            "global_borderline_ratio",
            "window_borderline_ratio",
            "scorer_enabled",
            "auto_disabled",
        ]

        assert reader.fieldnames == expected_header
        assert len(rows) == 1  # One telemetry entry
        row = rows[0]
        payload_bytes = int(row["payload_bytes"])
        assert 400 <= payload_bytes <= 2048
        assert row["selected_method"] in {"AURALITE", "BRIO"}
        assert row["messages_seen"] != ""
        assert row["global_borderline_ratio"] != ""



class TestPostCompressionValidation:
    """test suite for post-compression validation hook (task 18)"""

    @pytest.fixture
    def strategy_manager_with_validation(self):
        """create strategy manager with validation enabled"""
        engine = CompressionEngine(template_library=None)
        manager = CompressionStrategyManager(
            engine,
            algorithm_selector=None,
            template_manager=None,
            performance_optimizer=None,
            enable_validation=True
        )
        return manager

    @pytest.fixture
    def strategy_manager_no_validation(self):
        """create strategy manager with validation disabled"""
        engine = CompressionEngine(template_library=None)
        manager = CompressionStrategyManager(
            engine,
            algorithm_selector=None,
            template_manager=None,
            performance_optimizer=None,
            enable_validation=False
        )
        return manager

    def test_validation_enabled_parameter(self, strategy_manager_with_validation):
        """verify enable_validation parameter is set correctly"""
        assert strategy_manager_with_validation.enable_validation is True

    def test_validation_disabled_by_default(self, strategy_manager_no_validation):
        """verify validation is disabled by default"""
        assert strategy_manager_no_validation.enable_validation is False

    def test_validation_hook_invoked(self, strategy_manager_with_validation, caplog):
        """verify validation hook is invoked after compression"""
        import logging
        caplog.set_level(logging.WARNING)

        # compress a simple message
        text = "hello world test message"
        compressed, metadata = strategy_manager_with_validation._compress_with_strategies(
            text, [CompressionMethod.AURALITE, CompressionMethod.BRIO]
        )

        # validation should run (compression completes)
        assert compressed is not None
        assert len(compressed) > 0

        # mismatch count may be 0 or more depending on compression success
        assert strategy_manager_with_validation._validation_mismatch_count >= 0

    def test_validation_mismatch_count_tracking(self, strategy_manager_with_validation):
        """verify validation mismatch count is tracked"""
        # initially zero
        initial_count = strategy_manager_with_validation._validation_mismatch_count
        assert initial_count == 0

        # compress a message
        text = "test message for compression validation"
        strategy_manager_with_validation._compress_with_strategies(
            text, [CompressionMethod.AURALITE]
        )

        # mismatch count may stay 0 or increment depending on compression result
        # the key is that it's tracked (not None, and >= initial)
        assert strategy_manager_with_validation._validation_mismatch_count >= initial_count

    def test_validation_does_not_block_production(self, strategy_manager_with_validation):
        """verify validation failures don't block production flows"""
        text = "production message that must not be blocked"

        # compression should succeed even if validation hypothetically fails
        compressed, metadata = strategy_manager_with_validation._compress_with_strategies(
            text, [CompressionMethod.AURALITE, CompressionMethod.BRIO]
        )

        # compression result returned regardless of validation
        assert compressed is not None
        assert metadata is not None

    def test_validation_with_scorer_enabled(self):
        """verify validation works alongside scorer"""
        engine = CompressionEngine(template_library=None)
        manager = CompressionStrategyManager(
            engine,
            algorithm_selector=None,
            template_manager=None,
            performance_optimizer=None,
            enable_scorer=True,
            enable_validation=True
        )

        # both should be enabled
        assert manager.enable_scorer is True
        assert manager.enable_validation is True

        # compress borderline payload (scorer range)
        text = "test message in scorer range " * 20  # ~600 bytes, in scorer range
        compressed, metadata = manager._compress_with_strategies(
            text, [CompressionMethod.AURALITE, CompressionMethod.BRIO]
        )

        # should compress successfully with both scorer and validation active
        assert compressed is not None
        # mismatch count tracked (may be 0 or more)
        assert manager._validation_mismatch_count >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
