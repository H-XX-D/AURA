# AIWire Dictionary Comparison Matrix

This report compares the pinned AIWire v1 static dictionary with corpus-derived candidate dictionaries. Generated dictionaries are measurement artifacts only; using one in a deployed peer would require a new compatibility-manifest hash.

## Run Shape

- Fixture corpus: `fixtures/aiwire_sessions/public_session_corpus_v1.json`
- Sessions: `2`
- Messages: `72`
- zlib level: `3`
- Max entries per generated dictionary: `128`
- Max dictionary bytes: `32768`

## Dictionary Matrix

| Dictionary | Kind | Scope | Bytes | SHA-256 | FNV-1a64 | Manifest status |
|---|---|---|---:|---|---|---|
| no_dictionary | zlib_no_dictionary | all | 0 | `none` | `none` | fallback_baseline |
| aiwire_v1_static | current_static | all | 32,768 | `f5c9d524606a4cec9c397cb7ae177a8e1ec87f9819c749f6fd0b24a155313117` | `94dd21718372952e` | current_compatible |
| generated_combined | generated_combined | all | 4,490 | `d6c1419617ab913f027f9f339e95a676663d7d9367cdf5e43f67b846a3570927` | `dc26a5130d6aa1be` | candidate_only |
| generated_a2a | generated_protocol_specific | a2a | 2,004 | `2bcf9d5dc17adfe13b85017a53b78f98d3a750bdd3d0a31565937fec617ec7a4` | `80e537e261f67d65` | candidate_only |
| generated_agent_final | generated_protocol_specific | agent.final | 564 | `22af10191f151210e14e905ba38568701d462a7640757e137af3f03ef915b12a` | `15ea6d03cfa60e53` | candidate_only |
| generated_agent_handoff | generated_protocol_specific | agent.handoff | 338 | `2f73338ce85ffd74c3255900cd275ed438782c785d82fe5b2caea59bb12c3b85` | `71350bc73c36713e` | candidate_only |
| generated_agent_review | generated_protocol_specific | agent.review | 476 | `bf2ecc1b6629d87bba9cc9ace888143ef527d8be0f5f90eb7c4d05924bfea505` | `5842e4c630a12625` | candidate_only |
| generated_agent_trace | generated_protocol_specific | agent.trace | 350 | `0404cff8ab756767e821d7cf9f6e04c14be37ad7736eecbd5faa1b6a892f637e` | `16c943f04ae5e26e` | candidate_only |
| generated_local_agent | generated_protocol_specific | local.agent | 1,954 | `2817ee3cc498f5a504cb846e36cc78ac4062f27ef9bfdd2bfba4f744f1aa7e78` | `4459051cb442e05f` | candidate_only |
| generated_mcp | generated_protocol_specific | mcp | 2,698 | `7d19e67900a0bfc487c6c6ead9ab3ea7d9497fc8a88f65503cc1de2f319dda83` | `d7d82bf1477acc5b` | candidate_only |
| generated_memory_write | generated_protocol_specific | memory.write | 401 | `3da6f35c5aed12522d76e2714dc6b6022b34a3694b73de34619d4edcdbfb85ad` | `b3f3f4d2d3d1c779` | candidate_only |
| generated_openai_responses | generated_protocol_specific | openai.responses | 2,925 | `a74392e7ad82b2111f9f6a1b35730f255c099a3112385301eadfab187d956a0e` | `f9209a72f326ac3e` | candidate_only |

## All-Message Measurements

| Dictionary | Raw B | Wire B | B/frame | Ratio | Saved | Verified |
|---|---:|---:|---:|---:|---:|---|
| no_dictionary | 39,504 | 7,081 | 98.3 | 5.58x | 82.1% | `True` |
| aiwire_v1_static | 39,504 | 6,535 | 90.8 | 6.04x | 83.5% | `True` |
| generated_combined | 39,504 | 5,853 | 81.3 | 6.75x | 85.2% | `True` |

## Protocol-Scope Measurements

| Dictionary | Message scope | Frames | Wire B | B/frame | Ratio | Saved |
|---|---|---:|---:|---:|---:|---:|
| aiwire_v1_static | a2a | 12 | 1,036 | 86.3 | 5.59x | 82.1% |
| aiwire_v1_static | agent.final | 2 | 276 | 138.0 | 3.68x | 72.9% |
| aiwire_v1_static | agent.handoff | 2 | 324 | 162.0 | 3.72x | 73.1% |
| aiwire_v1_static | agent.review | 2 | 356 | 178.0 | 3.67x | 72.7% |
| aiwire_v1_static | agent.trace | 2 | 292 | 146.0 | 3.43x | 70.9% |
| aiwire_v1_static | local.agent | 10 | 910 | 91.0 | 4.82x | 79.3% |
| aiwire_v1_static | mcp | 16 | 1,372 | 85.8 | 7.70x | 87.0% |
| aiwire_v1_static | memory.write | 2 | 277 | 138.5 | 3.27x | 69.4% |
| aiwire_v1_static | openai.responses | 24 | 1,822 | 75.9 | 7.32x | 86.3% |
| generated_combined | a2a | 12 | 882 | 73.5 | 6.56x | 84.8% |
| generated_combined | agent.final | 2 | 188 | 94.0 | 5.41x | 81.5% |
| generated_combined | agent.handoff | 2 | 290 | 145.0 | 4.16x | 75.9% |
| generated_combined | agent.review | 2 | 286 | 143.0 | 4.57x | 78.1% |
| generated_combined | agent.trace | 2 | 231 | 115.5 | 4.34x | 77.0% |
| generated_combined | local.agent | 10 | 875 | 87.5 | 5.01x | 80.1% |
| generated_combined | mcp | 16 | 1,111 | 69.4 | 9.51x | 89.5% |
| generated_combined | memory.write | 2 | 171 | 85.5 | 5.30x | 81.1% |
| generated_combined | openai.responses | 24 | 1,442 | 60.1 | 9.24x | 89.2% |
| generated_a2a | a2a | 12 | 665 | 55.4 | 8.71x | 88.5% |
| generated_agent_final | agent.final | 2 | 145 | 72.5 | 7.01x | 85.7% |
| generated_agent_handoff | agent.handoff | 2 | 302 | 151.0 | 3.99x | 74.9% |
| generated_agent_review | agent.review | 2 | 258 | 129.0 | 5.06x | 80.2% |
| generated_agent_trace | agent.trace | 2 | 231 | 115.5 | 4.34x | 77.0% |
| generated_local_agent | local.agent | 10 | 589 | 58.9 | 7.45x | 86.6% |
| generated_mcp | mcp | 16 | 882 | 55.1 | 11.97x | 91.6% |
| generated_memory_write | memory.write | 2 | 161 | 80.5 | 5.63x | 82.2% |
| generated_openai_responses | openai.responses | 24 | 1,357 | 56.5 | 9.82x | 89.8% |
