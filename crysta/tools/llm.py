"""Optional language-model adapters: Ollama (local) or any OpenAI-compatible server. Nothing is downloaded."""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request

from ..errors import LLMUnavailable


def _post(url, payload, headers=None, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _get(url, timeout=1.5):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


class LLM:
    def __init__(self, config):
        self.cfg = config
        self._cache, self._at, self._lock = None, 0.0, threading.Lock()

    def status(self, force=False):
        with self._lock:
            if self._cache and not force and time.time() - self._at < 20:
                return self._cache
        st = {"available": False, "provider": None, "model": None,
              "detail": "No language model connected. Install Ollama (ollama.com) and pull a model to enable open-ended answers."}
        try:
            tags = _get(self.cfg.ollama_url.rstrip("/") + "/api/tags").get("models", [])
            names = [m["name"] for m in tags]
            model = self.cfg.ollama_model or (names[0] if names else "")
            if model:
                st = {"available": True, "provider": "ollama", "model": model, "detail": "Local model via Ollama."}
            else:
                st["detail"] = "Ollama is running but has no models. Run: ollama pull llama3.2:1b"
        except Exception:
            if self.cfg.openai_base and self.cfg.openai_model:
                st = {"available": True, "provider": "openai-compatible", "model": self.cfg.openai_model,
                      "detail": "OpenAI-compatible endpoint configured by you."}
        with self._lock:
            self._cache, self._at = st, time.time()
        return st

    def available(self):
        return self.status()["available"]

    def chat(self, messages, system=None, timeout=120):
        st = self.status()
        if not st["available"]:
            raise LLMUnavailable(st["detail"])
        msgs = ([{"role": "system", "content": system}] if system else []) + messages
        try:
            if st["provider"] == "ollama":
                d = _post(self.cfg.ollama_url.rstrip("/") + "/api/chat",
                          {"model": st["model"], "messages": msgs, "stream": False}, timeout=timeout)
                return d["message"]["content"].strip()
            h = {"Authorization": f"Bearer {self.cfg.openai_key}"} if self.cfg.openai_key else {}
            d = _post(self.cfg.openai_base.rstrip("/") + "/chat/completions",
                      {"model": st["model"], "messages": msgs}, headers=h, timeout=timeout)
            return d["choices"][0]["message"]["content"].strip()
        except (urllib.error.URLError, OSError, KeyError, ValueError) as e:
            self._cache = None
            raise LLMUnavailable(f"The language model didn't answer ({type(e).__name__}).")
