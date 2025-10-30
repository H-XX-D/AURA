#!/usr/bin/env python3
"""
Template Normalization Layer
Normalizes variable content (timestamps, UUIDs, IPs, floats) to increase template hit rates
"""

import re
from typing import Dict, Tuple
from dataclasses import dataclass


@dataclass
class NormalizationResult:
    """Result of text normalization"""
    normalized_text: str
    replacements: Dict[str, str]
    normalization_count: int


class TemplateNormalizer:
    """
    Normalize text before template matching to handle variable content

    Examples:
        "Deployment started at 2025-10-23T10:30:00Z"
        → "Deployment started at __TIMESTAMP_0__"

        "Request abc-123-def completed"
        → "Request __UUID_0__ completed"
    """

    # Regex patterns for normalization
    TIMESTAMP_ISO = re.compile(
        r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?',
        re.IGNORECASE
    )

    TIMESTAMP_HUMAN = re.compile(
        r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}',
        re.IGNORECASE
    )

    UUID_PATTERN = re.compile(
        r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b',
        re.IGNORECASE
    )

    IP_V4 = re.compile(
        r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
    )

    IP_V6 = re.compile(
        r'\b(?:[0-9a-f]{1,4}:){7}[0-9a-f]{1,4}\b',
        re.IGNORECASE
    )

    FLOAT_NUMBER = re.compile(
        r'\b\d+\.\d+\b'
    )

    HEX_NUMBER = re.compile(
        r'\b0x[0-9a-f]+\b',
        re.IGNORECASE
    )

    # Common units to preserve context
    SIZE_WITH_UNIT = re.compile(
        r'\b(\d+(?:\.\d+)?)\s*(KB|MB|GB|TB|KiB|MiB|GiB|TiB|bytes?)\b',
        re.IGNORECASE
    )

    TIME_WITH_UNIT = re.compile(
        r'\b(\d+(?:\.\d+)?)\s*(ms|μs|ns|s|sec|min|hour|hr)s?\b',
        re.IGNORECASE
    )

    def __init__(self, enable_timestamp: bool = True,
                 enable_uuid: bool = True,
                 enable_ip: bool = True,
                 enable_float: bool = True,
                 enable_hex: bool = True,
                 enable_size: bool = True,
                 enable_time: bool = True):
        """
        Initialize normalizer with configurable patterns

        Args:
            enable_timestamp: Normalize ISO/human timestamps
            enable_uuid: Normalize UUIDs
            enable_ip: Normalize IP addresses
            enable_float: Normalize floating point numbers
            enable_hex: Normalize hex numbers
            enable_size: Normalize sizes with units (preserves unit)
            enable_time: Normalize times with units (preserves unit)
        """
        self.enable_timestamp = enable_timestamp
        self.enable_uuid = enable_uuid
        self.enable_ip = enable_ip
        self.enable_float = enable_float
        self.enable_hex = enable_hex
        self.enable_size = enable_size
        self.enable_time = enable_time

    def normalize(self, text: str) -> NormalizationResult:
        """
        Normalize text for template matching

        Returns:
            NormalizationResult with normalized text and replacements
        """
        replacements = {}
        normalized = text
        count = 0

        # Order matters: do timestamps before floats to avoid partial matches

        # 1. Timestamps (ISO 8601)
        if self.enable_timestamp:
            for match in self.TIMESTAMP_ISO.finditer(text):
                key = f"__TIMESTAMP_{count}__"
                replacements[key] = match.group(0)
                normalized = normalized.replace(match.group(0), key, 1)
                count += 1

            # Human-readable timestamps
            for match in self.TIMESTAMP_HUMAN.finditer(text):
                if match.group(0) not in replacements.values():  # Avoid double-replacement
                    key = f"__TIMESTAMP_{count}__"
                    replacements[key] = match.group(0)
                    normalized = normalized.replace(match.group(0), key, 1)
                    count += 1

        # 2. UUIDs
        if self.enable_uuid:
            for match in self.UUID_PATTERN.finditer(text):
                key = f"__UUID_{count}__"
                replacements[key] = match.group(0)
                normalized = normalized.replace(match.group(0), key, 1)
                count += 1

        # 3. IP addresses
        if self.enable_ip:
            # IPv6 first (longer pattern)
            for match in self.IP_V6.finditer(text):
                key = f"__IPV6_{count}__"
                replacements[key] = match.group(0)
                normalized = normalized.replace(match.group(0), key, 1)
                count += 1

            # IPv4
            for match in self.IP_V4.finditer(text):
                key = f"__IPV4_{count}__"
                replacements[key] = match.group(0)
                normalized = normalized.replace(match.group(0), key, 1)
                count += 1

        # 4. Sizes with units (preserve unit for context)
        if self.enable_size:
            for match in self.SIZE_WITH_UNIT.finditer(text):
                value, unit = match.groups()
                key = f"__SIZE_{count}_{unit.upper()}__"
                replacements[key] = match.group(0)
                normalized = normalized.replace(match.group(0), key, 1)
                count += 1

        # 5. Times with units (preserve unit for context)
        if self.enable_time:
            for match in self.TIME_WITH_UNIT.finditer(text):
                value, unit = match.groups()
                key = f"__TIME_{count}_{unit.upper()}__"
                replacements[key] = match.group(0)
                normalized = normalized.replace(match.group(0), key, 1)
                count += 1

        # 6. Hex numbers
        if self.enable_hex:
            for match in self.HEX_NUMBER.finditer(text):
                key = f"__HEX_{count}__"
                replacements[key] = match.group(0)
                normalized = normalized.replace(match.group(0), key, 1)
                count += 1

        # 7. Floating point numbers (last to avoid matching timestamp parts)
        if self.enable_float:
            # Only match floats not already replaced
            temp_text = normalized
            for match in self.FLOAT_NUMBER.finditer(temp_text):
                # Skip if this position is already replaced (contains __)
                if '__' not in normalized[max(0, normalized.find(match.group(0))-5):
                                        normalized.find(match.group(0))+len(match.group(0))+5]:
                    key = f"__FLOAT_{count}__"
                    replacements[key] = match.group(0)
                    normalized = normalized.replace(match.group(0), key, 1)
                    count += 1

        return NormalizationResult(
            normalized_text=normalized,
            replacements=replacements,
            normalization_count=count
        )

    def denormalize(self, text: str, replacements: Dict[str, str]) -> str:
        """
        Restore original values after template formatting

        Args:
            text: Normalized text
            replacements: Dictionary of placeholder -> original value

        Returns:
            Text with original values restored
        """
        result = text
        for key, value in replacements.items():
            result = result.replace(key, value)
        return result


# Pre-configured normalizers for common use cases

def get_standard_normalizer() -> TemplateNormalizer:
    """Standard normalizer with all features enabled"""
    return TemplateNormalizer()


def get_aggressive_normalizer() -> TemplateNormalizer:
    """Aggressive normalizer for maximum template matching"""
    return TemplateNormalizer(
        enable_timestamp=True,
        enable_uuid=True,
        enable_ip=True,
        enable_float=True,
        enable_hex=True,
        enable_size=True,
        enable_time=True
    )


def get_conservative_normalizer() -> TemplateNormalizer:
    """Conservative normalizer - only timestamps and UUIDs"""
    return TemplateNormalizer(
        enable_timestamp=True,
        enable_uuid=True,
        enable_ip=False,
        enable_float=False,
        enable_hex=False,
        enable_size=False,
        enable_time=False
    )


# Example usage and tests
if __name__ == "__main__":
    normalizer = get_standard_normalizer()

    # Test cases
    test_cases = [
        "Deployment started at 2025-10-23T10:30:00Z",
        "Request abc-123-def completed in 45ms",
        "Connection from 192.168.1.100 established",
        "Processing file data.csv (1.2 GB)",
        "Error 0x80004005 at offset 0x1234",
        "Response time: 123.45ms, size: 2.5 MB",
    ]

    print("Template Normalization Test\n")
    print("=" * 80)

    for text in test_cases:
        result = normalizer.normalize(text)
        print(f"\nOriginal:   {text}")
        print(f"Normalized: {result.normalized_text}")
        print(f"Replacements: {len(result.replacements)}")

        if result.replacements:
            for key, value in result.replacements.items():
                print(f"  {key} = {value}")

        # Test denormalization
        restored = normalizer.denormalize(result.normalized_text, result.replacements)
        assert restored == text, f"Denormalization failed: {restored} != {text}"
        print("✓ Denormalization verified")

    print("\n" + "=" * 80)
    print("All tests passed!")
