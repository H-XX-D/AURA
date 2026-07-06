# AIWire Native Asyncio Network Suite: 2026-07-06

Local Mac loopback run using `tools/run_aiwire_network_suite.py` with
`--backend native`, `--coordinator asyncio`, public fixture replay, updated
session templates, `cluster` fixture variation, 64 logical agents, and 5
seconds per codec/profile. The raw JSON was captured at
`/tmp/aura_aiwire_native_asyncio_network_suite_2026-07-06.json` during the run;
this Markdown file is the committed audit summary.

These metrics treat each request/response pair as a semantic exchange. Framed bytes include TCP frame length prefixes, so the table reflects bytes the link actually has to carry for this harness.

| Profile | Codec | Backend | Completed | Ex/s | Framed B/ex | BW cap ex/s | BW gain | Obs/BW cap | Saved | p95 ms | Codec CPU us/ex | Link Mbps |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| lan_10m | raw | raw | 5399 | 1079.8 | 2311.6 | 1080.0 | 1.00x | 100.0% | -0.3% | 950.6 | 1.3 | 19.96 |
| lan_10m | zlib | zlib | 10249 | 2049.8 | 1216.5 | 2051.0 | 1.90x | 99.9% | 47.2% | 501.1 | 70.1 | 19.94 |
| lan_10m | aiwire | native | 33677 | 6735.4 | 366.8 | 6739.1 | 6.24x | 99.9% | 84.1% | 153.3 | 52.5 | 19.76 |
| lan_10m | aitoken_aiwire | aitoken+native | 47099 | 9419.8 | 108.4 | 22999.0 | 21.30x | 41.0% | 95.3% | 114.7 | 90.3 | 8.18 |
| wifi_busy | raw | raw | 6402 | 1280.4 | 2328.7 | 1290.0 | 1.00x | 99.3% | -0.3% | 3260.3 | 0.9 | 23.57 |
| wifi_busy | zlib | zlib | 11970 | 2394.0 | 1220.8 | 2460.5 | 1.91x | 97.3% | 47.4% | 1732.8 | 63.5 | 23.55 |
| wifi_busy | aiwire | native | 39884 | 7976.8 | 368.6 | 8231.8 | 6.38x | 96.9% | 84.1% | 536.8 | 56.0 | 23.59 |
| wifi_busy | aitoken_aiwire | aitoken+native | 47546 | 9509.2 | 108.4 | 27599.1 | 21.39x | 34.5% | 95.3% | 435.4 | 82.6 | 8.31 |
| lte_good | raw | raw | 5211 | 1042.2 | 2329.1 | 1074.8 | 1.00x | 97.0% | -0.3% | 5779.0 | 1.0 | 19.83 |
| lte_good | zlib | zlib | 9893 | 1978.6 | 1223.8 | 2046.7 | 1.90x | 96.7% | 47.3% | 3061.1 | 67.3 | 19.34 |
| lte_good | aiwire | native | 32915 | 6583.0 | 369.7 | 6879.1 | 6.40x | 95.7% | 84.1% | 929.5 | 52.5 | 19.46 |
| lte_good | aitoken_aiwire | aitoken+native | 44664 | 8932.8 | 108.4 | 23007.3 | 21.41x | 38.8% | 95.3% | 731.9 | 83.8 | 7.84 |
| edge_mesh | raw | raw | 3082 | 616.4 | 2327.1 | 643.7 | 1.00x | 95.8% | -0.3% | 4876.1 | 1.2 | 11.81 |
| edge_mesh | zlib | zlib | 5894 | 1178.8 | 1218.8 | 1228.9 | 1.91x | 95.9% | 47.5% | 2613.6 | 73.0 | 11.70 |
| edge_mesh | aiwire | native | 19425 | 3885.0 | 369.9 | 3985.4 | 6.19x | 97.5% | 84.1% | 821.2 | 48.0 | 11.56 |
| edge_mesh | aitoken_aiwire | aitoken+native | 46125 | 9225.0 | 108.5 | 13792.9 | 21.43x | 66.9% | 95.3% | 413.2 | 83.6 | 7.98 |

## Readout

- Best bandwidth reduction: `aitoken_aiwire` (95.3% framed bytes saved).
- Highest bandwidth-proportional capacity: `aitoken_aiwire` (27599.1 ex/s).
- Highest completed exchange rate: `aitoken_aiwire` (9509.2 ex/s).
- Lowest p95 roundtrip: `aitoken_aiwire` (114.7 ms).
- Lowest non-raw codec CPU: `aiwire` (48.0 us/ex).

For AI-to-AI messaging, the useful result is not just compression ratio. Bandwidth-proportional capacity is the exchange rate predicted from link bytes per second divided by framed bytes per exchange. A codec wins when it can turn that extra capacity into verified semantic exchanges without letting p95/p99 latency or codec CPU become the next bottleneck.
