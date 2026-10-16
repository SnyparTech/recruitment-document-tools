# LLM Model Comparison (researched October 2026)

Compares the **5 models actually configured in this project's provider chain** right now (`backend/.env`, see `RequirementAgent._provider_chain()` in `backend/app/agents/requirement_agent.py` and the equivalent in `backend/app/services/ai_providers.py`), on the 4 dimensions requested: **accuracy, cost, context length, input/output token limits**.

| Env var | Model actually configured |
|---|---|
| `OPENAI_MODEL` | `gpt-4.1-mini` |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` |
| `GROQ_MODEL` | `openai/gpt-oss-120b` |
| `NVIDIA_MODEL` | `meta/llama-3.2-11b-vision-instruct` |
| `OPENROUTER_MODEL` | `stealth/space-bunny-alpha` |

**Sourcing**: every number below comes from a live web search performed for this document, not from memory — this market moves too fast for a fixed training cutoff to be trusted. Each figure is cited. Where two credible sources disagreed, both are shown rather than picking one silently.

---

## 1. Pricing (USD per 1M tokens)

| Model | Input | Output | Cached input | Notes |
|---|---|---|---|---|
| **gpt-4.1-mini** (OpenAI) | $0.40 | $1.60 | $0.10 | |
| **gemini-3.5-flash-lite** (Google) | $0.30 | $2.50 | read $0.03 / write $0.08333 | |
| **gpt-oss-120b** (Groq) | $0.15 | $0.60 | $0.075 | |
| **llama-3.2-11b-vision-instruct** (NVIDIA NIM) | Free via build.nvidia.com's developer tier (current access path used by this project) | — | — | A third-party tracker quotes ~$0.34/1M blended for paid NIM access outside the free developer tier — NVIDIA does not publish this as transparently as OpenAI/Google |
| **stealth/space-bunny-alpha** (OpenRouter) | $0 | $0 | — | Free during OpenRouter's "stealth preview" period (since Sept 23, 2026); past stealth models have turned paid once their maker was publicly named — **do not treat $0 as permanent** |

## 2. Context window & output limits (tokens)

| Model | Context window | Max output tokens |
|---|---|---|
| gpt-4.1-mini | 1,047,576 | 32,768 |
| gemini-3.5-flash-lite | 1,048,576 | 65,536 |
| gpt-oss-120b | 131,072 | ~33,000 |
| llama-3.2-11b-vision-instruct | 131,072 | not separately published |
| stealth/space-bunny-alpha | 1,000,000 | not separately published |

Every model here comfortably exceeds this project's actual per-call token usage (a JD-extraction call is ~1,500 input / ~500 output tokens; a resume-structuring call is ~3,000 input / ~1,500 output) — none of these limits are a real constraint for this workload.

## 3. Accuracy (Artificial Analysis Intelligence Index — composite reasoning/knowledge/math/coding benchmark)

| Model | Intelligence Index score | Source note |
|---|---|---|
| gemini-3.5-flash-lite | **36** (per Artificial Analysis's own Oct 2026 announcement: "+11 points over Gemini 3.1 Flash-Lite's 25") — one separate model-card page shows **22** instead | Two sources disagree; the 36 figure is the more specific, directly-attributed one (Artificial Analysis's own account), the 22 may be a stale/cached page |
| gpt-oss-120b | 23.8 | artificialanalysis.ai comparison page |
| gpt-4.1-mini | 14.8 | artificialanalysis.ai comparison page |
| llama-3.2-11b-vision-instruct | 5 (also: MMLU 73.0 macro-avg 0-shot) | artificialanalysis.ai model page; MMLU from benchmarklist.com |
| stealth/space-bunny-alpha | **Not available** | The model's real identity/maker is undisclosed by design ("stealth preview") — no independent benchmark can exist until it's unmasked |

**Reading this table**: on this specific composite benchmark, Gemini 3.5 Flash-Lite currently scores highest of the four benchmarkable models, gpt-oss-120b second, gpt-4.1-mini third, and the small 11B vision model lowest (expected — it's the smallest parameter count by far and primarily a vision-capable model, not optimized for pure text reasoning benchmarks).

## 4. What this means for this project's two LLM call sites

Both real call sites (candidate-search JD extraction, resume structuring — see `docs/TECHNICAL_DOCUMENTATION_v2.md` §6) are structured-JSON-extraction tasks with hard constraints (keyword caps, enum validation against `resdex_schema.json`), where **instruction-following reliability matters more than raw reasoning benchmark score**. The Intelligence Index measures general reasoning/knowledge/math/coding — it does not directly measure "will this model respect a hard cap of 8 required keywords," which is the actual failure mode this project has hit repeatedly (keyword floods, hallucinated `active_in` values, non-atomic keyword phrases).

None of the 5 models above have a published, directly-comparable instruction-following-specific score in the same benchmark family, so the Intelligence Index numbers should be read as a general capability signal, not a guarantee of constraint-following behavior — that's still why this project keeps deterministic post-processing (`_normalize_keywords`, `_post_process_plan`) as a safety net regardless of which provider answers.

## 5. Practical notes specific to this project

- **Provider order is currently Gemini-first for testing** (see `_provider_chain()`'s docstring in `requirement_agent.py`) — the documented long-term default is OpenAI first, chosen for the accuracy/cost balance described above.
- **NVIDIA's free-tier access is the reason it's in the chain at all** — at real paid NIM pricing it would not obviously beat OpenAI or Gemini on cost-per-accuracy; it's included as a genuinely free fallback.
- **OpenRouter's stealth model carries real risk**: $0 pricing and unknown accuracy both can change the moment the provider is unmasked, with no warning. Treat it as a free trial-period fallback, not a model to depend on long-term.
- A recruiter can force any one specific provider via the chat UI's model picker (`GET /search/providers`) — useful for directly comparing output quality on a real JD, since the "model used" label is shown under every reply.

## Sources

- [GPT-4.1 Mini Model — OpenAI developer docs](https://developers.openai.com/api/docs/models/gpt-4.1-mini)
- [GPT-4.1 mini API Pricing 2026 — APIpulse](https://www.getapipulse.com/blog-gpt41-mini-pricing.html)
- [Gemini 3.5 Flash Lite — OpenRouter](https://openrouter.ai/google/gemini-3.5-flash-lite)
- [Gemini 3.5 Flash-Lite — Artificial Analysis model page](https://artificialanalysis.ai/models/gemini-3-5-flash-lite)
- [Artificial Analysis on X — Gemini 3.6 Flash / 3.5 Flash-Lite benchmark announcement](https://x.com/ArtificialAnlys/status/2079596244339707956)
- [gpt-oss-120b — Requesty pricing/context page](https://www.requesty.ai/models/groq/openai-gpt-oss-120b)
- [gpt-oss-120b — OpenRouter](https://openrouter.ai/openai/gpt-oss-120b)
- [Gemini 3.1 Flash-Lite vs gpt-oss-120b / vs GPT-4.1 mini — Artificial Analysis comparisons](https://artificialanalysis.ai/models/comparisons/gemini-3-1-flash-lite-preview-vs-gpt-4-1-mini)
- [Llama 3.2 11B (Vision) — Artificial Analysis model page](https://artificialanalysis.ai/models/llama-3-2-instruct-11b-vision)
- [Llama 3.2 11B Vision Instruct — benchmarklist.com](https://benchmarklist.com/models/meta-llama-llama-3.2-11b-vision-instruct/)
- [llama-3.2-11b-vision-instruct — NVIDIA build.nvidia.com model card](https://build.nvidia.com/meta/llama-3.2-11b-vision-instruct/modelcard)
- [Llama 3.2 11B Vision Instruct API Pricing — pricepertoken.com](https://pricepertoken.com/pricing-page/model/meta-llama-llama-3.2-11b-vision-instruct)
- [Space Bunny Alpha — OpenRouter](https://openrouter.ai/stealth/space-bunny-alpha)
- [Space Bunny Alpha: The Stealth Model and the MiniMax Clues](https://cellcog.ai/blog/what-is-space-bunny-alpha/)
