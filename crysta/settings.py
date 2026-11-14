"""User settings, permission levels and the audit log."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from .db import now

log = logging.getLogger("crysta.settings")
LEVELS = ("allow", "confirm", "deny")
PERM_CATEGORIES = ("read_files", "write_files", "open_apps", "run_commands", "keyboard_mouse", "destructive")
AUTO_TRUSTABLE = ("write_files", "open_apps", "run_commands", "keyboard_mouse")


def _bool(v): return isinstance(v, bool)
def _level(v): return v in LEVELS
def _dirs(v): return isinstance(v, list) and all(isinstance(x, str) and x for x in v) and len(v) <= 20


VALIDATORS = {
    "user_name": lambda v: isinstance(v, str) and 0 < len(v) <= 40,
    "memory_enabled": _bool,
    "internet_enabled": _bool,
    "speak_responses": _bool,
    "reduce_motion": _bool,
    "voice_lang": lambda v: v in ("en-IN", "en-US", "en-GB", "ta-IN"),
    "autonomy": lambda v: v in ("ask", "trusted"),
    "approved_dirs": _dirs,
    "speech_rate": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and 0.5 <= v <= 2,
    "speech_pitch": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and 0.5 <= v <= 2,
    "speech_volume": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1,
    "voice_name": lambda v: isinstance(v, str) and len(v) <= 120,
    "extensions_enabled": lambda v: isinstance(v, list) and all(isinstance(x, str) and len(x) <= 40 for x in v) and len(v) <= 20,
    **{f"perm.{c}": _level for c in PERM_CATEGORIES},
}


class Settings:
    def __init__(self, db, config):
        self.db, self.config = db, config

    def defaults(self):
        d = {
            "user_name": self.config.user_name, "memory_enabled": False, "internet_enabled": True,
            "speak_responses": True, "reduce_motion": False, "voice_lang": "en-IN", "autonomy": "ask",
            "approved_dirs": [str(Path.home())], "speech_rate": 1.0, "speech_pitch": 1.0, "speech_volume": 1.0,
            "voice_name": "", "extensions_enabled": [],
            "perm.read_files": "allow", "perm.write_files": "confirm", "perm.open_apps": "allow",
            "perm.run_commands": "confirm", "perm.keyboard_mouse": "confirm", "perm.destructive": "confirm",
        }
        return d

    def get(self, key):
        try:
            row = self.db.one("SELECT value FROM settings WHERE key=?", (key,))
            if row:
                return json.loads(row["value"])
        except Exception:
            log.exception("settings read failed for %s", key)
        return self.defaults()[key]

    def all(self):
        return {k: self.get(k) for k in self.defaults()}

    def set(self, key, value):
        if key not in VALIDATORS or not VALIDATORS[key](value):
            raise ValueError(f"Invalid setting: {key}")
        if key == "perm.destructive" and value == "allow":
            raise ValueError("Destructive actions can never be set to 'allow'; use 'confirm' or 'deny'.")
        self.db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (key, json.dumps(value)))

    def update(self, patch):
        for k, v in patch.items():  # validate everything first
            if k not in VALIDATORS or not VALIDATORS[k](v):
                raise ValueError(f"Invalid setting: {k}")
            if k == "perm.destructive" and v == "allow":
                raise ValueError("Destructive actions can never be set to 'allow'.")
        for k, v in patch.items():
            self.set(k, v)
        return patch

    def level(self, category):
        lvl = self.get(f"perm.{category}")
        if lvl != "deny" and category in AUTO_TRUSTABLE and self.get("autonomy") == "trusted":
            return "allow"
        return lvl


_SECRET = re.compile(r"(?i)\b(token|password|passwd|secret|api[_-]?key|authorization)\b(\s*[=:]\s*|\s+)(\S+)")
_BEARER = re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+")


def redact(text):
    text = _BEARER.sub("Bearer ***", str(text))
    return _SECRET.sub(lambda m: f"{m.group(1)}{m.group(2)}***", text)


class Audit:
    def __init__(self, db):
        self.db = db

    def log(self, actor, action, detail="", outcome="ok"):
        try:
            self.db.execute("INSERT INTO audit_events(created,actor,action,detail,outcome) VALUES(?,?,?,?,?)",
                            (now(), actor, action, redact(detail)[:500], outcome))
        except Exception:
            log.exception("audit write failed")

    def recent(self, n=50):
        try:
            return self.db.query("SELECT created,actor,action,detail,outcome FROM audit_events ORDER BY id DESC LIMIT ?", (n,))
        except Exception:
            return []

    def clear(self):
        self.db.execute("DELETE FROM audit_events")
