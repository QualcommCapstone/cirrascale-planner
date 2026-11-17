"""LLM providers."""

from __future__ import annotations

import asyncio
import json
import re

from app.config import Settings

# Deterministic fixtures for mock mode. Valid JSON for the two prompt types the
# RAG service builds (outline + per-stop days). Clearly synthetic.
_MOCK_OUTLINE = {
    "title": "Sample Two-Stop Trip",
    "summary": "A short synthetic itinerary for local development.",
    "where": "Japan",
    "when": "Best in late spring",
    "vibes": ["Local Culture", "Street Food"],
    "stops": [
        {
            "city": "Tokyo", "country": "Japan", "lat": 35.6762, "lng": 139.6503, "days": 2,
            "headline": "Neon and Quiet Shrines", "intro": "Backstreet izakayas beside grand shrines.",
            "stay": {"area": "Shinjuku", "why": "Trains everywhere and late-night food"},
            "food": [{"name": "Omoide Yokocho", "note": "Smoky yakitori alley"}],
        },
        {
            "city": "Kyoto", "country": "Japan", "lat": 35.0116, "lng": 135.7681, "days": 2,
            "headline": "Lanterns and Moss", "intro": "Temple gardens before the crowds.",
            "stay": {"area": "Gion", "why": "Walkable old teahouse streets"},
            "food": [{"name": "Nishiki Market", "note": "Grazing lunch of pickles"}],
        },
    ],
    "legs": [{"mode": "train", "durationMins": 140, "notes": "Shinkansen Nozomi"}],
}


def _mock_day(n: int) -> dict:
    def act(slot_name: str, name: str, cat: str, lat: float, lng: float) -> dict:
        return {
            "name": name, "neighborhood": "Central", "durationMins": 90, "cost": "$",
            "category": cat, "reason": f"A well-known {cat} stop (synthetic sample).",
            "lat": lat, "lng": lng,
        }

    return {
        "day": n,
        "morning": act("morning", f"Sample Sight {n}", "sight", 35.68 + n * 0.01, 139.76),
        "afternoon": act("afternoon", f"Sample Museum {n}", "culture", 35.69 + n * 0.01, 139.77),
        "evening": act("evening", f"Sample Food Street {n}", "food", 35.70 + n * 0.01, 139.78),
    }


class MockLLMProvider:
    """Returns deterministic, valid itinerary JSON. Keys off the prompt to pick
    the outline vs. per-stop-days shape."""

    async def generate(self, prompt: str, *, max_tokens: int = 1024) -> str:
        if '"stops"' in prompt:
            return json.dumps(_MOCK_OUTLINE)
        if '"days"' in prompt:
            m = re.search(r"days?\s+(\d+)\s*-\s*(\d+)", prompt)
            if m:
                start, end = int(m.group(1)), int(m.group(2))
            else:
                one = re.search(r"day\s+(\d+)", prompt)
                start = end = int(one.group(1)) if one else 1
            days = [_mock_day(n) for n in range(start, end + 1)]
            return json.dumps({"days": days})
        return "{}"


class CirrascaleLLMProvider:
    """Real completions via the Qualcomm AI Inference Suite. Reuses the known-good
    config (Bearer key, {prompt, model, stream, max_tokens} -> choices[0].text)
    with connection pooling, a request timeout, and bounded retries."""

    def __init__(self, settings: Settings) -> None:
        import httpx

        self._s = settings
        self._client = httpx.AsyncClient(
            base_url=settings.cirrascale_base_url,
            timeout=httpx.Timeout(settings.request_timeout_seconds),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            headers={
                "Authorization": f"Bearer {settings.cirrascale_api_key or ''}",
                "Content-Type": "application/json",
            },
        )

    async def generate(self, prompt: str, *, max_tokens: int = 1024) -> str:
        import httpx

        if not self._s.cirrascale_api_key:
            raise RuntimeError("CIRRASCALE_API_KEY is not set.")

        last_err: Exception | None = None
        for attempt in range(3):
            try:
                resp = await self._client.post(
                    "/completions",
                    json={
                        "prompt": prompt,
                        "model": self._s.cirrascale_model,
                        "stream": False,
                        "max_tokens": max_tokens,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                text = (data.get("choices") or [{}])[0].get("text")
                if not isinstance(text, str):
                    raise RuntimeError("Unexpected Cirrascale response (no choices[0].text).")
                return text.strip()
            except (httpx.HTTPError, RuntimeError) as err:
                last_err = err
                if attempt < 2:
                    await asyncio.sleep(0.5 * (attempt + 1))
        raise RuntimeError(f"Cirrascale request failed after retries: {last_err}")

    async def aclose(self) -> None:
        await self._client.aclose()
