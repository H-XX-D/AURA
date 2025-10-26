import os
from pathlib import Path

import pytest

from aura_compression.compressor import ProductionHybridCompressor
from aura_compression.sidechain import NoOpSidechainService, SidechainConfig, SidechainService


@pytest.fixture()
def sidechain_tmp(tmp_path: Path):
    db_path = tmp_path / "sidechain.db"
    blob_dir = tmp_path / "blobs"
    config = SidechainConfig(
        enabled=True,
        db_path=str(db_path),
        blob_dir=str(blob_dir),
        inline_threshold=32,
        blob_threshold=256,
    )
    service = SidechainService(config)
    try:
        yield service
    finally:
        service.close()


def test_sidechain_inline_storage(sidechain_tmp: SidechainService):
    payload = b"small-payload"
    metadata = {
        "original_size": len(payload),
        "compressed_size": len(payload),
        "method": "binary_semantic",
    }

    ref = sidechain_tmp.store_entry(payload, metadata)
    assert ref is not None
    assert ref.startswith("inline:")

    rows = sidechain_tmp.fetch_recent(limit=1)
    assert rows
    row = rows[0]
    assert row["storage_kind"] == "inline"
    assert row["metadata"]["method"] == "binary_semantic"


def test_sidechain_blob_storage(sidechain_tmp: SidechainService):
    payload = os.urandom(128)
    metadata = {
        "original_size": len(payload),
        "compressed_size": len(payload),
        "method": "auralite",
    }

    ref = sidechain_tmp.store_entry(payload, metadata)
    assert ref is not None
    assert ref.endswith(".bin")
    assert Path(ref).exists()

    rows = sidechain_tmp.fetch_recent(limit=1)
    assert rows[0]["storage_kind"] == "blob"


def test_sidechain_noop():
    noop = NoOpSidechainService()
    assert not noop.is_enabled
    assert noop.store_entry(b"data", {"method": "binary"}) is None
    assert noop.fetch_recent() == []


def test_compressor_semantic_sketch_persists(tmp_path: Path):
    compressor = ProductionHybridCompressor(
        min_compression_size=0,
        enable_aura=False,
        enable_gpu=False,
        enable_sidechain=True,
        sidechain_config={
            "db_path": str(tmp_path / "sidechain.db"),
            "blob_dir": str(tmp_path / "blobs"),
            "inline_threshold": 1024,
            "blob_threshold": 4096,
        },
    )
    text = "status=ok user=alice latency=120ms component=api\n" * 2
    try:
        _, _, metadata = compressor.compress(text)
        sketch = metadata.get("semantic_sketch")
        assert sketch is not None
        assert sketch["length"] == len(text)
        assert sketch.get("preview")
        assert isinstance(sketch.get("top_tokens"), list)

        assert compressor._sidechain.is_enabled  # type: ignore[attr-defined]
        rows = compressor._sidechain.fetch_recent(limit=1)  # type: ignore[attr-defined]
        assert rows
        stored = rows[0]["metadata"].get("semantic_sketch", {})
        assert stored.get("preview") == sketch.get("preview")
    finally:
        compressor._sidechain.close()  # type: ignore[attr-defined]
