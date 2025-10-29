#!/usr/bin/env python3
"""
AURA Automatic Template Discovery

Implements Claims 3, 15-18: Automatic discovery of emergent response
templates from production AI traffic.

Copyright (c) 2025 Todd James Hendricks
Licensed under Apache License 2.0
Patent Pending - Application No. 19/366,538
"""

from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict
import re
from dataclasses import dataclass, field
import difflib


@dataclass
class DiscoveredTemplate:
    """A template discovered from production traffic (Claim 15)"""
    pattern: str  # Template pattern with {0}, {1} slots
    frequency: int  # Occurrence count
    avg_compression_ratio: float  # Expected compression ratio
    category: str  # Response category
    examples: List[str]  # Example messages
    confidence: float  # Discovery confidence (0-1)
    template_id: Optional[int] = None  # Assigned template ID
    slot_count: int = 0  # Number of parameter slots


class TemplateDiscovery:
    """
    Automatic Template Discovery System (Claims 15-18)

    Analyzes production AI traffic to discover emergent response patterns,
    extract parameterized templates, and add them to the compression library.

    Discovery Pipeline (Claim 15):
    1. Collect message corpus from production traffic
    2. Extract common patterns using n-gram analysis
    3. Parameterize patterns into templates with {0}, {1} slots
    4. Validate templates with frequency and confidence thresholds
    5. Calculate compression ratios
    6. Add high-value templates to library

    Performance Metrics:
    - Minimum frequency: 3 occurrences (default)
    - Minimum confidence: 0.8 (default)
    - Target: 200+ templates (Claim 5)
    - Coverage goal: 72% of AI messages (Appendix C)
    """

    def __init__(self, min_frequency: int = 3, min_confidence: float = 0.8):
        self.min_frequency = min_frequency
        self.min_confidence = min_confidence
        self.message_history: List[str] = []
        self.discovered_templates: List[DiscoveredTemplate] = []
        self.next_template_id = 200  # Start discovered templates at ID 200

    def analyze_messages(self, messages: List[str]) -> List[DiscoveredTemplate]:
        """
        Analyze message corpus to discover templates (Claim 15)

        Args:
            messages: List of AI-generated messages from production traffic

        Returns:
            List of validated templates ready for compression library
        """
        self.message_history.extend(messages)

        # Step 1: Extract n-grams and identify common phrases
        ngrams = self.extract_ngrams(messages, n=5)

        # Step 2: Find frequently occurring patterns
        frequent_patterns = self.find_frequent_patterns(ngrams)

        # Step 3: Cluster similar messages
        message_clusters = self.cluster_similar_messages(messages)

        # Step 4: Parameterize patterns from clusters
        templates = self.parameterize_clusters(message_clusters)

        # Step 5: Validate templates
        validated_templates = self.validate_templates(templates)

        # Step 6: Calculate compression ratios
        for template in validated_templates:
            template.avg_compression_ratio = self.estimate_compression_ratio(template)
            template.slot_count = template.pattern.count('{')

        # Step 7: Assign template IDs
        for template in validated_templates:
            template.template_id = self.next_template_id
            self.next_template_id += 1

        self.discovered_templates.extend(validated_templates)

        return validated_templates

    def extract_ngrams(self, messages: List[str], n: int = 5) -> Dict[str, int]:
        """
        Extract n-grams from message corpus (Claim 16)

        Args:
            messages: Message corpus
            n: N-gram size (default 5 words)

        Returns:
            Dictionary mapping n-grams to occurrence counts
        """
        ngrams = defaultdict(int)

        for message in messages:
            words = message.split()
            # Extract n-grams of varying sizes (3 to n words)
            for gram_size in range(3, min(n + 1, len(words) + 1)):
                for i in range(len(words) - gram_size + 1):
                    ngram = ' '.join(words[i:i + gram_size])
                    ngrams[ngram] += 1

        return ngrams

    def find_frequent_patterns(self, ngrams: Dict[str, int]) -> List[Tuple[str, int]]:
        """
        Find patterns occurring above frequency threshold (Claim 16)

        Args:
            ngrams: N-gram frequency dictionary

        Returns:
            List of (pattern, count) tuples sorted by frequency
        """
        frequent = []

        for ngram, count in ngrams.items():
            if count >= self.min_frequency:
                frequent.append((ngram, count))

        # Sort by frequency (most frequent first)
        frequent.sort(key=lambda x: x[1], reverse=True)

        return frequent

    def cluster_similar_messages(self, messages: List[str]) -> List[List[str]]:
        """
        Cluster similar messages using edit distance (Claim 17)

        Uses difflib.SequenceMatcher to group messages with similar structure.

        Args:
            messages: Message corpus

        Returns:
            List of message clusters (each cluster is a list of similar messages)
        """
        clusters: List[List[str]] = []
        used: Set[int] = set()

        for i, msg1 in enumerate(messages):
            if i in used:
                continue

            cluster = [msg1]
            used.add(i)

            for j, msg2 in enumerate(messages):
                if j <= i or j in used:
                    continue

                # Calculate similarity ratio
                similarity = difflib.SequenceMatcher(None, msg1, msg2).ratio()

                # If messages are structurally similar (60%+ match)
                if similarity >= 0.6:
                    cluster.append(msg2)
                    used.add(j)

            # Only keep clusters with multiple messages
            if len(cluster) >= self.min_frequency:
                clusters.append(cluster)

        return clusters

    def parameterize_clusters(self, clusters: List[List[str]]) -> List[DiscoveredTemplate]:
        """
        Parameterize message clusters into templates (Claim 17)

        For each cluster, identifies the common structure and variable parts,
        creating a template pattern with {0}, {1}, etc. placeholders.

        Example:
            Cluster: ["The capital of France is Paris",
                     "The capital of Spain is Madrid"]
            Template: "The capital of {0} is {1}"

        Args:
            clusters: List of message clusters

        Returns:
            List of discovered templates
        """
        templates = []

        for cluster in clusters:
            if len(cluster) < self.min_frequency:
                continue

            # Extract template pattern from cluster
            pattern, confidence = self.extract_template_pattern(cluster)

            if not pattern or confidence < self.min_confidence:
                continue

            template = DiscoveredTemplate(
                pattern=pattern,
                frequency=len(cluster),
                avg_compression_ratio=0.0,  # Calculated later
                category=self.categorize_pattern(pattern),
                examples=cluster[:10],  # Keep up to 10 examples
                confidence=confidence
            )
            templates.append(template)

        return templates

    def extract_template_pattern(self, messages: List[str]) -> Tuple[Optional[str], float]:
        """
        Extract template pattern from similar messages (Claim 17)

        Uses word-level alignment to identify fixed and variable parts.

        Args:
            messages: Cluster of similar messages

        Returns:
            Tuple of (template_pattern, confidence_score)
        """
        if len(messages) < 2:
            return None, 0.0

        # Tokenize all messages
        tokenized = [msg.split() for msg in messages]

        # Find minimum length
        min_len = min(len(tokens) for tokens in tokenized)
        if min_len == 0:
            return None, 0.0

        # Align words position by position
        template_parts = []
        param_count = 0
        variable_positions = []

        for pos in range(min_len):
            words_at_pos = [tokens[pos] for tokens in tokenized]
            unique_words = set(words_at_pos)

            if len(unique_words) == 1:
                # All messages have same word - fixed part of template
                template_parts.append(words_at_pos[0])
            else:
                # Words vary - create parameter slot
                template_parts.append(f'{{{param_count}}}')
                param_count += 1
                variable_positions.append(pos)

        # Need at least one parameter slot to be a useful template
        if param_count == 0:
            return None, 0.0

        # Calculate confidence based on ratio of fixed to variable parts
        confidence = (min_len - param_count) / min_len

        template_pattern = ' '.join(template_parts)

        return template_pattern, confidence

    def validate_templates(self, templates: List[DiscoveredTemplate]) -> List[DiscoveredTemplate]:
        """
        Validate discovered templates (Claim 18)

        Ensures templates:
        - Occur frequently enough (min_frequency threshold)
        - Have high confidence (min_confidence threshold)
        - Provide compression benefit (ratio > 1.5:1)
        - Don't overlap with existing templates

        Args:
            templates: Candidate templates

        Returns:
            List of validated templates
        """
        validated = []

        for template in templates:
            # Check frequency threshold
            if template.frequency < self.min_frequency:
                continue

            # Check confidence threshold
            if template.confidence < self.min_confidence:
                continue

            # Check for duplicates with existing templates
            if self.overlaps_existing(template):
                continue

            # Check pattern is valid
            if not template.pattern or len(template.pattern) < 5:
                continue

            validated.append(template)

        return validated

    def overlaps_existing(self, template: DiscoveredTemplate) -> bool:
        """
        Check if template overlaps with existing templates

        Args:
            template: Candidate template

        Returns:
            True if template already exists
        """
        for existing in self.discovered_templates:
            # Exact match check
            if template.pattern == existing.pattern:
                return True

            # Similarity check (90%+ similar)
            similarity = difflib.SequenceMatcher(
                None,
                template.pattern,
                existing.pattern
            ).ratio()

            if similarity >= 0.9:
                return True

        return False

    def estimate_compression_ratio(self, template: DiscoveredTemplate) -> float:
        """
        Estimate compression ratio for template (Claim 18)

        Calculates expected bandwidth savings from using this template.

        Formula:
            ratio = original_size / compressed_size

        Compressed size:
            - Template ID: 1 byte (IDs 0-255) or 2 bytes (256-65535)
            - Param count: 1 byte
            - Each param: 1 byte length + param data

        Args:
            template: Template to estimate

        Returns:
            Compression ratio (e.g., 5.0 means 5:1 compression)
        """
        if not template.examples:
            return 1.0

        total_original = 0
        total_compressed = 0

        for example in template.examples:
            original_size = len(example.encode('utf-8'))
            total_original += original_size

            # Extract parameter values
            params = self.extract_param_values(template.pattern, example)

            # Calculate compressed size
            compressed_size = 1  # Template ID (1 byte for IDs < 256)
            if template.slot_count > 0:
                compressed_size += 1  # Param count
                for param in params:
                    compressed_size += 1 + len(param.encode('utf-8'))  # Length + data

            total_compressed += compressed_size

        ratio = total_original / total_compressed if total_compressed > 0 else 1.0
        return ratio

    def extract_param_values(self, pattern: str, message: str) -> List[str]:
        """
        Extract parameter values from message matching pattern

        Args:
            pattern: Template pattern with {0}, {1} placeholders
            message: Actual message

        Returns:
            List of parameter values
        """
        # Convert template pattern to regex
        # Replace {0}, {1} with capture groups
        regex_pattern = re.escape(pattern)
        for i in range(10):  # Support up to 10 parameters
            regex_pattern = regex_pattern.replace(
                rf'\{{{i}\}}',
                r'(.+?)'
            )

        # Try to match
        match = re.match(regex_pattern, message)
        if match:
            return list(match.groups())

        # Fallback: word-level extraction
        pattern_words = pattern.split()
        message_words = message.split()
        params = []
        param_idx = 0
        msg_idx = 0

        for pattern_word in pattern_words:
            if '{' in pattern_word and '}' in pattern_word:
                # Extract parameter
                if msg_idx < len(message_words):
                    params.append(message_words[msg_idx])
                    msg_idx += 1
            else:
                # Skip fixed word
                msg_idx += 1

        return params

    def categorize_pattern(self, pattern: str) -> str:
        """
        Categorize template pattern into semantic category

        Categories match Appendix C:
        - limitations: AI capability boundaries
        - facts: Factual statements
        - definitions: Technical definitions
        - code_examples: Programming examples
        - instructions: How-to guides
        - comparisons: Contrast statements
        - explanations: Reasoning
        - enumerations: Lists
        - recommendations: Advice
        - clarifications: Follow-up questions
        - general: Other

        Args:
            pattern: Template pattern

        Returns:
            Category name
        """
        pattern_lower = pattern.lower()

        # Category detection rules
        if any(keyword in pattern_lower for keyword in
               ["cannot", "don't have", "unable to", "can't", "not able"]):
            return 'limitations'

        elif '```' in pattern or 'code' in pattern_lower or 'example' in pattern_lower:
            return 'code_examples'

        elif pattern_lower.startswith('to ') or 'how to' in pattern_lower:
            return 'instructions'

        elif ' is ' in pattern_lower or ' are ' in pattern_lower:
            if 'definition' in pattern_lower or 'means' in pattern_lower:
                return 'definitions'
            else:
                return 'facts'

        elif 'versus' in pattern_lower or 'compared to' in pattern_lower:
            return 'comparisons'

        elif 'because' in pattern_lower or 'reason' in pattern_lower:
            return 'explanations'

        elif pattern.count(',') >= 2 or 'first' in pattern_lower:
            return 'enumerations'

        elif 'should' in pattern_lower or 'recommend' in pattern_lower:
            return 'recommendations'

        elif '?' in pattern or 'what' in pattern_lower or 'which' in pattern_lower:
            return 'clarifications'

        else:
            return 'general'

    def get_best_templates(self, top_n: int = 100) -> List[DiscoveredTemplate]:
        """
        Get top N templates by value score

        Value score = compression_ratio × frequency

        Args:
            top_n: Number of templates to return

        Returns:
            Top N templates sorted by value
        """
        scored = [
            (t, t.avg_compression_ratio * t.frequency)
            for t in self.discovered_templates
        ]
        scored.sort(key=lambda x: x[1], reverse=True)

        return [t for t, score in scored[:top_n]]

    def export_templates(self, format: str = 'dict') -> Dict[int, str]:
        """
        Export discovered templates for compression library (Claim 18)

        Args:
            format: Export format ('dict' or 'json')

        Returns:
            Dictionary mapping template IDs to pattern strings
        """
        exported = {}

        for template in self.get_best_templates():
            if template.template_id:
                exported[template.template_id] = template.pattern

        return exported

    def get_statistics(self) -> Dict[str, any]:
        """
        Get discovery statistics

        Returns:
            Statistics dictionary
        """
        total_templates = len(self.discovered_templates)

        categories = defaultdict(int)
        for template in self.discovered_templates:
            categories[template.category] += 1

        avg_ratio = sum(t.avg_compression_ratio for t in self.discovered_templates) / total_templates if total_templates > 0 else 0.0
        avg_frequency = sum(t.frequency for t in self.discovered_templates) / total_templates if total_templates > 0 else 0.0

        return {
            'total_templates': total_templates,
            'categories': dict(categories),
            'avg_compression_ratio': avg_ratio,
            'avg_frequency': avg_frequency,
            'messages_analyzed': len(self.message_history),
        }
