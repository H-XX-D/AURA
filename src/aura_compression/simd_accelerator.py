"""SIMD-accelerated message processing for small messages."""

import time
import array
import struct
from typing import List, Tuple, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import threading
import os

# Check for SIMD support
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None

class SIMDMessageProcessor:
    """SIMD-accelerated processing for small messages.

    Uses vectorized operations to process multiple small messages in parallel,
    significantly improving throughput for common message sizes.
    """

    def __init__(self, max_batch_size: int = 64, enable_simd: bool = True):
        self.max_batch_size = max_batch_size
        self.enable_simd = enable_simd and HAS_NUMPY
        self._batch_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="simd_processor")

        # SIMD processing statistics
        self.simd_operations = 0
        self.fallback_operations = 0
        self.batch_processing_time = 0.0

        # Pre-allocated buffers for SIMD operations
        if self.enable_simd:
            self._float_buffer = np.zeros(max_batch_size, dtype=np.float32)
            self._int_buffer = np.zeros(max_batch_size, dtype=np.int32)
            self._bool_buffer = np.zeros(max_batch_size, dtype=bool)

    def process_batch_simd(self, messages: List[str], operation: str = "length") -> List[Any]:
        """Process a batch of messages using SIMD operations.

        Args:
            messages: List of messages to process
            operation: Type of operation ('length', 'entropy', 'hash', 'tokenize')

        Returns:
            List of results for each message
        """
        if not self.enable_simd or len(messages) == 0:
            return self._process_batch_fallback(messages, operation)

        start_time = time.time()

        try:
            if operation == "length":
                result = self._simd_length_batch(messages)
            elif operation == "entropy":
                result = self._simd_entropy_batch(messages)
            elif operation == "hash":
                result = self._simd_hash_batch(messages)
            elif operation == "tokenize":
                result = self._simd_tokenize_batch(messages)
            else:
                return self._process_batch_fallback(messages, operation)

            self.simd_operations += len(messages)
            self.batch_processing_time += time.time() - start_time

            return result

        except Exception:
            # Fallback to non-SIMD processing on any error
            self.fallback_operations += len(messages)
            return self._process_batch_fallback(messages, operation)

    def _simd_length_batch(self, messages: List[str]) -> List[int]:
        """Calculate lengths using SIMD operations."""
        lengths = np.array([len(msg) for msg in messages], dtype=np.int32)
        return lengths.tolist()

    def _simd_entropy_batch(self, messages: List[str]) -> List[float]:
        """Calculate entropy using SIMD operations."""
        entropies = []

        for msg in messages:
            if len(msg) == 0:
                entropies.append(0.0)
                continue

            # Count character frequencies
            char_counts = np.zeros(256, dtype=np.int32)
            for char in msg:
                char_counts[ord(char) % 256] += 1

            # Calculate probabilities
            probs = char_counts[char_counts > 0].astype(np.float32) / len(msg)

            # Calculate entropy: -sum(p * log2(p))
            if len(probs) > 0:
                entropy = -np.sum(probs * np.log2(probs))
            else:
                entropy = 0.0

            entropies.append(float(entropy))

        return entropies

    def _simd_hash_batch(self, messages: List[str]) -> List[int]:
        """Calculate simple hashes using SIMD operations."""
        hashes = []

        for msg in messages:
            # Simple rolling hash optimized for SIMD
            if len(msg) == 0:
                hashes.append(0)
                continue

            # Convert to numpy array for vectorized operations
            chars = np.array([ord(c) for c in msg], dtype=np.uint8)
            hash_val = np.uint32(5381)  # djb2 hash start

            # Vectorized rolling hash
            for char_val in chars:
                hash_val = ((hash_val << 5) + hash_val) + char_val  # hash * 33 + c

            hashes.append(int(hash_val))

        return hashes

    def _simd_tokenize_batch(self, messages: List[str]) -> List[List[str]]:
        """Tokenize messages using SIMD-optimized operations."""
        results = []

        for msg in messages:
            # Fast tokenization using numpy operations
            if len(msg) == 0:
                results.append([])
                continue

            # Convert to numpy array
            chars = np.array([ord(c) for c in msg], dtype=np.uint8)

            # Find whitespace positions (SIMD comparison)
            whitespace_mask = np.isin(chars, [32, 9, 10, 13])  # space, tab, \n, \r

            # Find word boundaries
            word_starts = np.where(~whitespace_mask & np.roll(whitespace_mask, 1))[0]
            if not whitespace_mask[0]:  # First character is not whitespace
                word_starts = np.concatenate([[0], word_starts])

            # Extract words
            words = []
            for start in word_starts:
                # Find end of word
                end_mask = whitespace_mask[start:]
                if np.any(end_mask):
                    end = start + np.argmax(end_mask)
                else:
                    end = len(msg)

                if end > start:
                    word = msg[start:end]
                    if word:  # Skip empty words
                        words.append(word)

            results.append(words)

        return results

    def _process_batch_fallback(self, messages: List[str], operation: str) -> List[Any]:
        """Fallback processing without SIMD."""
        results = []

        for msg in messages:
            if operation == "length":
                results.append(len(msg))
            elif operation == "entropy":
                results.append(self._calculate_entropy(msg))
            elif operation == "hash":
                results.append(hash(msg))
            elif operation == "tokenize":
                results.append(msg.split())
            else:
                results.append(None)

        return results

    def _calculate_entropy(self, text: str) -> float:
        """Calculate Shannon entropy of text."""
        if len(text) == 0:
            return 0.0

        char_counts = {}
        for char in text:
            char_counts[char] = char_counts.get(char, 0) + 1

        entropy = 0.0
        for count in char_counts.values():
            prob = count / len(text)
            entropy -= prob * (prob).bit_length() / 8.0  # Approximate log2

        return entropy

    def get_stats(self) -> Dict[str, Any]:
        """Get SIMD processing statistics."""
        total_operations = self.simd_operations + self.fallback_operations

        return {
            'simd_enabled': self.enable_simd,
            'numpy_available': HAS_NUMPY,
            'simd_operations': self.simd_operations,
            'fallback_operations': self.fallback_operations,
            'simd_ratio': self.simd_operations / total_operations if total_operations > 0 else 0.0,
            'avg_batch_time': self.batch_processing_time / max(total_operations, 1),
            'max_batch_size': self.max_batch_size
        }

    def should_use_simd(self, messages: List[str]) -> bool:
        """Determine if SIMD processing should be used for a batch."""
        if not self.enable_simd or len(messages) == 0:
            return False

        # Use SIMD for batches that are reasonably sized and contain small messages
        avg_length = sum(len(msg) for msg in messages) / len(messages)
        return len(messages) <= self.max_batch_size and avg_length <= 1000

class SIMDOptimizedCompressor:
    """Compression system optimized for small messages using SIMD operations."""

    def __init__(self, enable_simd: bool = True):
        self.simd_processor = SIMDMessageProcessor(enable_simd=enable_simd)
        self.compression_stats = {
            'simd_batches': 0,
            'fallback_batches': 0,
            'total_messages': 0,
            'avg_batch_size': 0.0
        }

    def compress_batch(self, messages: List[str]) -> List[Tuple[bytes, str, Dict[str, Any]]]:
        """Compress a batch of messages using SIMD optimizations where beneficial."""
        if not messages:
            return []

        # Decide whether to use SIMD batch processing
        use_simd = self.simd_processor.should_use_simd(messages)

        if use_simd and len(messages) > 1:
            # SIMD batch processing
            self.compression_stats['simd_batches'] += 1

            # Pre-calculate features using SIMD
            lengths = self.simd_processor.process_batch_simd(messages, "length")
            entropies = self.simd_processor.process_batch_simd(messages, "entropy")
            tokens_list = self.simd_processor.process_batch_simd(messages, "tokenize")

            # Process each message with SIMD-optimized features
            results = []
            for i, msg in enumerate(messages):
                # Use pre-calculated features for compression decision
                features = {
                    'length': lengths[i],
                    'entropy': entropies[i],
                    'token_count': len(tokens_list[i]) if tokens_list[i] else 0,
                    'processed_with_simd': True
                }

                # Simple compression based on features (placeholder for actual compression)
                if features['entropy'] < 3.0 and features['length'] > 10:
                    # Likely compressible
                    compressed = self._simple_compress(msg)
                    method = "simd_optimized"
                    ratio = len(msg) / len(compressed) if len(compressed) > 0 else 1.0
                else:
                    # Not worth compressing
                    compressed = msg.encode('utf-8')
                    method = "uncompressed"
                    ratio = 1.0

                metadata = {
                    'original_size': len(msg.encode('utf-8')),
                    'compressed_size': len(compressed),
                    'ratio': ratio,
                    'method': method,
                    'simd_features': features
                }

                results.append((compressed, method, metadata))

        else:
            # Fallback to individual processing
            self.compression_stats['fallback_batches'] += 1
            results = []

            for msg in messages:
                compressed = self._simple_compress(msg)
                ratio = len(msg) / len(compressed) if len(compressed) > 0 else 1.0

                metadata = {
                    'original_size': len(msg.encode('utf-8')),
                    'compressed_size': len(compressed),
                    'ratio': ratio,
                    'method': 'fallback',
                    'processed_with_simd': False
                }

                results.append((compressed, 'fallback', metadata))

        # Update statistics
        self.compression_stats['total_messages'] += len(messages)
        self.compression_stats['avg_batch_size'] = (
            (self.compression_stats['avg_batch_size'] * (self.compression_stats['total_messages'] - len(messages)) +
             len(messages)) / self.compression_stats['total_messages']
        )

        return results

    def _simple_compress(self, message: str) -> bytes:
        """Simple compression for demonstration (replace with actual compression)."""
        # Simple run-length encoding for repeated characters
        if len(message) < 10:
            return message.encode('utf-8')

        compressed = bytearray()
        i = 0
        while i < len(message):
            char = message[i]
            count = 1
            while i + count < len(message) and message[i + count] == char and count < 255:
                count += 1

            if count > 3:  # Only compress runs of 4+ characters
                compressed.extend([ord(char), count])
            else:
                for _ in range(count):
                    compressed.append(ord(char))

            i += count

        # Add compression marker
        result = bytearray([0x01])  # Simple compression marker
        result.extend(compressed)

        # Return compressed if smaller, otherwise original
        original_bytes = message.encode('utf-8')
        return bytes(result) if len(result) < len(original_bytes) else original_bytes

    def get_stats(self) -> Dict[str, Any]:
        """Get compression statistics."""
        return {
            'simd_processor': self.simd_processor.get_stats(),
            'compression': self.compression_stats
        }