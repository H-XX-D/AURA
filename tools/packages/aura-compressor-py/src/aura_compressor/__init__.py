"""
AURA Compressor Python package.

Regenerated interfaces expose the minimal surface that the surrounding
project and tests depend on. Implementations focus on clarity and the
behaviour documented in the verification notes.
"""

from .lib.template_manager import TemplateManager, TemplateRecord
from .lib.template_discovery import TemplateDiscovery, TemplateCandidate
from .lib.hacs_tokenizer import HACSTokenizer
from .streamer import AuraStreamSession

__all__ = [
    "TemplateManager",
    "TemplateRecord",
    "TemplateDiscovery",
    "TemplateCandidate",
    "HACSTokenizer",
    "AuraStreamSession",
]
