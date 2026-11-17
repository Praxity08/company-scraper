"""Calls Google's Gemini API and returns JSON that follows a given schema.

The AI only REPORTS facts with quotes; plain code checks the quotes and makes every decision.
The key is sent in a header (never in the address) and never appears in error messages.
"""
import json

import requests

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MODELS_API = "https://generativelanguage.googleapis.com/v1beta/models"
TIMEOUT = 100   # seconds to wait for one answer


class AIError(Exception):
    """A Gemini problem, with a message that never contains the key."""


def scrub(text, key):
    return text.replace(key, "[key hidden]") if key else text


def generate_json(system, prompt, schema, api_key, model, timeout=TIMEOUT):
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json",
                             "responseSchema": schema},
    }
    try:
        r = requests.post(API.format(model=model), json=body, timeout=timeout,
                          headers={"x-goog-api-key": api_key, "Content-Type": "application/json"})
    except requests.RequestException as e:
        raise AIError(f"could not reach Gemini ({type(e).__name__})") from None
    if r.status_code != 200:
        detail = ""
        try:
            detail = str((r.json().get("error") or {}).get("message", ""))
        except ValueError:
            pass
        raise AIError(scrub(f"Gemini returned HTTP {r.status_code}" + (f": {detail[:200]}" if detail else ""), api_key))
    try:
        data = r.json()
    except ValueError:
        raise AIError("Gemini sent a reply that is not JSON") from None
    candidates = data.get("candidates") or []
    if not candidates:
        reason = (data.get("promptFeedback") or {}).get("blockReason", "no answer")
        raise AIError(f"Gemini gave no answer ({reason})")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
    try:
        return json.loads(text)
    except ValueError:
        raise AIError(f"Gemini's answer could not be read (finish reason: {candidates[0].get('finishReason', '?')})") from None


def list_models(api_key):
    """Names of the models this key may use for generateContent (for checking the setting)."""
    r = requests.get(MODELS_API, headers={"x-goog-api-key": api_key}, params={"pageSize": 200}, timeout=20)
    if r.status_code != 200:
        raise AIError(f"Gemini returned HTTP {r.status_code} when listing models")
    return [m["name"].split("/", 1)[-1] for m in r.json().get("models", [])
            if "generateContent" in (m.get("supportedGenerationMethods") or [])]
