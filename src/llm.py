"""The only file that talks to an LLM provider.

Everything else calls call_llm(prompt, cfg) and gets back plain text plus real
token counts. To change model, edit `llm:` in config.yaml; to add a provider,
add one function here.
"""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

from src.config import ROOT


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int   # visible output + any "thinking" tokens the provider bills as output
    model: str


def call_llm(prompt: str, cfg: dict) -> LLMResponse:
    """Send one prompt; return the reply. Raises on any API error (the caller decides whether to retry)."""
    load_dotenv(ROOT / ".env")
    key = os.getenv(cfg["api_key_env"])
    if not key:
        raise RuntimeError(f"{cfg['api_key_env']} is not set. Add it to .env")
    if cfg["provider"] == "gemini":
        return _call_gemini(prompt, cfg, key)
    raise ValueError(f"Unknown llm provider {cfg['provider']!r} in config.yaml")


def is_daily_quota(error: Exception) -> bool:
    """A per-day quota error (free tier): nothing will succeed until tomorrow, so the run should stop."""
    text = str(error).lower()
    return getattr(error, "code", None) == 429 and ("per day" in text or "perday" in text)


def is_retryable(error: Exception) -> bool:
    """Retry only temporary problems: per-minute rate limits (429), server errors (5xx) and network errors.
    Other 4xx errors (bad request, bad key) and daily quotas will fail the same way every time."""
    code = getattr(error, "code", None)
    if is_daily_quota(error):
        return False
    return not isinstance(code, int) or code == 429 or code >= 500


def _call_gemini(prompt: str, cfg: dict, key: str) -> LLMResponse:
    from google import genai
    from google.genai import types

    # JSON mode is only available on the v1beta API (the SDK default v1 rejects it with a 400).
    client = genai.Client(api_key=key, http_options=types.HttpOptions(api_version="v1beta"))
    response = client.models.generate_content(
        model=cfg["model"],
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=cfg["temperature"],
            response_mime_type="application/json",   # ask for JSON; the schema itself is in the prompt
        ),
    )
    usage = response.usage_metadata
    return LLMResponse(
        text=response.text or "",
        input_tokens=usage.prompt_token_count or 0,
        output_tokens=(usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0),
        model=cfg["model"],
    )
