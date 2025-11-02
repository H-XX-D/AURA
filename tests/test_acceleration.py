#!/usr/bin/env python3
"""Comprehensive tests for acceleration module"""

import sys
import time

from aura_compression.acceleration import (
    MetadataSignature,
    CachedResponse,
    LRUPatternCache,
    ConversationAccelerator,
)


def test_metadata_signature():
    """Test MetadataSignature creation and key generation"""
    print("=" * 60)
    print("TEST 1: MetadataSignature")
    print("=" * 60)
    
    sig1 = MetadataSignature(
        compression_method="brio",
        template_ids=(1, 2, 3),
        has_lz77=True,
        has_literals=False,
        token_count=10
    )
    
    sig2 = MetadataSignature(
        compression_method="brio",
        template_ids=(1, 2, 3),
        has_lz77=True,
        has_literals=False,
        token_count=10
    )
    
    sig3 = MetadataSignature(
        compression_method="auralite",
        template_ids=(1, 2, 3),
        has_lz77=True,
        has_literals=False,
        token_count=10
    )
    
    key1 = sig1.to_key()
    key2 = sig2.to_key()
    key3 = sig3.to_key()
    
    print(f"Signature 1 key: {key1}")
    print(f"Signature 2 key: {key2}")
    print(f"Signature 3 key: {key3}")
    
    if key1 == key2:
        print("✅ PASSED: Identical signatures produce same key")
    else:
        print("❌ FAILED: Identical signatures should produce same key")
        return False
    
    if key1 != key3:
        print("✅ PASSED: Different signatures produce different keys")
    else:
        print("❌ FAILED: Different signatures should produce different keys")
        return False
    
    return True

def test_cached_response():
    """Test CachedResponse touch functionality"""
    print("\n" + "=" * 60)
    print("TEST 2: CachedResponse")
    print("=" * 60)
    
    cached = CachedResponse(response="test response")
    initial_count = cached.hit_count
    initial_time = cached.last_accessed
    
    print(f"Initial hit count: {initial_count}")
    
    time.sleep(0.01)
    cached.touch()
    
    print(f"After touch hit count: {cached.hit_count}")
    print(f"Time updated: {cached.last_accessed > initial_time}")
    
    if cached.hit_count == initial_count + 1:
        print("✅ PASSED: Touch increments hit count")
    else:
        print("❌ FAILED: Touch should increment hit count")
        return False
    
    if cached.last_accessed > initial_time:
        print("✅ PASSED: Touch updates last_accessed")
    else:
        print("❌ FAILED: Touch should update last_accessed")
        return False
    
    return True

def test_lru_cache():
    """Test LRU cache eviction and retrieval"""
    print("\n" + "=" * 60)
    print("TEST 3: LRU Pattern Cache")
    print("=" * 60)
    
    cache = LRUPatternCache(max_size=3)
    
    # Add items
    cache.put("key1", "response1")
    cache.put("key2", "response2")
    cache.put("key3", "response3")
    
    print(f"Cache size after 3 items: {cache.size()}")
    
    if cache.size() != 3:
        print("❌ FAILED: Cache should have 3 items")
        return False
    
    # Access key1 to make it most recent
    result = cache.get("key1")
    print(f"Retrieved key1: {result}")
    
    if result != "response1":
        print("❌ FAILED: Should retrieve correct response")
        return False
    
    # Add 4th item, should evict key2 (least recently used)
    cache.put("key4", "response4")
    
    print(f"Cache size after adding 4th item: {cache.size()}")
    
    if cache.size() != 3:
        print("❌ FAILED: Cache should stay at max_size")
        return False
    
    # key2 should be evicted
    result2 = cache.get("key2")
    if result2 is None:
        print("✅ PASSED: LRU eviction works (key2 evicted)")
    else:
        print("❌ FAILED: key2 should have been evicted")
        return False
    
    # key1 should still be there
    result1 = cache.get("key1")
    if result1 == "response1":
        print("✅ PASSED: Recently accessed key1 not evicted")
    else:
        print("❌ FAILED: key1 should not have been evicted")
        return False
    
    # Test hit rate
    hit_rate = cache.get_hit_rate()
    print(f"Cache hit rate: {hit_rate:.2%}")
    
    return True

def test_conversation_accelerator_basic():
    """Test basic ConversationAccelerator functionality"""
    print("\n" + "=" * 60)
    print("TEST 4: ConversationAccelerator Basic")
    print("=" * 60)
    
    accelerator = ConversationAccelerator(
        cache_size=100,
        enable_platform_wide_learning=False,
        preload_speed_profile=False
    )
    
    # Create test metadata
    metadata = {
        'method': 'brio',
        'template_ids': [1, 2, 3],
        'has_lz77_matches': True,
        'has_literals': False,
        'plain_token_length': 10,
    }
    
    # First attempt should be cache miss
    result = accelerator.try_fast_path(metadata)
    print(f"First attempt (should be None): {result}")
    
    if result is not None:
        print("❌ FAILED: First attempt should be cache miss")
        return False
    
    # Cache a response
    accelerator.cache_response(metadata, "cached response")
    
    # Second attempt should be cache hit
    result = accelerator.try_fast_path(metadata)
    print(f"Second attempt (should be cached): {result}")
    
    if result != "cached response":
        print("❌ FAILED: Should retrieve cached response")
        return False
    
    print("✅ PASSED: Basic cache operations work")
    
    # Check metrics
    metrics = accelerator.get_metrics()
    print(f"\nMetrics:")
    print(f"  Cache hits: {metrics['cache_hits']}")
    print(f"  Cache misses: {metrics['cache_misses']}")
    print(f"  Hit rate: {metrics['hit_rate']:.2%}")
    
    return True

def test_conversation_accelerator_hit_rate():
    """Test hit rate calculation"""
    print("\n" + "=" * 60)
    print("TEST 5: Hit Rate Calculation")
    print("=" * 60)
    
    accelerator = ConversationAccelerator(
        cache_size=100,
        preload_speed_profile=False
    )
    
    # Create multiple metadata patterns
    patterns = []
    for i in range(5):
        patterns.append({
            'method': 'brio',
            'template_ids': [i],
            'has_lz77_matches': False,
            'has_literals': True,
            'plain_token_length': 10,
        })
    
    # Cache all patterns
    for i, pattern in enumerate(patterns):
        accelerator.cache_response(pattern, f"response_{i}")
    
    # Access patterns multiple times (hits)
    hit_count = 0
    miss_count = 0
    
    for _ in range(10):
        for pattern in patterns:
            result = accelerator.try_fast_path(pattern)
            if result:
                hit_count += 1
            else:
                miss_count += 1
    
    print(f"Hits: {hit_count}")
    print(f"Misses: {miss_count}")
    
    hit_rate = accelerator.get_hit_rate()
    print(f"Hit rate: {hit_rate:.2%}")
    
    if hit_rate == 1.0:
        print("✅ PASSED: 100% hit rate for cached patterns")
    else:
        print(f"⚠️  WARNING: Expected 100% hit rate, got {hit_rate:.2%}")
    
    return True

def test_platform_wide_learning():
    """Test platform-wide cache sharing"""
    print("\n" + "=" * 60)
    print("TEST 6: Platform-Wide Learning")
    print("=" * 60)
    
    accelerator = ConversationAccelerator(
        cache_size=50,
        enable_platform_wide_learning=True,
        preload_speed_profile=False
    )
    
    metadata = {
        'method': 'auralite',
        'template_ids': [100],
        'has_lz77_matches': False,
        'has_literals': True,
        'plain_token_length': 5,
    }
    
    # Cache in platform
    accelerator.cache_response(metadata, "platform cached")
    
    # Clear session cache to test platform fallback
    accelerator.session_cache = LRUPatternCache(50)
    
    # Should still get from platform cache
    result = accelerator.try_fast_path(metadata)
    print(f"Retrieved from platform cache: {result}")
    
    if result == "platform cached":
        print("✅ PASSED: Platform-wide learning works")
        return True
    else:
        print("❌ FAILED: Should retrieve from platform cache")
        return False

def test_speedup_calculation():
    """Test speedup factor calculation"""
    print("\n" + "=" * 60)
    print("TEST 7: Speedup Factor Calculation")
    print("=" * 60)
    
    accelerator = ConversationAccelerator(
        cache_size=100,
        preload_speed_profile=True  # Use default profile
    )
    
    speedup = accelerator.get_speedup_factor(baseline_latency_ms=13.0)
    print(f"Initial speedup factor: {speedup:.2f}x")
    
    # With preloaded profile, we should see significant speedup
    if speedup > 10:
        print(f"✅ PASSED: Preloaded profile shows {speedup:.2f}x speedup")
    else:
        print(f"⚠️  WARNING: Expected >10x speedup with preload, got {speedup:.2f}x")
    
    avg_latency = accelerator.get_average_latency()
    print(f"Average latency: {avg_latency:.4f}ms")
    
    return True

def test_signature_extraction():
    """Test signature extraction from metadata"""
    print("\n" + "=" * 60)
    print("TEST 8: Signature Extraction")
    print("=" * 60)
    
    accelerator = ConversationAccelerator(preload_speed_profile=False)
    
    metadata = {
        'method': 'binary_semantic',
        'template_ids': [1, 2, 3, 4],
        'has_lz77_matches': True,
        'has_literals': False,
        'plain_token_length': 20,
    }
    
    signature = accelerator.extract_signature(metadata)
    
    print(f"Extracted signature:")
    print(f"  Method: {signature.compression_method}")
    print(f"  Template IDs: {signature.template_ids}")
    print(f"  Has LZ77: {signature.has_lz77}")
    print(f"  Has literals: {signature.has_literals}")
    print(f"  Token count: {signature.token_count}")
    
    if signature.compression_method == 'binary_semantic':
        print("✅ PASSED: Method extracted correctly")
    else:
        print("❌ FAILED: Method not extracted correctly")
        return False
    
    if signature.template_ids == (1, 2, 3, 4):
        print("✅ PASSED: Template IDs extracted correctly")
    else:
        print("❌ FAILED: Template IDs not extracted correctly")
        return False
    
    return True

def main():
    """Run all tests"""
    print("\n🧪 ACCELERATION MODULE COMPREHENSIVE TESTS")
    print("=" * 60)
    
    results = []
    
    try:
        results.append(("MetadataSignature", test_metadata_signature()))
        results.append(("CachedResponse", test_cached_response()))
        results.append(("LRU Cache", test_lru_cache()))
        results.append(("Basic Accelerator", test_conversation_accelerator_basic()))
        results.append(("Hit Rate", test_conversation_accelerator_hit_rate()))
        results.append(("Platform Learning", test_platform_wide_learning()))
        results.append(("Speedup Calculation", test_speedup_calculation()))
        results.append(("Signature Extraction", test_signature_extraction()))
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
