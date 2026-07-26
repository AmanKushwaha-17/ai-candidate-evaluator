"""
Shared LLM client — lives in src/common because it has no notion of "stage."
stage1_pretest's resume + github evaluators both depend on this; nothing
stage-specific belongs here.
"""

from __future__ import annotations

import json
import os
import time
from typing import Protocol

import requests


class LLMClient(Protocol):
    def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        """Return the model's response parsed as a JSON dict. Raises on failure."""
        ...


class GroqLLMClient:
    """
    Calls Groq's chat completions endpoint.
    Rotates through all keys in GROQ_API_KEYS on rate-limit (429).
    Falls back to retry with delay only when all keys are exhausted.
    """

    API_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_keys: list[str] | None = None, model: str = "llama-3.3-70b-versatile"):
        if api_keys:
            self._keys = api_keys
        else:
            raw = os.getenv("GROQ_API_KEYS", "")
            self._keys = [k.strip() for k in raw.split(",") if k.strip()]

        if not self._keys:
            raise ValueError("No Groq API keys found (set GROQ_API_KEYS in .env).")

        self.model = model
        self._current_key_idx = 0

    @property
    def _api_key(self) -> str:
        return self._keys[self._current_key_idx]

    def _rotate_key(self) -> bool:
        """Switch to the next key. Returns False if all keys are exhausted."""
        next_idx = self._current_key_idx + 1
        if next_idx >= len(self._keys):
            return False
        self._current_key_idx = next_idx
        print(f"  [rate limit] switching to API key {self._current_key_idx + 1}/{len(self._keys)} …")
        return True

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        self._current_key_idx = 0

        while True:
            try:
                response = requests.post(
                    self.API_URL,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.2,
                        "response_format": {"type": "json_object"},
                    },
                    timeout=30,
                )

                if response.status_code == 429:
                    if self._rotate_key():
                        continue

                    retry_after = int(response.headers.get("Retry-After", 30))
                    print(f"  [rate limit] all keys exhausted — waiting {retry_after}s …")
                    time.sleep(retry_after)
                    self._current_key_idx = 0
                    continue

                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                return json.loads(content)

            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 429:
                    if self._rotate_key():
                        continue
                raise
