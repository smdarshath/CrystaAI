"""Permission + confirmation layer used by every sensitive tool."""
from __future__ import annotations

import secrets
import threading
import time

from .errors import NeedsConfirmation, PermissionDenied

CONFIRM_TTL = 120


class PendingStore:
    def __init__(self):
        self._items, self._lock = {}, threading.Lock()

    def add(self, tool, kwargs, description, risk):
        token = secrets.token_urlsafe(16)
        with self._lock:
            self._sweep()
            self._items[token] = {"tool": tool, "kwargs": kwargs, "description": description,
                                  "risk": risk, "expires": time.time() + CONFIRM_TTL}
        return token

    def pop(self, token):
        with self._lock:
            self._sweep()
            return self._items.pop(token, None)

    def list(self):
        with self._lock:
            self._sweep()
            return [{"token": t, "description": i["description"], "risk": i["risk"]} for t, i in self._items.items()]

    def _sweep(self):
        t = time.time()
        for k in [k for k, v in self._items.items() if v["expires"] < t]:
            del self._items[k]


class PermissionManager:
    def __init__(self, settings, pending, audit):
        self.settings, self.pending, self.audit = settings, pending, audit

    def check(self, category, tool, kwargs, description, risk="medium", confirmed=False):
        """Raise PermissionDenied / NeedsConfirmation unless the action may proceed now."""
        level = self.settings.level(category)
        if level == "deny":
            self.audit.log("system", tool, description, "denied")
            raise PermissionDenied(f"'{category.replace('_', ' ')}' is switched off in Computer settings.")
        if confirmed:
            return
        if level == "confirm" or category == "destructive":
            token = self.pending.add(tool, kwargs, description, risk)
            raise NeedsConfirmation(token, description, risk, tool)
