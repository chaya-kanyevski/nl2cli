"""עטיפה דקה סביב ספק LLM תואם OpenAI."""
from __future__ import annotations

import time

from . import config

_client = None


class LLMConfigError(RuntimeError):
    pass


def _get_client():
    global _client
    if _client is None:
        if not config.LLM_API_KEY:
            raise LLMConfigError(
                "לא הוגדר LLM_API_KEY. העתיקי את .env.example ל-.env והזיני מפתח."
            )
        from openai import OpenAI
        _client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)
    return _client


def complete(system: str, user: str, temperature: float | None = None,
             retries: int = 3) -> str:
    """שולח פרומפט מערכת + הודעת משתמש ומחזיר את הטקסט הגולמי של המודל."""
    client = _get_client()
    temp = config.TEMPERATURE if temperature is None else temperature
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=config.LLM_MODEL,
                temperature=temp,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            return resp.choices[0].message.content or ""
        except Exception as e:  # rate limit / רשת – ניסיון חוזר עם השהיה
            last_err = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"קריאה ל-LLM נכשלה: {last_err}")
