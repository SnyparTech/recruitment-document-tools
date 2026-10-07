# LLM Model Comparison — GPT-4.1 mini vs GPT-5 mini (researched October 2026)

Scoped to this project's actual LLM call sites, and narrowed to these two
models per request. There are exactly two real LLM call sites in this
codebase:

- **Candidate search (JD → SearchPlan)** — `RequirementAgent`,
  `backend/app/agents/requirement_agent.py`. JD text in, Resdex search
  criteria out (keywords, experience range, location, etc), under hard
  constraints (max 8 required keywords, max 12 preferred, valid
  `resdex_schema.json` enums).
- **Resume structuring** — `GroqResumeAIProvider`,
  `backend/app/services/ai_providers.py`, used by `resume_converter.py`.
  Raw extracted resume text in, structured sections out.

(Dossier compiling and WhatsApp message drafting don't call an LLM at all —
see those services' own docstrings — so they're out of scope here.)

**Sourcing note:** pricing and benchmark numbers below are from OpenRouter's
per-model pricing/benchmark pages and cross-referenced third-party trackers,
not training-data memory — model names and prices in this market move past
any fixed knowledge cutoff.

---

## Pricing

| Model | Input (per 1M tokens) | Output (per 1M tokens) |
|---|---|---|
| GPT-4.1 mini | $0.40 | $1.60 |
| GPT-5 mini | $0.25 | $2.00 |

## Instruction-following (ability to obey hard constraints, e.g. "max 8 required keywords")

| Model | Benchmark | Score |
|---|---|---|
| GPT-4.1 mini | IFEval | 84.1% |
| GPT-5 mini | IFBench | 71–75% (varies by reasoning intensity) |

Different test suites, different scoring — not a precise apples-to-apples
ranking, but both are instruction-adherence benchmarks, and GPT-4.1 mini's
result is the stronger of the two on the evidence available.

---

## Cost estimate for this project's actual workload

Assumptions: a candidate-search call is ~1,500 input tokens (JD text + system
prompt) / ~500 output tokens (SearchPlan JSON); a resume-structuring call is
~3,000 input / ~1,500 output tokens. Volume: 200 candidate-search calls +
200 resume-structuring calls per month.

| | GPT-4.1 mini | GPT-5 mini |
|---|---|---|
| Cost per candidate-search call | $0.0014 | $0.0014 |
| Cost per resume-structuring call | $0.0036 | $0.0038 |
| ~200+200 calls/month total | **$1.00** | **$1.03** |

Cost is a wash — 3 cents/month apart, noise at this volume. GPT-5 mini's
cheaper input rate roughly cancels against its pricier output rate given
this project's input-heavy token mix on both call types.

---

## Recommendation

Since cost doesn't differentiate them, pick on instruction-following:
**GPT-4.1 mini** — 84.1% IFEval is the stronger signal available, at
effectively identical cost (~$1/month) to GPT-5 mini. Either is a reasonable
choice if the provider has to be OpenAI; GPT-4.1 mini is the slight edge.

---

## Sources

- [GPT-4.1 Mini — API Pricing & Benchmarks (OpenRouter)](https://openrouter.ai/openai/gpt-4.1-mini)
- [GPT-5 Mini — API Pricing & Benchmarks (OpenRouter)](https://openrouter.ai/openai/gpt-5-mini)
- [GPT-4.1 mini vs GPT-5.4 nano: Benchmarks & Cost — BenchLM](https://benchlm.ai/compare/gpt-4-1-mini-vs-gpt-5-4-nano)
