# A1-N Qwen3.6-27B alignment matrix (2026-09-30)

| Item | RPent documented reference | Active A1-N implementation | Evidence |
|---|---|---|---|
| model | Qwen3.6-27B | Qwen3.6-27B-FP8 revision `e89b16ebf1988b3d6befa7de50abc2d76f26eb09` | service `alignment_config.json`, model manifest |
| backend | vLLM example | SGLang (vLLM absent in dedicated node01 runtime) | job 2721 `sglang.log` |
| tool choice | `--enable-auto-tool-choice` + `--tool-call-parser qwen3_coder` | SGLang equivalent `--tool-call-parser qwen3_coder`; gateway forwards guided regex | service command and `m2_api.py` |
| reasoning | `--reasoning-parser qwen3` | `--reasoning-parser qwen3`, gateway blocks thinking tokens and sends `enable_thinking=false` | service command, `/health` |
| chat template | server auto template | SGLang reports default HuggingFace chat template for OpenAI content | job 2721 log |
| context | official example `--max-model-len 262144` | 49152 context/max-total-tokens, the largest verified one-GPU allocation; old 32768 overflowed input + 8192 completion | job 2721 KV allocation and old 2707 logs |
| sampling | model generation defaults | temperature 1.0, top_k 20, top_p 0.95; no extra continuation/retry | job 2721 log and request transcripts |
| memory | benchmark no-memory condition is required | local profile with only zero-byte `MEMORY.md`; no memory files or model output injected | A1 manifest and output tree |
| prompt boundary | official RPent prompt | current RPent prompt still tells the agent to inspect/read memory paths; with zero-byte local memory, smoke showed directory probing | job 2730 `cli.log` |

The last row is an unresolved protocol alignment item. It is recorded rather than hidden: job 2730 is a valid parser/runtime smoke, but its task result remains separate from any official Qwen leaderboard claim until the official no-memory prompt/profile is confirmed. No “continue” sentence or parser retry was added.
