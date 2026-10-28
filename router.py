"""Small, dependency-free Jarvis fallback router.

Provider credentials are never included in errors or logs. This is an isolated
prototype; Home Assistant integration is intentionally a later step.
"""
from __future__ import annotations
import json, os, urllib.error, urllib.request
from dataclasses import dataclass


class ProviderError(RuntimeError):
    def __init__(self, provider: str, retryable: bool, status: int | None = None):
        super().__init__(f"{provider} unavailable")
        self.provider, self.retryable, self.status = provider, retryable, status


@dataclass
class Result:
    text: str
    provider: str
    attempts: tuple[str, ...]


def _post(url: str, payload: dict, headers: dict[str, str], timeout: float) -> dict:
    req = urllib.request.Request(url, json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        # Authentication/model/endpoint errors are also retryable here: the
        # next configured provider must remain available when one provider's
        # key or model is restricted.
        raise ProviderError("provider", exc.code in (400, 401, 403, 404, 408, 409, 429) or exc.code >= 500, exc.code) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ProviderError("provider", True) from None


class Router:
    def __init__(self, providers: dict[str, callable] | None = None, order: list[str] | None = None):
        self.providers = providers or self._configured()
        self.order = order or [p.strip() for p in os.getenv("JARVIS_ROUTER_ORDER", "groq,gemini,local").split(",") if p.strip()]

    def _configured(self):
        out = {}
        if os.getenv("GROQ_API_KEY"):
            out["groq"] = lambda messages: self._openai("groq", "https://api.groq.com/openai/v1/chat/completions", os.environ["GROQ_API_KEY"], os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"), messages)
        if os.getenv("GEMINI_API_KEY"):
            out["gemini"] = lambda messages: self._gemini(os.environ["GEMINI_API_KEY"], os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"), messages)
        if os.getenv("LOCAL_LLM_URL"):
            out["local"] = lambda messages: self._openai("local", os.environ["LOCAL_LLM_URL"].rstrip("/") + "/v1/chat/completions", os.getenv("LOCAL_LLM_KEY", ""), os.getenv("LOCAL_LLM_MODEL", "local"), messages)
        return out

    def _openai(self, name, url, key, model, messages):
        headers = {"Content-Type": "application/json"}
        if key: headers["Authorization"] = "Bearer " + key
        data = _post(url, {"model": model, "messages": messages, "temperature": 0.2}, headers, 12)
        return data["choices"][0]["message"]["content"]

    def _gemini(self, key, model, messages):
        prompt = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        data = _post(url, {"contents": [{"parts": [{"text": prompt}]}]}, {"Content-Type": "application/json"}, 12)
        return data["candidates"][0]["content"]["parts"][0]["text"]

    def complete(self, messages) -> Result:
        attempts = []
        for name in self.order:
            fn = self.providers.get(name)
            if not fn: continue
            attempts.append(name)
            try:
                text = fn(messages)
                if text: return Result(text, name, tuple(attempts))
                raise ProviderError(name, True)
            except ProviderError as exc:
                if not exc.retryable: raise
        raise RuntimeError("No configured provider responded")
