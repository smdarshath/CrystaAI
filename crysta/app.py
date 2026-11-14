"""Wires the whole application together (no global state, so tests can build isolated instances)."""
from __future__ import annotations

import logging
import threading
import time
from logging.handlers import RotatingFileHandler

from . import __version__
from .config import Config
from .coordinator import Coordinator
from .db import Database
from .pairing import Pairing
from .permissions import PendingStore, PermissionManager
from .settings import Audit, Settings
from .tools import hardware, system_info
from .tools.llm import LLM
from .tools.registry import Toolbox

log = logging.getLogger("crysta")


def setup_logging(data_dir):
    data_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger("crysta")
    if root.handlers:
        return
    root.setLevel(logging.INFO)
    fh = RotatingFileHandler(data_dir / "crysta.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.addHandler(fh)


class App:
    def __init__(self, config=None, quiet=False):
        self.config = config or Config()
        if not quiet:
            setup_logging(self.config.data_dir)
        self.version = __version__
        self.started = time.time()
        self.db = Database(self.config.data_dir / "crysta.db")
        self.settings = Settings(self.db, self.config)
        self.audit = Audit(self.db)
        self.pending = PendingStore()
        self.perm = PermissionManager(self.settings, self.pending, self.audit)
        self.llm = LLM(self.config)
        self.toolbox = Toolbox(self.config, self.db, self.settings, self.audit, self.perm, self.llm)
        self.toolbox.internet_probe = self.internet
        self.coordinator = Coordinator(self)
        self.pairing = Pairing(self.db, self.audit)
        self._net = (0.0, False)
        self._net_lock = threading.Lock()

    def internet(self):
        with self._net_lock:
            if time.time() - self._net[0] > 30:
                self._net = (time.time(), system_info.internet_ok(1.2))
            return self._net[1]

    def status(self):
        llm = self.llm.status()
        return {"version": self.version, "uptime_s": int(time.time() - self.started),
                "internet": self.internet() and self.settings.get("internet_enabled"),
                "internet_reachable": self.internet(), "internet_enabled": self.settings.get("internet_enabled"),
                "llm": llm, "memory_enabled": self.settings.get("memory_enabled"), "agents": len(self.coordinator.registry.ids()),
                "user_name": self.settings.get("user_name"), "process": hardware.own_process(),
                "loaded_agents": self.coordinator.registry.loaded_ids()}

    def execute_confirmation(self, token, approve):
        item = self.pending.pop(token)
        if not item:
            return {"ok": False, "message": "That confirmation expired or was already used."}
        if not approve:
            self.audit.log("user", item["tool"], item["description"], "declined")
            return {"ok": True, "declined": True, "message": "Okay, I cancelled that."}
        self.audit.log("user", item["tool"], item["description"], "approved")
        try:
            r = self.toolbox.call(item["tool"], _confirmed=True, **item["kwargs"])
        except Exception as e:
            log.warning("confirmed action failed: %s", e)
            return {"ok": False, "message": str(e) if str(e) else "That failed."}
        if isinstance(r, dict) and "ok" in r:
            return r
        return {"ok": True, "message": "Done.", "data": r}
