from __future__ import annotations

import aura_compression
from aura_compression import aiwire, research


def test_aiwire_facade_has_versioned_stable_contract() -> None:
    assert aiwire.AIWIRE_PUBLIC_API_VERSION == 1
    assert aiwire.AI_WIRE_VERSION == 1
    assert aiwire.AI_WIRE_PROTOCOL == "aura.aiwire"


def test_historical_root_aiwire_exports_are_compatible_aliases() -> None:
    assert aiwire.AIWireSessionEncoder is aura_compression.AIWireSessionEncoder
    assert aiwire.AIWireSessionDecoder is aura_compression.AIWireSessionDecoder
    assert aiwire.build_aiwire_handshake is aura_compression.build_aiwire_handshake


def test_stable_facade_round_trips_a_frame() -> None:
    payload = b'{"id":1,"jsonrpc":"2.0","method":"tools/list"}'
    encoder = aiwire.AIWireSessionEncoder(use_native=False)
    decoder = aiwire.AIWireSessionDecoder(use_native=False)

    assert decoder.decompress_frame(encoder.compress_frame(payload)) == payload


def test_research_namespace_is_explicitly_experimental() -> None:
    assert research.RESEARCH_API_STABILITY == "experimental"
    assert research.ProductionHybridCompressor is aura_compression.ProductionHybridCompressor
