#!/usr/bin/env python3
"""
Template Discovery Engine - Patent Claims 3, 15-18
Automatically derives compression templates from historical audit logs using:
- N-gram frequency analysis (Claim 3)
- Edit-distance clustering (Claim 15)
- Regex inference
- Prefix/suffix extraction
"""
import re
import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Optional, Set, Tuple
from difflib import SequenceMatcher


@dataclass
class TemplateCandidate:
    """
    Candidate template discovered from audit logs
    """
    pattern: str  # Pattern with {0}, {1}, etc. slots
    frequency: int  # How often this pattern appears
    compression_ratio: float  # Estimated compression advantage
    slot_count: int  # Number of variable slots
    examples: List[str] = field(default_factory=list)  # Example messages
    safety_approved: bool = False  # Passed safety screening
    version: int = 1  # Template version number
    discovered_at: Optional[str] = None  # ISO timestamp

    # Usage tracking for LRU cache and demotion (Claim 18)
    usage_count: int = 0  # Times this template was used
    last_used: Optional[str] = None  # Last usage timestamp
    days_since_used: int = 0  # Days since last use

    def record_usage(self) -> None:
        """Record that this template was used"""
        self.usage_count += 1
        self.last_used = datetime.now(timezone.utc).isoformat()
        self.days_since_used = 0

    def update_days_since_used(self) -> None:
        """Update days since last use"""
        if self.last_used:
            try:
                last_used_dt = datetime.fromisoformat(self.last_used.replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                delta = now - last_used_dt
                self.days_since_used = delta.days
            except Exception:
                self.days_since_used = 0

    def to_dict(self) -> Dict:
        return {
            'pattern': self.pattern,
            'frequency': self.frequency,
            'compression_ratio': self.compression_ratio,
            'slot_count': self.slot_count,
            'examples': self.examples[:3],  # First 3 examples
            'safety_approved': self.safety_approved,
            'version': self.version,
            'discovered_at': self.discovered_at,
            'usage_count': self.usage_count,
            'last_used': self.last_used,
            'days_since_used': self.days_since_used,
        }


class NGramMiner:
    """
    N-gram frequency analysis for template discovery (Claim 3)
    """

    def __init__(self, min_ngram_length: int = 10, max_ngram_length: int = 100):
        self.min_ngram_length = min_ngram_length
        self.max_ngram_length = max_ngram_length

    def extract_ngrams(self, messages: List[str], min_frequency: int = 5) -> List[Tuple[str, int]]:
        """
        Extract frequent n-grams from messages (Claim 3)

        Args:
            messages: List of plaintext messages from audit logs
            min_frequency: Minimum occurrences to be considered

        Returns:
            List of (ngram, frequency) tuples sorted by frequency
        """
        ngram_counts = Counter()

        for message in messages:
            # Extract n-grams of varying lengths
            for n in range(self.min_ngram_length, min(self.max_ngram_length, len(message))):
                for i in range(len(message) - n + 1):
                    ngram = message[i:i + n]
                    # Skip pure whitespace or special chars
                    if len(ngram.strip()) >= self.min_ngram_length:
                        ngram_counts[ngram] += 1

        # Filter by minimum frequency
        frequent_ngrams = [(ngram, count) for ngram, count in ngram_counts.items()
                          if count >= min_frequency]

        # Sort by frequency descending
        frequent_ngrams.sort(key=lambda x: x[1], reverse=True)

        return frequent_ngrams


class ClusteringEngine:
    """
    Edit-distance clustering to identify paraphrased variations (Claims 3, 15)
    """

    def __init__(self, similarity_threshold: float = 0.7):
        """
        Args:
            similarity_threshold: Minimum similarity (0-1) to cluster messages
        """
        self.similarity_threshold = similarity_threshold

    def compute_similarity(self, text1: str, text2: str) -> float:
        """
        Compute edit distance similarity (Claim 15)

        Returns:
            Similarity score 0-1 (1 = identical)
        """
        return SequenceMatcher(None, text1, text2).ratio()

    def cluster_messages(self, messages: List[str]) -> List[List[str]]:
        """
        Cluster similar messages using edit distance (Claim 15)

        Returns:
            List of message clusters
        """
        if not messages:
            return []

        clusters = []
        unclustered = messages.copy()

        while unclustered:
            # Start new cluster with first unclustered message
            seed = unclustered.pop(0)
            cluster = [seed]

            # Find similar messages
            remaining = []
            for msg in unclustered:
                similarity = self.compute_similarity(seed, msg)
                if similarity >= self.similarity_threshold:
                    cluster.append(msg)
                else:
                    remaining.append(msg)

            clusters.append(cluster)
            unclustered = remaining

        return clusters


class PatternExtractor:
    """
    Extract parameterized patterns with variable slots (Claim 3)
    """

    def extract_pattern(self, messages: List[str]) -> Optional[TemplateCandidate]:
        """
        Extract common pattern from clustered messages (Claim 3)

        Returns:
            TemplateCandidate with pattern and slots, or None if no pattern found
        """
        if not messages or len(messages) < 2:
            return None

        # Find longest common subsequences
        pattern = self._find_common_structure(messages)

        if not pattern:
            return None

        # Count slots in pattern
        slot_count = pattern.count('{')

        # Estimate compression ratio
        avg_message_len = sum(len(m) for m in messages) / len(messages)
        pattern_len = len(pattern)
        compression_ratio = avg_message_len / pattern_len if pattern_len > 0 else 1.0

        return TemplateCandidate(
            pattern=pattern,
            frequency=len(messages),
            compression_ratio=compression_ratio,
            slot_count=slot_count,
            examples=messages[:5],
            discovered_at=datetime.now(timezone.utc).isoformat(),
        )

    def _find_common_structure(self, messages: List[str]) -> Optional[str]:
        """
        Find common structure across messages, marking variations as {0}, {1}, etc.
        """
        if len(messages) < 2:
            return messages[0] if messages else None

        # Start with first message as reference
        reference = messages[0]
        tokens = reference.split()

        # Find token positions that vary across messages
        variable_positions = set()
        for i, token in enumerate(tokens):
            # Check if this token varies in other messages
            for other_msg in messages[1:]:
                other_tokens = other_msg.split()
                if i >= len(other_tokens) or other_tokens[i] != token:
                    variable_positions.add(i)
                    break

        # Build pattern with slots
        pattern_tokens = []
        slot_index = 0
        for i, token in enumerate(tokens):
            if i in variable_positions:
                pattern_tokens.append(f'{{{slot_index}}}')
                slot_index += 1
            else:
                pattern_tokens.append(token)

        pattern = ' '.join(pattern_tokens)

        # Only return pattern if it has some fixed structure
        if pattern.count('{') >= len(tokens):
            return None  # Too generic

        return pattern


class SafetyScreener:
    """
    Safety screening for template candidates (Claim 3)
    Prevents promotion of harmful patterns
    """

    def __init__(self):
        # Harmful patterns to reject
        self.harmful_keywords = {
            'password', 'secret', 'api_key', 'token', 'credentials',
            'hack', 'exploit', 'vulnerability', 'inject', 'bypass',
            'illegal', 'weapon', 'drug', 'harm', 'attack',
        }

    def screen(self, candidate: TemplateCandidate) -> bool:
        """
        Screen template candidate for safety (Claim 3)

        Returns:
            True if safe, False if potentially harmful
        """
        pattern_lower = candidate.pattern.lower()

        # Check for harmful keywords
        for keyword in self.harmful_keywords:
            if keyword in pattern_lower:
                return False

        # Check examples
        for example in candidate.examples:
            example_lower = example.lower()
            for keyword in self.harmful_keywords:
                if keyword in example_lower:
                    return False

        return True


class TemplateDiscoveryEngine:
    """
    Main template discovery engine (Claims 3, 15-18)
    Combines n-gram mining, clustering, pattern extraction, and safety screening
    """

    def __init__(
        self,
        min_frequency: int = 5,
        compression_threshold: float = 2.0,
        similarity_threshold: float = 0.7,
        starting_template_id: int = 200,
        max_template_id: int = 255,
    ):
        """
        Args:
            min_frequency: Minimum pattern occurrences for promotion (Claim 16)
            compression_threshold: Minimum compression advantage (Claim 16)
            similarity_threshold: Clustering similarity threshold (Claim 15)
            starting_template_id: First ID to assign to discovered templates
            max_template_id: Highest ID allowed for discovered templates (fits 1 byte)
        """
        self.min_frequency = min_frequency
        self.compression_threshold = compression_threshold
        self.starting_template_id = starting_template_id
        self.max_template_id = max_template_id

        self.ngram_miner = NGramMiner()
        self.clustering_engine = ClusteringEngine(similarity_threshold)
        self.pattern_extractor = PatternExtractor()
        self.safety_screener = SafetyScreener()

        # Promoted templates (Claim 17)
        self.promoted_templates: Dict[int, TemplateCandidate] = {}
        self.next_template_id = starting_template_id

    def discover_templates(self, messages: List[str]) -> List[TemplateCandidate]:
        """
        Discover templates from audit log messages (Claim 3)

        Pipeline:
        1. N-gram mining to find frequent phrases
        2. Clustering to group paraphrased variations
        3. Pattern extraction to create templates with slots
        4. Safety screening to prevent harmful patterns
        5. Compression testing to ensure advantage

        Returns:
            List of approved template candidates ready for promotion
        """
        if not messages:
            return []

        print(f"Discovering templates from {len(messages)} messages...")

        # Step 1: Cluster similar messages (Claim 15)
        print("Step 1: Clustering similar messages...")
        clusters = self.clustering_engine.cluster_messages(messages)
        print(f"  Found {len(clusters)} clusters")

        # Step 2: Extract patterns from clusters (Claim 3)
        print("Step 2: Extracting patterns...")
        candidates = []
        for cluster in clusters:
            if len(cluster) >= self.min_frequency:
                pattern = self.pattern_extractor.extract_pattern(cluster)
                if pattern:
                    candidates.append(pattern)

        print(f"  Extracted {len(candidates)} pattern candidates")

        # Step 3: Safety screening (Claim 3)
        print("Step 3: Safety screening...")
        safe_candidates = []
        for candidate in candidates:
            if self.safety_screener.screen(candidate):
                candidate.safety_approved = True
                safe_candidates.append(candidate)

        print(f"  {len(safe_candidates)} candidates passed safety")

        # Step 4: Compression advantage testing (Claim 16)
        print("Step 4: Testing compression advantage...")
        approved_candidates = []
        for candidate in safe_candidates:
            if candidate.compression_ratio >= self.compression_threshold:
                approved_candidates.append(candidate)

        print(f"  {len(approved_candidates)} candidates meet compression threshold")

        return approved_candidates

    def promote_template(self, candidate: TemplateCandidate) -> int:
        """
        Promote template candidate to production (Claims 3, 17, 18)

        Returns:
            Template ID assigned to promoted template
        """
        template_id = self.next_template_id
        if template_id > self.max_template_id:
            raise RuntimeError(
                f"Discovered template ID capacity exhausted (>{self.max_template_id}). "
                "Increase max_template_id or retire old templates."
            )
        self.next_template_id += 1

        # Version and timestamp
        candidate.version = 1
        candidate.discovered_at = datetime.now(timezone.utc).isoformat()

        self.promoted_templates[template_id] = candidate

        # Log promotion event for forensic review (Claim 18)
        print(f"PROMOTED: Template {template_id}")
        print(f"  Pattern: {candidate.pattern}")
        print(f"  Frequency: {candidate.frequency}")
        print(f"  Compression: {candidate.compression_ratio:.2f}:1")
        print(f"  Safety: {'APPROVED' if candidate.safety_approved else 'PENDING'}")

        return template_id

    def get_template_store(self) -> Dict[int, str]:
        """
        Get template store for client synchronization (Claim 17)

        Returns:
            Dictionary of template_id -> pattern for clients
        """
        return {tid: template.pattern for tid, template in self.promoted_templates.items()}

    def export_audit_log(self) -> List[Dict]:
        """
        Export promotion events for forensic review (Claim 18)

        Returns:
            List of promotion event records
        """
        events = []
        for template_id, template in self.promoted_templates.items():
            events.append({
                'template_id': template_id,
                'pattern': template.pattern,
                'frequency': template.frequency,
                'compression_ratio': template.compression_ratio,
                'safety_approved': template.safety_approved,
                'version': template.version,
                'discovered_at': template.discovered_at,
            })
        return events


class PrefixSuffixExtractor:
    """
    Extract repeated intros/outros for dictionary additions (Claim 3)
    """

    def __init__(self, min_length: int = 5):
        self.min_length = min_length

    def extract_prefixes(self, messages: List[str], min_frequency: int = 5) -> List[Tuple[str, int]]:
        """Extract common prefixes"""
        prefix_counts = Counter()

        for message in messages:
            # Try prefixes of varying lengths
            for length in range(self.min_length, min(50, len(message))):
                prefix = message[:length]
                if prefix.endswith(' '):  # End at word boundary
                    prefix_counts[prefix.strip()] += 1

        frequent = [(p, c) for p, c in prefix_counts.items() if c >= min_frequency]
        frequent.sort(key=lambda x: x[1], reverse=True)
        return frequent

    def extract_suffixes(self, messages: List[str], min_frequency: int = 5) -> List[Tuple[str, int]]:
        """Extract common suffixes"""
        suffix_counts = Counter()

        for message in messages:
            # Try suffixes of varying lengths
            for length in range(self.min_length, min(50, len(message))):
                suffix = message[-length:]
                if suffix.startswith(' '):  # Start at word boundary
                    suffix_counts[suffix.strip()] += 1

        frequent = [(s, c) for s, c in suffix_counts.items() if c >= min_frequency]
        frequent.sort(key=lambda x: x[1], reverse=True)
        return frequent
