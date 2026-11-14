"""HTTP server (standard library). Local UI = full access; paired phones = token + limited scope."""
from __future__ import annotations

import hmac
import json
import logging
import mimetypes
import ssl
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlparse

from . import nlp
from .errors import CrystaError, NeedsConfirmation, PermissionDenied, ToolUnavailable

log = logging.getLogger("crysta.server")
MAX_BODY = 65536
LOOPBACK = {"127.0.0.1", "::1", "::ffff:127.0.0.1"}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]", "::1"}
STATIC_OK = {".html", ".js", ".css", ".svg", ".png", ".ico", ".json", ".webmanifest"}
PUBLIC = {("GET", "/api/health"), ("POST", "/api/pair/request"), ("GET", "/api/pair/status")}
LOCAL_ONLY = {("PATCH", "/api/settings"), ("POST", "/api/devices/pair-code"), ("GET", "/api/devices"), ("POST", "/api/devices/decide"),
              ("POST", "/api/devices/disconnect"), ("POST", "/api/devices/revoke-all"), ("POST", "/api/devices/control"), ("GET", "/api/audit"), ("POST", "/api/open-url"),
              ("DELETE", "/api/audit"), ("GET", "/api/memory"), ("DELETE", "/api/memory"), ("GET", "/api/memory/export"),
              ("POST", "/api/emergency-stop")}


class ApiError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def make_handler(app):
    routes = {}

    def route(method, path):
        def deco(fn):
            routes[(method, path)] = fn
            return fn
        return deco

    def need(body, key, typ=str, maxlen=2000):
        v = body.get(key)
        if not isinstance(v, typ) or (typ is str and (not v.strip() or len(v) > maxlen)):
            raise ApiError(400, "bad_request", f"'{key}' is missing or invalid.")
        return v

    def arg(q, key, default=""):
        return (q.get(key) or [default])[0]

    def tool(name, **kw):
        """Run a toolbox tool for a direct UI action; permission prompts become a structured 'needs_confirmation' reply."""
        try:
            r = app.toolbox.call(name, **kw)
        except NeedsConfirmation as nc:
            return {"status": "needs_confirmation", "confirmation": {"token": nc.token, "description": nc.description, "risk": nc.risk, "tool": nc.tool}}
        except PermissionDenied as e:
            raise ApiError(403, "permission_denied", str(e))
        except ToolUnavailable as e:
            raise ApiError(503, "unavailable", str(e))
        return {"status": "ok", "result": r}

    # ---------- routes
    @route("GET", "/api/health")
    def health(h, q, body, auth):
        return {"status": "ok", "version": app.version}

    @route("GET", "/api/status")
    def status(h, q, body, auth):
        return app.status()

    @route("GET", "/api/agents")
    def agents(h, q, body, auth):
        last = {}
        for run in app.coordinator.history:
            last[run["agent"]] = run
        reg = app.coordinator.registry
        return {"agents": [dict(a, last_run=last.get(a["id"])) for a in reg.listing()], "loaded": reg.loaded_ids(), "extensions": reg.extension_report}

    @route("GET", "/api/agent")
    def agent_detail(h, q, body, auth):
        try:
            return app.coordinator.registry.get(arg(q, "id")).info()
        except KeyError:
            raise ApiError(404, "not_found", "No such agent.")

    @route("POST", "/api/chat")
    def chat(h, q, body, auth):
        msg = need(body, "message")
        conv = str(body.get("conversation_id") or "default")[:40]
        remote = auth["role"] != "local"
        return app.coordinator.handle(msg, conv, remote=remote, can_control=bool(auth.get("can_control")), deep=bool(body.get("deep")))

    @route("POST", "/api/research")
    def research(h, q, body, auth):
        mode = body.get("mode", "web")
        if mode == "video":
            url = need(body, "url", maxlen=300)
            sub = nlp.Subtask("video", "zykron", url, {"url": url})
            label = url
        else:
            label = need(body, "query", maxlen=300)
            sub = nlp.Subtask("youtube" if mode == "youtube" else "research", "zykron", label,
                              {"query": label, "deep": bool(body.get("deep")), "verify": bool(body.get("verify"))})
        out = app.coordinator.run_single(sub, deep=bool(body.get("deep")))
        r = out["results"][0]
        try:
            app.toolbox.call("research_history_add", query=label, kind=mode, status=r["status"], summary=r["summary"], sources=r["sources"])
        except Exception:
            log.exception("history save failed")
        return out

    @route("GET", "/api/research/history")
    def research_history(h, q, body, auth):
        return {"enabled": app.settings.get("memory_enabled"), "history": app.toolbox.call("research_history_list")}

    @route("DELETE", "/api/research/history")
    def research_history_clear(h, q, body, auth):
        return app.toolbox.call("research_history_clear")

    @route("GET", "/api/hardware")
    def hardware_info(h, q, body, auth):
        return app.toolbox.call("hardware")

    # ----- files (VEGA / NOVA workspaces). Permission prompts come back as needs_confirmation.
    @route("GET", "/api/files/places")
    def f_places(h, q, body, auth): return tool("files_places")

    @route("GET", "/api/files/list")
    def f_list(h, q, body, auth): return tool("files_list", path=arg(q, "path", "~"))

    @route("GET", "/api/files/info")
    def f_info(h, q, body, auth): return tool("files_info", path=need({"p": arg(q, "path")}, "p"))

    @route("GET", "/api/files/read")
    def f_read(h, q, body, auth): return tool("files_read", path=need({"p": arg(q, "path")}, "p"))

    @route("GET", "/api/files/find")
    def f_find(h, q, body, auth): return tool("files_find", name=need({"n": arg(q, "name")}, "n", maxlen=100), root=arg(q, "root") or None)

    @route("GET", "/api/files/image")
    def f_image(h, q, body, auth):
        r = tool("files_image", path=need({"p": arg(q, "path")}, "p"))
        return r["result"]  # (mime, bytes)

    @route("POST", "/api/files/write")
    def f_write(h, q, body, auth): return tool("files_write", path=need(body, "path"), content=need({"c": body.get("content", "x") or "x"}, "c", maxlen=2_000_000) and body.get("content", ""))

    @route("POST", "/api/files/mkdir")
    def f_mkdir(h, q, body, auth): return tool("files_mkdir", path=need(body, "path"))

    @route("POST", "/api/files/rename")
    def f_rename(h, q, body, auth): return tool("files_rename", path=need(body, "path"), new_name=need(body, "new_name", maxlen=200))

    @route("POST", "/api/files/copy")
    def f_copy(h, q, body, auth): return tool("files_copy", src=need(body, "src"), dst=need(body, "dst"))

    @route("POST", "/api/files/move")
    def f_move(h, q, body, auth): return tool("files_move", src=need(body, "src"), dst=need(body, "dst"))

    @route("POST", "/api/files/delete")
    def f_delete(h, q, body, auth): return tool("files_delete", path=need(body, "path"))

    @route("POST", "/api/files/open")
    def f_open(h, q, body, auth): return tool("files_open", path=need(body, "path"))

    @route("POST", "/api/open-url")
    def open_url(h, q, body, auth): return tool("open_url", url=need(body, "url", maxlen=1000))

    @route("POST", "/api/terminal/run")
    def term_run(h, q, body, auth): return tool("run_command", command=need(body, "command", maxlen=500))

    @route("GET", "/api/project/commands")
    def proj_cmds(h, q, body, auth): return tool("project_commands", path=arg(q, "path", "~"))

    @route("GET", "/api/project/inspect")
    def proj_inspect(h, q, body, auth): return tool("project_inspect", path=arg(q, "path", "~"))

    @route("POST", "/api/error/explain")
    def err_explain(h, q, body, auth): return app.toolbox.call("explain_error", text=need(body, "text", maxlen=20000))

    @route("GET", "/api/logs")
    def logs(h, q, body, auth): return app.toolbox.call("logs_tail", lines=min(int(arg(q, "lines", "200") or 200), 500))

    # ----- science
    @route("GET", "/api/science/library")
    def sci_lib(h, q, body, auth): return app.toolbox.call("science_library")

    @route("POST", "/api/science/solve")
    def sci_solve(h, q, body, auth):
        return app.toolbox.call("science_solve", formula=need(body, "formula", maxlen=40), values=need(body, "values", dict), target=need(body, "target", maxlen=10))

    @route("POST", "/api/science/plot")
    def sci_plot(h, q, body, auth):
        return app.toolbox.call("science_plot", expr=need(body, "expr", maxlen=200), lo=float(body.get("lo", -10)), hi=float(body.get("hi", 10)))

    @route("POST", "/api/calc")
    def calc(h, q, body, auth):
        try:
            return app.toolbox.call("calculator", text=need(body, "text", maxlen=200))
        except ValueError as e:
            raise ApiError(400, "bad_expression", str(e))

    # ----- notes / memory / tasks
    @route("GET", "/api/notes")
    def notes_list(h, q, body, auth): return {"enabled": app.settings.get("memory_enabled"), "notes": app.toolbox.call("notes_list")}

    @route("POST", "/api/notes")
    def notes_add(h, q, body, auth):
        return app.toolbox.call("notes_add", title=str(body.get("title") or need(body, "body", maxlen=5000))[:60], body=need(body, "body", maxlen=5000),
                                category=str(body.get("category") or "general")[:30], project=(str(body["project"])[:60] if body.get("project") else None))

    @route("PATCH", "/api/notes")
    def notes_patch(h, q, body, auth):
        return app.toolbox.call("notes_update", id=need(body, "id", int), **{k: body[k] for k in ("title", "body", "category", "project") if k in body})

    @route("DELETE", "/api/notes")
    def notes_del(h, q, body, auth): return app.toolbox.call("notes_delete", id=need(body, "id", int))

    @route("GET", "/api/memory/search")
    def mem_search(h, q, body, auth): return app.toolbox.call("memory_search", query=need({"q": arg(q, "q")}, "q", maxlen=100))

    @route("POST", "/api/memory/enable")
    def mem_enable(h, q, body, auth): return tool("memory_set_enabled", enabled=bool(body.get("enabled", True)))

    @route("GET", "/api/tasks")
    def tasks_list(h, q, body, auth): return {"tasks": app.toolbox.call("task_list", project=arg(q, "project") or None), "projects": app.toolbox.call("projects")}

    @route("POST", "/api/tasks")
    def tasks_add(h, q, body, auth):
        due = body.get("due")
        return app.toolbox.call("task_add", title=need(body, "title", maxlen=200), due=float(due) if due not in (None, "") else None,
                                project=str(body.get("project") or "General")[:60], kind=body.get("kind", "task"), status=body.get("status", "pending"))

    @route("PATCH", "/api/tasks")
    def tasks_patch(h, q, body, auth):
        kw = {k: body[k] for k in ("title", "status", "project", "kind") if k in body}
        if "due" in body:
            kw["due"] = float(body["due"]) if body["due"] not in (None, "") else None
        return app.toolbox.call("task_update", id=need(body, "id", int), **kw)

    @route("DELETE", "/api/tasks")
    def tasks_del(h, q, body, auth): return app.toolbox.call("task_delete", id=need(body, "id", int))

    @route("POST", "/api/orion/starter-plan")
    def starter_plan(h, q, body, auth):
        proj = str(body.get("project") or "General")[:60]
        steps = ["Define the goal and what \"done\" looks like", "Research and collect requirements", "Design the approach", "Build the first working version", "Test and fix problems", "Release and review"]
        now_t = time.time()
        ids = [app.toolbox.call("task_add", title=t, due=now_t + (i + 1) * 7 * 86400, project=proj, kind="milestone")["id"] for i, t in enumerate(steps)]
        return {"created": ids}

    # ----- voice (only real engines are exposed)
    @route("GET", "/api/voice/status")
    def voice_status(h, q, body, auth): return app.toolbox.call("voice_status")

    @route("POST", "/api/voice/speak")
    def voice_speak(h, q, body, auth):
        st = app.toolbox.call("voice_status")
        if not st["tts_engine"]:
            raise ApiError(501, "not_available", "No operating-system speech engine is installed (Linux: sudo apt install espeak-ng).")
        return app.toolbox.call("voice_speak", text=need(body, "text", maxlen=800), lang=str(body.get("lang", "en"))[:10], rate=float(body.get("rate", 1.0)))

    @route("POST", "/api/voice/stop")
    def voice_stop(h, q, body, auth): return app.toolbox.call("voice_stop")

    @route("POST", "/api/voice/listen")
    def voice_listen(h, q, body, auth):
        if not app.toolbox.call("voice_status")["stt"]["available"]:
            raise ApiError(501, "not_available", app.toolbox.call("voice_status")["stt"]["reason"])
        return app.toolbox.call("voice_listen")


    @route("POST", "/api/cancel")
    def cancel(h, q, body, auth):
        app.coordinator.cancel(body.get("conversation_id"))
        return {"ok": True}

    @route("POST", "/api/confirm")
    def confirm(h, q, body, auth):
        if auth["role"] != "local" and not auth.get("can_control"):
            raise ApiError(403, "forbidden", "This device can't approve actions.")
        return app.execute_confirmation(need(body, "token"), bool(body.get("approve")))

    @route("GET", "/api/settings")
    def get_settings(h, q, body, auth):
        s = app.settings.all()
        return {"settings": s, "effective_levels": {c: app.settings.level(c) for c in ("read_files", "write_files", "open_apps", "run_commands", "keyboard_mouse", "destructive")},
                "llm": app.llm.status(), "lan_enabled": app.config.host not in ("127.0.0.1", "localhost", "::1"), "port": app.config.port}

    @route("PATCH", "/api/settings")
    def patch_settings(h, q, body, auth):
        try:
            app.settings.update(body)
        except ValueError as e:
            raise ApiError(400, "invalid_setting", str(e))
        app.audit.log("user", "settings", ",".join(body.keys()))
        return get_settings(h, q, {}, auth)

    @route("POST", "/api/devices/pair-code")
    def pair_code(h, q, body, auth):
        return app.pairing.create_code()

    @route("POST", "/api/pair/request")
    def pair_request(h, q, body, auth):
        try:
            rid = app.pairing.submit(need(body, "code", maxlen=10), str(body.get("name", ""))[:40], h.client_address[0])
        except PermissionError as e:
            raise ApiError(403, "pairing_refused", str(e))
        return {"request_id": rid}

    @route("GET", "/api/pair/status")
    def pair_status(h, q, body, auth):
        return app.pairing.status((q.get("id") or [""])[0])

    @route("GET", "/api/devices")
    def devices(h, q, body, auth):
        return {"devices": app.pairing.devices(), "pending": app.pairing.pending()}

    @route("POST", "/api/devices/decide")
    def decide(h, q, body, auth):
        try:
            app.pairing.decide(need(body, "id"), bool(body.get("approve")), bool(body.get("can_control")))
        except KeyError as e:
            raise ApiError(404, "not_found", str(e))
        return {"ok": True}

    @route("POST", "/api/devices/disconnect")
    def disconnect(h, q, body, auth):
        app.pairing.revoke(need(body, "id", int))
        return {"ok": True}

    @route("POST", "/api/devices/control")
    def dev_control(h, q, body, auth):
        app.pairing.set_control(need(body, "id", int), bool(body.get("allowed")))
        return {"ok": True}

    @route("POST", "/api/devices/revoke-all")
    def revoke_all(h, q, body, auth):
        app.pairing.revoke_all()
        return {"ok": True}

    @route("POST", "/api/emergency-stop")
    def emergency(h, q, body, auth):
        app.coordinator.cancel()
        app.pairing.revoke_all()
        app.settings.update({"autonomy": "ask"})
        app.audit.log("user", "emergency_stop", "all devices revoked, autonomy reset", "ok")
        return {"ok": True, "message": "All devices disconnected, running tasks cancelled, full-control mode off."}

    @route("GET", "/api/audit")
    def audit(h, q, body, auth):
        return {"events": app.audit.recent(60)}

    @route("DELETE", "/api/audit")
    def audit_clear(h, q, body, auth):
        app.audit.clear()
        return {"ok": True}

    @route("GET", "/api/memory")
    def memory(h, q, body, auth):
        return {"enabled": app.settings.get("memory_enabled"), "memories": app.toolbox.t_memory_list(), "notes": app.toolbox.t_notes_list(),
                "messages": app.db.one("SELECT COUNT(*) AS n FROM messages")["n"]}

    @route("DELETE", "/api/memory")
    def memory_delete(h, q, body, auth):
        if body.get("scope") == "all":
            return app.toolbox.t_memory_delete(scope="all", _confirmed=True)  # user pressed a button in the UI
        if isinstance(body.get("id"), int):
            return app.toolbox.t_memory_delete(id=body["id"])
        raise ApiError(400, "bad_request", "Send {id} or {scope:'all'}.")

    @route("GET", "/api/memory/export")
    def memory_export(h, q, body, auth):
        return {"exported": time.time(), "memories": app.toolbox.t_memory_list(), "notes": app.toolbox.t_notes_list(),
                "messages": app.db.query("SELECT conversation_id,role,content,created FROM messages ORDER BY id")}

    @route("GET", "/api/tasks/due")
    def tasks_due(h, q, body, auth):
        return {"due": app.db.query("SELECT id,title,due FROM tasks WHERE status='pending' AND notified=0 AND due IS NOT NULL AND due<=?", (time.time(),))}

    @route("POST", "/api/tasks/ack")
    def tasks_ack(h, q, body, auth):
        app.db.execute("UPDATE tasks SET notified=1 WHERE id=?", (need(body, "id", int),))
        return {"ok": True}

    # ---------- handler
    class Handler(BaseHTTPRequestHandler):
        server_version = "CrystaAI"
        sys_version = ""

        def log_message(self, fmt, *args):
            log.debug(fmt, *args)

        def _send(self, status, payload, ctype="application/json", extra=None):
            raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(raw)

        def _err(self, status, code, message):
            self._send(status, {"error": {"code": code, "message": message}})

        def _auth(self):
            ip = self.client_address[0]
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0].lower() if not (self.headers.get("Host") or "").startswith("[") else "[::1]"
            if ip in LOOPBACK:
                if host not in LOCAL_HOSTS and host not in app.config.allowed_hosts:
                    raise ApiError(403, "bad_host", "Unexpected Host header.")
                tok = app.config.session_token
                if tok:  # desktop mode: only the app window (which holds the cookie) may use the API
                    jar = SimpleCookie(self.headers.get("Cookie") or "")
                    if "crysta_session" not in jar or not hmac.compare_digest(jar["crysta_session"].value, tok):
                        return {"role": "anonymous"}
                return {"role": "local"}
            token = (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
            dev = app.pairing.verify(token)
            if dev:
                return {"role": "device", "can_control": bool(dev["can_control"]), "device": dev["name"]}
            return {"role": "anonymous"}

        def _dispatch(self, method):
            try:
                url = urlparse(self.path)
                auth = self._auth()
                if method in ("POST", "PATCH", "DELETE"):
                    origin = self.headers.get("Origin")
                    if origin and urlparse(origin).netloc != self.headers.get("Host"):
                        raise ApiError(403, "bad_origin", "Cross-site requests are not allowed.")
                if method == "GET" and app.config.session_token and parse_qs(url.query).get("s", [""])[0]:
                    if hmac.compare_digest(parse_qs(url.query)["s"][0], app.config.session_token):  # first load by the app window
                        self.send_response(302); self.send_header("Location", "/")
                        self.send_header("Set-Cookie", f"crysta_session={app.config.session_token}; Path=/; HttpOnly; SameSite=Strict")
                        self.send_header("Content-Length", "0"); self.end_headers(); return
                if not url.path.startswith("/api/"):
                    if app.config.session_token and auth["role"] == "anonymous" and url.path in ("/", "/index.html"):
                        return self._err(401, "unauthorized", "Open CRYSTA from its own application window.")
                    return self._static(url.path) if method == "GET" else self._err(405, "method_not_allowed", "Not allowed.")
                fn = routes.get((method, url.path))
                if fn is None:
                    raise ApiError(404, "not_found", "No such endpoint.")
                key = (method, url.path)
                if auth["role"] == "anonymous" and key not in PUBLIC:
                    raise ApiError(401, "unauthorized", "Pair this device first.")
                if auth["role"] != "local" and key in LOCAL_ONLY:
                    raise ApiError(403, "local_only", "This can only be done on the computer running Crysta.")
                body = {}
                if method in ("POST", "PATCH", "DELETE"):
                    n = int(self.headers.get("Content-Length") or 0)
                    if n > MAX_BODY:
                        raise ApiError(413, "too_large", "Request is too large.")
                    if n:
                        try:
                            body = json.loads(self.rfile.read(n).decode("utf-8"))
                        except (ValueError, UnicodeDecodeError):
                            raise ApiError(400, "bad_json", "Request body must be valid JSON.")
                        if not isinstance(body, dict):
                            raise ApiError(400, "bad_json", "Request body must be a JSON object.")
                if auth["role"] == "device" and not auth.get("can_control") and url.path.startswith(("/api/files/", "/api/terminal/", "/api/logs", "/api/project/", "/api/hardware")):
                    raise ApiError(403, "forbidden", "This paired device is not allowed to control this computer.")
                result = fn(self, parse_qs(url.query), body, auth)
                if isinstance(result, tuple):
                    return self._send(200, result[1], result[0])
                extra = {"Content-Disposition": "attachment; filename=crysta-export.json"} if url.path == "/api/memory/export" else None
                self._send(200, result, extra=extra)
            except ApiError as e:
                self._err(e.status, e.code, e.message)
            except PermissionDenied as e:
                self._err(403, "permission_denied", str(e))
            except ToolUnavailable as e:
                self._err(503, "unavailable", str(e))
            except CrystaError as e:
                self._err(400, "request_failed", str(e))
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                log.exception("unhandled error on %s %s", method, self.path)
                self._err(500, "internal_error", "Something went wrong inside Crysta. The details are in data/crysta.log.")

        def _static(self, path):
            rel = "index.html" if path in ("/", "") else path.lstrip("/")
            base = app.config.web_dir.resolve()
            f = (base / rel).resolve()
            try:
                f.relative_to(base)
            except ValueError:
                return self._err(404, "not_found", "Not found.")
            if not f.is_file() or f.suffix.lower() not in STATIC_OK:
                return self._err(404, "not_found", "Not found.")
            ctype = mimetypes.guess_type(str(f))[0] or "application/octet-stream"
            if f.suffix == ".js":
                ctype = "text/javascript"
            self._send(200, f.read_bytes(), ctype + ("; charset=utf-8" if ctype.startswith("text") else ""))

        def do_GET(self): self._dispatch("GET")
        def do_POST(self): self._dispatch("POST")
        def do_PATCH(self): self._dispatch("PATCH")
        def do_DELETE(self): self._dispatch("DELETE")

    return Handler


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False


def make_server(app, host=None, port=None):
    srv = Server((host or app.config.host, app.config.port if port is None else port), make_handler(app))
    if app.config.tls_cert and app.config.tls_key:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(app.config.tls_cert, app.config.tls_key)
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    return srv
