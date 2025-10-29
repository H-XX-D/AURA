from aura_compression import ProductionHybridCompressor

text = "Test message for audit logging that is long enough to be compressed properly"
comp = ProductionHybridCompressor(enable_aura=True, min_compression_size=10)
compressed, method, meta = comp.compress(text)
print("method:", method)
print("meta:", meta)
print("compressed length:", len(compressed))
# show raw token bytes for Aura Lite
if compressed[0] == 0x04:  # AURA_LITE
    payload = compressed[1:]
    print("payload header:", payload[:12])
    if payload[:1] == b"\xAA":
        token_len = payload[2]
        tokens = payload[3:3+token_len]
    elif payload[:4] == b"AUL1":
        token_len = int.from_bytes(payload[6:10], 'big')
        tokens = payload[11:11+token_len]
    else:
        tokens = payload
    print("tokens:", list(tokens))
    # Walk tokens human-readable
    i = 0
    out = []
    while i < len(tokens):
        kind = tokens[i]; i += 1
        if kind == 0x00:
            tid = tokens[i]; i += 1
            sc = tokens[i]; i += 1
            slots = []
            for _ in range(sc):
                sl = int.from_bytes(tokens[i:i+2], 'big'); i += 2
                s = tokens[i:i+sl].decode('utf-8'); i += sl
                slots.append(s)
            out.append(("T", tid, slots))
        elif kind == 0x01:
            eid = tokens[i]; i += 1
            out.append(("D", eid))
        elif kind == 0x03:
            ln = tokens[i]; i += 1
            s = tokens[i:i+ln].decode('utf-8'); i += ln
            out.append(("L", s))
        else:
            out.append(("?", kind))
    print("parsed tokens:")
    for t in out:
        print(t)

plain = comp.decompress(compressed)
print("decompressed:", plain)
print("equal:", plain == text)
