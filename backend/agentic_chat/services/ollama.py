import json

import requests

from .settings import CHAT_MODEL, OLLAMA_URL


def chat(messages, *, json_mode=False, timeout=90):
    payload = {
        "model": CHAT_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0},
    }
    if json_mode:
        payload["format"] = "json"
    response = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=timeout)
    response.raise_for_status()
    content = response.json().get("message", {}).get("content", "")
    if json_mode:
        return json.loads(content)
    return content.strip()

