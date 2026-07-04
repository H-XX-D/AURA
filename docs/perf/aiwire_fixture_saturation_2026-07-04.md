# AIWire Fixture Bandwidth Saturation

This report uses the committed public AIWire session fixture corpus. It measures hot-path bytes for each codec, then projects how many concurrent logical agents are needed to fill realistic network profiles.

- Fixture: `fixtures/aiwire_sessions/public_session_corpus_v1.json`
- Exchanges: `36` request/response pairs
- Backend mode: `python`
- Per-agent in-flight window: `1`

The effective capacity is the minimum of bandwidth capacity, latency-window capacity, and measured local codec CPU ceiling.

| Profile | Agents | Codec | B/ex | BW ex/s | Eff ex/s | Msg/s | Fill | Need agents | p95 ms | Limit | vs raw | Saved | Raw Mbps equiv |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| edge_mesh | 1 | aitoken | 529.1 | 2811.0 | 25.5 | 51.0 | 0.9% | 111 | 39.2 | latency_window | 1.02x | 52.1% | 0.23 |
| edge_mesh | 1 | aitoken_aiwire | 359.1 | 4109.0 | 25.6 | 51.2 | 0.6% | 161 | 39.1 | latency_window | 1.02x | 67.5% | 0.23 |
| edge_mesh | 1 | aiwire | 365.6 | 3967.1 | 25.7 | 51.4 | 0.6% | 155 | 38.9 | latency_window | 1.02x | 66.9% | 0.23 |
| edge_mesh | 1 | raw | 1105.3 | 1352.6 | 25.1 | 50.2 | 1.9% | 54 | 39.9 | latency_window | 1.00x | 0.0% | 0.22 |
| edge_mesh | 1 | zlib | 643.2 | 2319.2 | 25.4 | 50.9 | 1.1% | 92 | 39.3 | latency_window | 1.01x | 41.8% | 0.23 |
| edge_mesh | 8 | aitoken | 529.1 | 2811.0 | 204.0 | 408.0 | 7.3% | 111 | 39.2 | latency_window | 1.02x | 52.1% | 1.80 |
| edge_mesh | 8 | aitoken_aiwire | 359.1 | 4109.0 | 204.8 | 409.6 | 5.0% | 161 | 39.1 | latency_window | 1.02x | 67.5% | 1.81 |
| edge_mesh | 8 | aiwire | 365.6 | 3967.1 | 205.5 | 411.0 | 5.2% | 155 | 38.9 | latency_window | 1.02x | 66.9% | 1.82 |
| edge_mesh | 8 | raw | 1105.3 | 1352.6 | 200.6 | 401.3 | 14.8% | 54 | 39.9 | latency_window | 1.00x | 0.0% | 1.77 |
| edge_mesh | 8 | zlib | 643.2 | 2319.2 | 203.6 | 407.2 | 8.8% | 92 | 39.3 | latency_window | 1.01x | 41.8% | 1.80 |
| edge_mesh | 64 | aitoken | 529.1 | 2811.0 | 1632.0 | 3264.0 | 58.1% | 111 | 39.2 | latency_window | 1.21x | 52.1% | 14.43 |
| edge_mesh | 64 | aitoken_aiwire | 359.1 | 4109.0 | 1638.6 | 3277.2 | 39.9% | 161 | 39.1 | latency_window | 1.21x | 67.5% | 14.49 |
| edge_mesh | 64 | aiwire | 365.6 | 3967.1 | 1643.9 | 3287.8 | 41.4% | 155 | 38.9 | latency_window | 1.22x | 66.9% | 14.54 |
| edge_mesh | 64 | raw | 1105.3 | 1352.6 | 1352.6 | 2705.3 | 100.0% | 54 | 39.9 | bandwidth | 1.00x | 0.0% | 11.96 |
| edge_mesh | 64 | zlib | 643.2 | 2319.2 | 1628.7 | 3257.5 | 70.2% | 92 | 39.3 | latency_window | 1.20x | 41.8% | 14.40 |
| lan_10m | 1 | aitoken | 529.1 | 4685.1 | 157.9 | 315.8 | 3.4% | 30 | 6.3 | latency_window | 1.06x | 52.1% | 1.40 |
| lan_10m | 1 | aitoken_aiwire | 359.1 | 6848.3 | 159.6 | 319.2 | 2.3% | 43 | 6.3 | latency_window | 1.07x | 67.5% | 1.41 |
| lan_10m | 1 | aiwire | 365.6 | 6611.8 | 162.9 | 325.9 | 2.5% | 41 | 6.1 | latency_window | 1.09x | 66.9% | 1.44 |
| lan_10m | 1 | raw | 1105.3 | 2254.4 | 149.6 | 299.2 | 6.6% | 16 | 6.7 | latency_window | 1.00x | 0.0% | 1.32 |
| lan_10m | 1 | zlib | 643.2 | 3865.3 | 157.4 | 314.9 | 4.1% | 25 | 6.4 | latency_window | 1.05x | 41.8% | 1.39 |
| lan_10m | 8 | aitoken | 529.1 | 4685.1 | 1263.0 | 2526.1 | 27.0% | 30 | 6.3 | latency_window | 1.06x | 52.1% | 11.17 |
| lan_10m | 8 | aitoken_aiwire | 359.1 | 6848.3 | 1276.7 | 2553.3 | 18.6% | 43 | 6.3 | latency_window | 1.07x | 67.5% | 11.29 |
| lan_10m | 8 | aiwire | 365.6 | 6611.8 | 1303.5 | 2607.1 | 19.7% | 41 | 6.1 | latency_window | 1.09x | 66.9% | 11.53 |
| lan_10m | 8 | raw | 1105.3 | 2254.4 | 1196.8 | 2393.7 | 53.1% | 16 | 6.7 | latency_window | 1.00x | 0.0% | 10.58 |
| lan_10m | 8 | zlib | 643.2 | 3865.3 | 1259.6 | 2519.1 | 32.6% | 25 | 6.4 | latency_window | 1.05x | 41.8% | 11.14 |
| lan_10m | 64 | aitoken | 529.1 | 4685.1 | 4685.1 | 9370.1 | 100.0% | 30 | 6.3 | bandwidth | 2.08x | 52.1% | 41.43 |
| lan_10m | 64 | aitoken_aiwire | 359.1 | 6848.3 | 5585.5 | 11170.9 | 81.6% | 43 | 6.3 | cpu | 2.48x | 67.5% | 49.39 |
| lan_10m | 64 | aiwire | 365.6 | 6611.8 | 6611.8 | 13223.6 | 100.0% | 41 | 6.1 | bandwidth | 2.93x | 66.9% | 58.47 |
| lan_10m | 64 | raw | 1105.3 | 2254.4 | 2254.4 | 4508.8 | 100.0% | 16 | 6.7 | bandwidth | 1.00x | 0.0% | 19.93 |
| lan_10m | 64 | zlib | 643.2 | 3865.3 | 3865.3 | 7730.6 | 100.0% | 25 | 6.4 | bandwidth | 1.71x | 41.8% | 34.18 |
| lte_good | 1 | aitoken | 529.1 | 4765.9 | 12.8 | 25.7 | 0.3% | 372 | 78.0 | latency_window | 1.00x | 52.1% | 0.11 |
| lte_good | 1 | aitoken_aiwire | 359.1 | 6848.3 | 12.8 | 25.7 | 0.2% | 534 | 78.0 | latency_window | 1.00x | 67.5% | 0.11 |
| lte_good | 1 | aiwire | 365.6 | 6611.8 | 12.8 | 25.7 | 0.2% | 515 | 77.8 | latency_window | 1.00x | 66.9% | 0.11 |
| lte_good | 1 | raw | 1105.3 | 2269.2 | 12.8 | 25.6 | 0.6% | 178 | 78.1 | latency_window | 1.00x | 0.0% | 0.11 |
| lte_good | 1 | zlib | 643.2 | 3909.0 | 12.8 | 25.7 | 0.3% | 305 | 77.9 | latency_window | 1.00x | 41.8% | 0.11 |
| lte_good | 8 | aitoken | 529.1 | 4765.9 | 102.6 | 205.2 | 2.2% | 372 | 78.0 | latency_window | 1.00x | 52.1% | 0.91 |
| lte_good | 8 | aitoken_aiwire | 359.1 | 6848.3 | 102.6 | 205.3 | 1.5% | 534 | 78.0 | latency_window | 1.00x | 67.5% | 0.91 |
| lte_good | 8 | aiwire | 365.6 | 6611.8 | 102.8 | 205.6 | 1.6% | 515 | 77.8 | latency_window | 1.00x | 66.9% | 0.91 |
| lte_good | 8 | raw | 1105.3 | 2269.2 | 102.4 | 204.8 | 4.5% | 178 | 78.1 | latency_window | 1.00x | 0.0% | 0.91 |
| lte_good | 8 | zlib | 643.2 | 3909.0 | 102.6 | 205.3 | 2.6% | 305 | 77.9 | latency_window | 1.00x | 41.8% | 0.91 |
| lte_good | 64 | aitoken | 529.1 | 4765.9 | 820.9 | 1641.8 | 17.2% | 372 | 78.0 | latency_window | 1.00x | 52.1% | 7.26 |
| lte_good | 64 | aitoken_aiwire | 359.1 | 6848.3 | 821.0 | 1642.0 | 12.0% | 534 | 78.0 | latency_window | 1.00x | 67.5% | 7.26 |
| lte_good | 64 | aiwire | 365.6 | 6611.8 | 822.4 | 1644.7 | 12.4% | 515 | 77.8 | latency_window | 1.00x | 66.9% | 7.27 |
| lte_good | 64 | raw | 1105.3 | 2269.2 | 819.2 | 1638.3 | 36.1% | 178 | 78.1 | latency_window | 1.00x | 0.0% | 7.24 |
| lte_good | 64 | zlib | 643.2 | 3909.0 | 821.1 | 1642.2 | 21.0% | 305 | 77.9 | latency_window | 1.00x | 41.8% | 7.26 |
| wifi_busy | 1 | aitoken | 529.1 | 5719.1 | 32.3 | 64.7 | 0.6% | 177 | 30.9 | latency_window | 1.00x | 52.1% | 0.29 |
| wifi_busy | 1 | aitoken_aiwire | 359.1 | 8217.9 | 32.3 | 64.7 | 0.4% | 255 | 30.9 | latency_window | 1.00x | 67.5% | 0.29 |
| wifi_busy | 1 | aiwire | 365.6 | 7934.2 | 32.5 | 64.9 | 0.4% | 245 | 30.8 | latency_window | 1.01x | 66.9% | 0.29 |
| wifi_busy | 1 | raw | 1105.3 | 2723.0 | 32.2 | 64.4 | 1.2% | 85 | 31.1 | latency_window | 1.00x | 0.0% | 0.28 |
| wifi_busy | 1 | zlib | 643.2 | 4690.8 | 32.4 | 64.7 | 0.7% | 145 | 30.9 | latency_window | 1.01x | 41.8% | 0.29 |
| wifi_busy | 8 | aitoken | 529.1 | 5719.1 | 258.6 | 517.2 | 4.5% | 177 | 30.9 | latency_window | 1.00x | 52.1% | 2.29 |
| wifi_busy | 8 | aitoken_aiwire | 359.1 | 8217.9 | 258.6 | 517.3 | 3.1% | 255 | 30.9 | latency_window | 1.00x | 67.5% | 2.29 |
| wifi_busy | 8 | aiwire | 365.6 | 7934.2 | 259.7 | 519.4 | 3.3% | 245 | 30.8 | latency_window | 1.01x | 66.9% | 2.30 |
| wifi_busy | 8 | raw | 1105.3 | 2723.0 | 257.5 | 515.0 | 9.5% | 85 | 31.1 | latency_window | 1.00x | 0.0% | 2.28 |
| wifi_busy | 8 | zlib | 643.2 | 4690.8 | 258.8 | 517.7 | 5.5% | 145 | 30.9 | latency_window | 1.01x | 41.8% | 2.29 |
| wifi_busy | 64 | aitoken | 529.1 | 5719.1 | 2069.0 | 4138.0 | 36.2% | 177 | 30.9 | latency_window | 1.00x | 52.1% | 18.30 |
| wifi_busy | 64 | aitoken_aiwire | 359.1 | 8217.9 | 2069.0 | 4138.1 | 25.2% | 255 | 30.9 | latency_window | 1.00x | 67.5% | 18.30 |
| wifi_busy | 64 | aiwire | 365.6 | 7934.2 | 2077.8 | 4155.6 | 26.2% | 245 | 30.8 | latency_window | 1.01x | 66.9% | 18.37 |
| wifi_busy | 64 | raw | 1105.3 | 2723.0 | 2060.1 | 4120.3 | 75.7% | 85 | 31.1 | latency_window | 1.00x | 0.0% | 18.22 |
| wifi_busy | 64 | zlib | 643.2 | 4690.8 | 2070.7 | 4141.4 | 44.1% | 145 | 30.9 | latency_window | 1.01x | 41.8% | 18.31 |

Readout:

- `B/ex` is framed hot-path bytes per request/response exchange.
- `BW ex/s` is the pure bandwidth capacity for that profile.
- `Eff ex/s` is capped by bandwidth, p95 latency window, and measured codec CPU.
- `Need agents` is `ceil(BW ex/s * projected_p95_seconds / per_agent_window)`.
- `Raw Mbps equiv` is the bandwidth raw JSON would need to carry the same effective semantic exchange rate.

