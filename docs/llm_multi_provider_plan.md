# LLM Multi-Provider Integration Plan

## Goal

Build a gradual path from the current OpenAI-only agent runtime to a multi-provider LLM architecture that supports:

- OpenAI models
- third-party OpenAI-compatible providers such as MiniMax
- agent-level provider and model selection
- optional routing strategy and fallback behavior

The first milestone is to get MiniMax working end-to-end in the existing `openai-agents` based framework with the smallest safe set of changes.


## Current State

The current backend agent runtime has these properties:

- Agent definitions live in `backend/agent_configs/config/*.yaml`
- `backend/app/core/llm/agent_loader.py` loads YAML and builds `Agent(...)`
- `backend/app/core/llm/gateway.py` executes agents through `Runner.run(...)`
- configuration is centered around `OPENAI_API_KEY` and `OPENAI_API_BASE`
- agent YAML currently declares `model`, but not provider, routing, or fallback metadata

This is a good base for gradual expansion because business tasks already depend on `AgentGateway` instead of directly calling provider SDKs.


## Design Principles

1. Keep business workflows unchanged

- Modules such as job analysis, resume tailoring, and cover letter generation should continue to call `AgentGateway.get().call(...)`
- Provider selection should be solved inside the LLM infrastructure layer, not in task code

2. Maintain backward compatibility

- Existing YAML agents without provider metadata must continue to work
- OpenAI should remain the default provider until explicitly overridden

3. Add capabilities in layers

- provider access first
- agent-level model/provider configuration second
- routing and fallback third

4. Optimize for safe rollout

- first validate one low-risk agent on MiniMax
- then validate structured output stability
- only then extend to more agents or introduce fallback logic

5. Treat structured output as a first-class risk

- this project relies heavily on Pydantic structured outputs
- some OpenAI-compatible providers support chat completion endpoints but are less reliable with JSON-schema style structured outputs
- each new provider must be validated against the actual schemas used in this codebase


## Target Architecture

The target design introduces three levels of decision-making:

### 1. Provider Layer

The runtime knows how to create and use multiple providers, for example:

- `openai`
- `minimax`
- future providers such as OpenRouter-compatible routes or other OpenAI-compatible backends

Each provider definition includes:

- API key source
- base URL
- API mode (`responses` or `chat_completions`)
- tracing compatibility
- known capability flags

### 2. Agent Configuration Layer

Each agent can declare which provider and model it should use.

Example target YAML shape:

```yaml
provider: minimax
model: MiniMax-M2.5
```

Backward-compatible agents may omit `provider`, in which case the default provider is used.

### 3. Strategy Layer

Some agents may later need selection logic or fallback behavior.

Example target YAML shape:

```yaml
provider: minimax
model: MiniMax-M2.5
fallbacks:
  - provider: openai
    model: gpt-5-mini
strategy:
  type: primary_with_fallback
```

This layer should be introduced only after provider execution is stable.


## Phase Plan

## Phase 0 - Planning and Compatibility Validation

### Objective

Confirm the exact integration boundaries of `openai-agents` with OpenAI-compatible providers such as MiniMax.

### Scope

- verify MiniMax endpoint details
- verify which API mode is required
- verify whether structured outputs are stable enough for current schemas
- define the initial provider configuration contract

### Expected Output

- this implementation plan document
- a concrete provider config design
- a decision to start with one pilot agent

### Exit Criteria

- MiniMax connection approach is documented
- first pilot agent is selected


## Phase 1 - Provider Infrastructure

### Objective

Make the runtime capable of sending agent requests to either OpenAI or MiniMax without changing business task code.

### Scope

Add provider-aware configuration to backend settings.

Recommended new settings:

- `DEFAULT_LLM_PROVIDER`
- `OPENAI_API_KEY`
- `OPENAI_API_BASE`
- `MINIMAX_API_KEY`
- `MINIMAX_API_BASE`
- optional provider-specific tracing flags

Add a provider abstraction in the LLM infrastructure layer.

Recommended new module:

- `backend/app/core/llm/providers.py`

Responsibilities:

- resolve provider config
- create provider-specific `AsyncOpenAI` client
- define which API mode should be used per provider
- expose capability metadata if needed later

### Implementation Direction

For MiniMax:

- use OpenAI-compatible base URL
- create an `AsyncOpenAI(base_url=..., api_key=...)` client
- force `chat_completions` mode for the Agents SDK
- disable tracing initially if tracing depends on OpenAI-native credentials

### Non-Goals

- no agent-level fallback yet
- no strategy engine yet
- no business-task modifications

### Exit Criteria

- runtime can instantiate a MiniMax-backed client
- one agent can be routed to MiniMax without touching task logic


## Phase 2 - Agent-Level Provider and Model Configuration

### Objective

Allow each agent YAML to choose its provider and model explicitly.

### Scope

Extend agent YAML format with optional fields:

```yaml
provider: openai | minimax
model: <provider-specific model name>
```

Update `backend/app/core/llm/agent_loader.py` to:

- parse `provider`
- keep old configs valid when `provider` is absent
- attach provider metadata to the in-memory agent object

Possible runtime metadata attached to the agent:

- `agent.provider`
- `agent.agent_id`
- `agent.config_version`
- `agent.max_turns`

### Rollout Approach

Start with one low-risk agent, recommended:

- `job_analyzer`

Reason:

- output is intermediate analysis data rather than final user-facing prose
- lower user-visible quality risk if provider behavior differs slightly
- good fit for structured output validation because it exercises a non-trivial schema
- easier to compare provider behavior with fixtures and regression-style tests

### Exit Criteria

- at least one YAML agent uses `provider: minimax`
- execution succeeds through existing `AgentGateway`


## Phase 3 - Structured Output Validation

### Objective

Validate that MiniMax can reliably return structured outputs for the schemas actually used by this project.

### Scope

Test at least these schema patterns:

- simple single-field content schema
- medium-complexity analysis schema with lists and nested objects

Recommended validation order:

1. `CoverLetterDraft`
2. `TranslatedText`
3. `MatchAnalysis`
4. `AnalyzedJob` / `AnalyzedResume`

### Risks

- provider may not fully support JSON-schema structured outputs
- provider may produce valid JSON but not schema-tight JSON
- provider may require prompt adjustments for higher consistency

### Mitigation

- start with the smallest schema
- if needed, downgrade some provider integrations from strict schema mode to prompt-disciplined JSON parsing later
- keep OpenAI available as the stable reference path

### Exit Criteria

- MiniMax is proven stable for at least one production-relevant schema
- limitations are documented before broader rollout


## Phase 4 - Fallback Support

### Objective

Add deterministic fallback from a primary provider/model to a secondary provider/model.

### Scope

Extend YAML with fallback metadata:

```yaml
provider: minimax
model: MiniMax-M2.5
fallbacks:
  - provider: openai
    model: gpt-5-mini
```

Update `AgentGateway` to:

- classify retryable vs non-retryable failures
- retry only on safe categories such as timeout, rate limit, transient provider error, or malformed output when retry policy allows it
- preserve observability for both primary and fallback attempts

### Important Rules

- never fallback silently without logging
- record which provider/model actually served the result
- do not fallback on prompt/schema bugs that should fail fast

### Exit Criteria

- one agent can run on MiniMax first and fallback to OpenAI when appropriate
- AI call logs distinguish primary and fallback attempts


## Phase 5 - Agent Selection Strategy

### Objective

Support per-agent provider selection policy, not just static provider assignment.

### Scope

Potential strategy types:

- `fixed`
- `primary_with_fallback`
- `cost_optimized`
- `quality_first`
- `latency_first`

Example future YAML:

```yaml
strategy:
  type: primary_with_fallback
provider: minimax
model: MiniMax-M2.5
fallbacks:
  - provider: openai
    model: gpt-5-mini
```

### Recommended Constraint

Do not implement dynamic multi-provider routing until:

- provider execution is stable
- structured output behavior is understood
- fallback logging is mature

### Exit Criteria

- selection policy is declarative in YAML
- gateway resolves provider choice without leaking logic into task modules


## Proposed Configuration Design

## Backend Settings

Recommended additions to `backend/app/core/config.py`:

```python
DEFAULT_LLM_PROVIDER: str = "openai"

MINIMAX_API_KEY: str = ""
MINIMAX_API_BASE: str = "https://api.minimax.io/v1"

LLM_TRACING_ENABLED: bool = False
```

Optional future additions:

```python
OPENAI_TRACING_ENABLED: bool = True
MINIMAX_TRACING_ENABLED: bool = False
```


## Agent YAML

### Phase 1-2 shape

```yaml
version: 1
name: cover_letter_polisher
provider: minimax
model: MiniMax-M2.5
max_turns: 2
model_settings:
  max_tokens: 2200
  reasoning:
    effort: low
  verbosity: low
```

### Phase 4+ shape

```yaml
version: 1
name: cover_letter_polisher
provider: minimax
model: MiniMax-M2.5
fallbacks:
  - provider: openai
    model: gpt-5-mini
max_turns: 2
```


## Proposed Code Changes

## Files Expected in Phase 1-2

- `backend/app/core/config.py`
- `backend/app/core/llm/agent_loader.py`
- `backend/app/core/llm/gateway.py`
- `backend/app/core/llm/config.py`
- new: `backend/app/core/llm/providers.py`
- selected YAML files in `backend/agent_configs/config/`

## Provider Factory Responsibilities

Recommended functions:

- `get_provider_config(provider_name)`
- `build_openai_client(provider_name)`
- `get_provider_api_mode(provider_name)`
- `is_tracing_enabled(provider_name)`

## Gateway Responsibilities

The gateway should remain the single runtime entry point.

It should:

- resolve provider from the loaded agent
- choose API mode for the provider
- execute the agent using the correct client/runtime mode
- log provider/model used for each call

It should not:

- contain business workflow logic
- hardcode agent IDs
- hide fallback behavior from logs


## Validation Plan

## Phase 1 Validation

- config loads with MiniMax variables present
- MiniMax client can be constructed
- a MiniMax-backed agent can be instantiated by `AgentLoader`

## Phase 2 Validation

- one YAML agent with `provider: minimax` loads successfully
- gateway routes that agent through MiniMax without task code changes

## Phase 3 Validation

- validate `CoverLetterDraft` output stability first
- compare error rate against OpenAI baseline
- inspect malformed JSON or schema mismatch behavior

## Phase 4 Validation

- simulate provider failure
- verify fallback attempt is triggered only when policy allows
- verify logs capture both attempts clearly


## Recommended Rollout Sequence

1. Add provider config and provider factory
2. Make MiniMax execution work for one pilot agent
3. Validate structured output stability
4. Add fallback metadata and gateway support
5. Add richer strategy types only after the above is stable


## Immediate Next Step

The next implementation step should be:

1. add provider-aware settings and provider factory
2. add optional `provider` field support in agent YAML loading
3. route one pilot agent (`job_analyzer`) to MiniMax using chat-completions mode
4. verify `AnalyzedJob` structured output stability before expanding to other agents


## Out of Scope for the First Milestone

- dynamic cost-aware model routing
- automatic quality benchmarking across providers
- mixed-provider parallel racing
- generalized policy engine for all agents
- replacing the existing `AgentGateway` abstraction
