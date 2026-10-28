# Jarvis provider router (isolated)

This component is deliberately separate from Home Assistant. It routes a conversation request in the order **Groq → Gemini → local**, retrying only on timeouts, rate limits, network errors, and server errors. API keys are read only from environment variables and are never logged.

It does not change Assist, Nabu, Fully Kiosk, or any Home Assistant configuration.

## Configuration

Set `GROQ_API_KEY`, `GEMINI_API_KEY`, and optionally `LOCAL_LLM_URL`. The local endpoint must be OpenAI-compatible. `JARVIS_ROUTER_ORDER` can override the order (for example `groq,gemini,local`).

## Test

`python -m unittest discover -s tests -v`

The included tests use mocked providers and verify fallback without contacting a provider or exposing secrets.
