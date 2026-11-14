"""Device pairing: laptop shows a code, phone requests, laptop user approves, phone gets a revocable token."""
from __future__ import annotations

import hashlib
import secrets
import threading
import time

from .db import now


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


class Pairing:
    CODE_TTL, MAX_FAILS = 300, 5

    def __init__(self, db, audit):
        self.db, self.audit = db, audit
        self.codes, self.requests, self.fails = {}, {}, {}
        self._lock = threading.Lock()

    def create_code(self):
        code = f"{secrets.randbelow(10**6):06d}"
        with self._lock:
            self.codes = {c: e for c, e in self.codes.items() if e > time.time()}
            self.codes[code] = time.time() + self.CODE_TTL
        return {"code": code, "expires_in": self.CODE_TTL}

    def submit(self, code, name, ip):
        with self._lock:
            f = [t for t in self.fails.get(ip, []) if t > time.time() - 300]
            if len(f) >= self.MAX_FAILS:
                raise PermissionError("Too many wrong codes. Wait 5 minutes.")
            exp = self.codes.get(code)
            if not exp or exp < time.time():
                self.fails[ip] = f + [time.time()]
                raise PermissionError("That code is wrong or expired.")
            del self.codes[code]
            rid = secrets.token_urlsafe(8)
            self.requests[rid] = {"name": (name or "Unnamed device")[:40], "ip": ip, "status": "waiting", "token": None, "created": time.time()}
        self.audit.log("pairing", "request", f"{name} from {ip}")
        return rid

    def pending(self):
        with self._lock:
            return [{"id": k, "name": v["name"], "ip": v["ip"]} for k, v in self.requests.items() if v["status"] == "waiting" and time.time() - v["created"] < 600]

    def decide(self, rid, approve, can_control=False):
        with self._lock:
            r = self.requests.get(rid)
            if not r or r["status"] != "waiting":
                raise KeyError("No such pending request.")
            if not approve:
                r["status"] = "denied"
                self.audit.log("pairing", "denied", r["name"])
                return
            token = secrets.token_urlsafe(32)
            r["status"], r["token"] = "approved", token
        self.db.execute("INSERT INTO device_pairs(name,token_hash,can_control,created,last_seen) VALUES(?,?,?,?,?)",
                        (r["name"], _hash(token), 1 if can_control else 0, now(), now()))
        self.audit.log("pairing", "approved", f"{r['name']} control={can_control}")

    def status(self, rid):
        with self._lock:
            r = self.requests.get(rid)
            if not r:
                return {"status": "unknown"}
            if r["status"] == "approved" and r["token"]:
                tok, r["token"] = r["token"], None  # token is handed over exactly once
                return {"status": "approved", "token": tok}
            return {"status": r["status"]}

    def verify(self, token):
        if not token:
            return None
        row = self.db.one("SELECT id,name,can_control FROM device_pairs WHERE token_hash=? AND revoked=0", (_hash(token),))
        if row:
            self.db.execute("UPDATE device_pairs SET last_seen=? WHERE id=?", (now(), row["id"]))
        return row

    def devices(self):
        return self.db.query("SELECT id,name,can_control,created,last_seen FROM device_pairs WHERE revoked=0 ORDER BY id")

    def revoke(self, device_id):
        self.db.execute("UPDATE device_pairs SET revoked=1 WHERE id=?", (int(device_id),))
        self.audit.log("pairing", "revoked", str(device_id))

    def revoke_all(self):
        self.db.execute("UPDATE device_pairs SET revoked=1")
        self.audit.log("pairing", "revoked_all")

    def set_control(self, device_id, allowed):
        self.db.execute("UPDATE device_pairs SET can_control=? WHERE id=?", (1 if allowed else 0, int(device_id)))
