"""Language-model adapters for ova.brain.ModelBrain, and photo notes for the adjuster.

No model id is built in: the operator sets OVA_LLM_MODEL to a current, fast model. The turn
model stays small and fast; the brain calls it only for what the rules could not place.
"""
from __future__ import annotations

import base64


class AnthropicChat:
    """Anthropic Messages API (REST). Written to the docs (checked 2026-09); tested against a
    fake."""

    def __init__(self, key: str, model: str, base_url: str = "https://api.anthropic.com",
                 client=None):
        self.key, self.model, self.base_url, self.client = key, model, base_url, client
        self.name = f"anthropic:{model}"

    async def _post(self, body: dict) -> dict:
        import httpx
        client = self.client or httpx.AsyncClient(timeout=20)
        try:
            r = await client.post(f"{self.base_url}/v1/messages", json=body,
                                  headers={"x-api-key": self.key,
                                           "anthropic-version": "2023-06-01"})
            r.raise_for_status()
            return r.json()
        finally:
            if self.client is None:
                await client.aclose()

    async def complete(self, system: str, user: str, max_tokens: int = 300) -> str:
        data = await self._post({"model": self.model, "max_tokens": max_tokens,
                                 "system": system,
                                 "messages": [{"role": "user", "content": user}]})
        return "".join(b.get("text", "") for b in data.get("content", [])
                       if b.get("type") == "text")

    async def describe_image(self, image: bytes, mime: str, prompt: str) -> str:
        data = await self._post({"model": self.model, "max_tokens": 200, "messages": [
            {"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime,
                                             "data": base64.b64encode(image).decode()}},
                {"type": "text", "text": prompt}]}]})
        return "".join(b.get("text", "") for b in data.get("content", [])
                       if b.get("type") == "text")


class OpenAIChat:
    """OpenAI-compatible chat completions: OpenAI, Ollama, vLLM, and others. Written to the
    docs (checked 2026-09); tested against a fake."""

    def __init__(self, key: str, model: str, base_url: str = "https://api.openai.com",
                 client=None):
        self.key, self.model, self.base_url, self.client = key, model, base_url, client
        self.name = f"openai-compatible:{model}"

    async def _post(self, body: dict) -> dict:
        import httpx
        client = self.client or httpx.AsyncClient(timeout=20)
        try:
            r = await client.post(f"{self.base_url}/v1/chat/completions", json=body,
                                  headers={"Authorization": f"Bearer {self.key}"})
            r.raise_for_status()
            return r.json()
        finally:
            if self.client is None:
                await client.aclose()

    async def complete(self, system: str, user: str, max_tokens: int = 300) -> str:
        data = await self._post({"model": self.model, "max_tokens": max_tokens,
                                 "temperature": 0,
                                 "messages": [{"role": "system", "content": system},
                                              {"role": "user", "content": user}]})
        return data["choices"][0]["message"]["content"] or ""

    async def describe_image(self, image: bytes, mime: str, prompt: str) -> str:
        url = f"data:{mime};base64,{base64.b64encode(image).decode()}"
        data = await self._post({"model": self.model, "max_tokens": 200, "messages": [
            {"role": "user", "content": [{"type": "text", "text": prompt},
                                         {"type": "image_url", "image_url": {"url": url}}]}]})
        return data["choices"][0]["message"]["content"] or ""


PHOTO_PROMPT = ("You help an insurance adjuster triage a photo sent with a claim. In one or "
                "two sentences, describe the visible damage and what the photo shows. Do not "
                "estimate cost and do not say whether anything is covered. If the photo is "
                "unclear or shows no damage, say so.")
