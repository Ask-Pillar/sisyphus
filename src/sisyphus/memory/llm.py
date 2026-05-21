"""OpenAI-compatible LLM client for memory recall."""

import json
import os
import urllib.request
import urllib.error
from typing import Optional


class LLMClient:
    """Lightweight OpenAI-compatible chat client.

    Reads config from environment:
      SISYPHUS_LLM_API_KEY  (default: $OPENAI_API_KEY)
      SISYPHUS_LLM_BASE_URL (default: https://api.openai.com/v1)
      SISYPHUS_LLM_MODEL    (default: gpt-4o-mini)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 15,
    ):
        self.api_key = api_key or os.environ.get("SISYPHUS_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
        self.base_url = (base_url or os.environ.get("SISYPHUS_LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.model = model or os.environ.get("SISYPHUS_LLM_MODEL") or "gpt-4o-mini"
        self.timeout = timeout

    def chat(self, messages: list) -> str:
        """Send a chat completion request and return response text."""
        if not self.api_key:
            raise RuntimeError(
                "No API key configured. Set SISYPHUS_LLM_API_KEY or OPENAI_API_KEY."
            )

        max_tokens = int(os.environ.get("SISYPHUS_LLM_MAX_TOKENS", "2048"))
        body = json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": max_tokens,
        }).encode()

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            resp = urllib.request.urlopen(req, timeout=self.timeout)
            data = json.loads(resp.read().decode())
            return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"LLM API error {e.code}: {e.read().decode()}")
        except urllib.error.URLError as e:
            raise TimeoutError(f"LLM request failed: {e.reason}")
