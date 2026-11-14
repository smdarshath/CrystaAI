import http.client
import json
import threading
import unittest
from html.parser import HTMLParser
from pathlib import Path

from helpers import make_app

from crysta.server import make_server

WEB = Path(__file__).resolve().parent.parent / "web"


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = make_app()
        cls.srv = make_server(cls.app, "127.0.0.1", 0)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.srv.server_close()

    def req(self, method, path, body=None, headers=None, raw=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        h = dict(headers or {})
        data = raw if raw is not None else (json.dumps(body) if body is not None else None)
        if data is not None:
            h.setdefault("Content-Type", "application/json")
        c.request(method, path, data, h)
        r = c.getresponse()
        txt = r.read().decode()
        try:
            return r.status, json.loads(txt)
        except ValueError:
            return r.status, txt

    def test_health_and_status(self):
        self.assertEqual(self.req("GET", "/api/health")[1]["status"], "ok")
        s = self.req("GET", "/api/status")[1]
        self.assertEqual(s["agents"], 9)
        self.assertIn("llm", s)

    def test_chat_roundtrip(self):
        st, d = self.req("POST", "/api/chat", {"message": "calculate 12*12"})
        self.assertEqual((st, d["reply"]), (200, "12*12 = 144"))

    def test_agents_endpoint(self):
        self.assertEqual(len(self.req("GET", "/api/agents")[1]["agents"]), 9)

    def test_error_responses_are_consistent(self):
        st, d = self.req("POST", "/api/chat", raw="{not json")
        self.assertEqual((st, d["error"]["code"]), (400, "bad_json"))
        st, d = self.req("POST", "/api/chat", {"message": ""})
        self.assertEqual((st, d["error"]["code"]), (400, "bad_request"))
        st, d = self.req("POST", "/api/chat", {"message": "x" * 3000})
        self.assertEqual(st, 400)
        st, d = self.req("POST", "/api/chat", raw="x" * 70000)
        self.assertEqual(st, 413)
        st, d = self.req("GET", "/api/nope")
        self.assertEqual((st, d["error"]["code"]), (404, "not_found"))
        st, d = self.req("PATCH", "/api/settings", {"perm.destructive": "allow"})
        self.assertEqual(st, 400)
        st, d = self.req("PATCH", "/api/settings", {"evil": 1})
        self.assertEqual(st, 400)

    def test_no_tracebacks_leak(self):
        orig = self.app.coordinator.handle
        self.app.coordinator.handle = lambda *a, **k: 1 / 0
        try:
            st, d = self.req("POST", "/api/chat", {"message": "hi"})
        finally:
            self.app.coordinator.handle = orig
        self.assertEqual(st, 500)
        self.assertNotIn("ZeroDivision", json.dumps(d))
        self.assertNotIn("Traceback", json.dumps(d))

    def test_host_header_and_origin_checks(self):
        self.assertEqual(self.req("GET", "/api/health", headers={"Host": "evil.example.com"})[0], 403)
        st, _ = self.req("POST", "/api/chat", {"message": "hi"}, headers={"Origin": "https://evil.example.com"})
        self.assertEqual(st, 403)

    def test_static_files_and_traversal(self):
        st, html = self.req("GET", "/")
        self.assertEqual(st, 200)
        self.assertIn("CRYSTA AI", html)
        self.assertEqual(self.req("GET", "/js/app.js")[0], 200)
        self.assertEqual(self.req("GET", "/../crysta/config.py")[0], 404)
        self.assertEqual(self.req("GET", "/%2e%2e/crysta/config.py")[0], 404)
        self.assertEqual(self.req("GET", "/data/crysta.db")[0], 404)

    def test_pairing_over_http(self):
        code = self.req("POST", "/api/devices/pair-code", {})[1]["code"]
        st, d = self.req("POST", "/api/pair/request", {"code": code, "name": "Phone"})
        self.assertEqual(st, 200)
        rid = d["request_id"]
        self.assertEqual(self.req("GET", f"/api/devices")[1]["pending"][0]["id"], rid)
        self.req("POST", "/api/devices/decide", {"id": rid, "approve": True})
        self.assertEqual(self.req("GET", f"/api/pair/status?id={rid}")[1]["status"], "approved")
        st, d = self.req("POST", "/api/pair/request", {"code": "123456", "name": "x"})
        self.assertEqual(st, 403)

    def test_remote_access_rules(self):
        """Simulate non-local callers by calling the handler's auth logic through the pairing/verify layer."""
        app = self.app
        rid = app.pairing.submit(app.pairing.create_code()["code"], "Tablet", "10.0.0.5")
        app.pairing.decide(rid, True, can_control=False)
        tok = app.pairing.status(rid)["token"]
        dev = app.pairing.verify(tok)
        self.assertEqual(dev["can_control"], 0)
        self.assertIsNone(app.pairing.verify("garbage"))
        from crysta.server import LOCAL_ONLY, PUBLIC
        for key in (("PATCH", "/api/settings"), ("POST", "/api/devices/pair-code"), ("GET", "/api/audit"), ("GET", "/api/memory"), ("POST", "/api/emergency-stop")):
            self.assertIn(key, LOCAL_ONLY)
        self.assertNotIn(("POST", "/api/chat"), PUBLIC)

    def test_tasks_due_ack(self):
        import time
        app = self.app
        tid = app.toolbox.call("task_add", title="due now", due=time.time() - 1)["id"]
        self.assertTrue(any(t["id"] == tid for t in self.req("GET", "/api/tasks/due")[1]["due"]))
        self.req("POST", "/api/tasks/ack", {"id": tid})
        self.assertFalse(any(t["id"] == tid for t in self.req("GET", "/api/tasks/due")[1]["due"]))

    def test_memory_controls(self):
        self.app.settings.set("memory_enabled", True)
        self.app.toolbox.call("memory_save", key="k", value="v")
        self.assertTrue(self.req("GET", "/api/memory/export")[1]["memories"])
        self.req("DELETE", "/api/memory", {"scope": "all"})
        self.assertEqual(self.req("GET", "/api/memory")[1]["memories"], [])
        self.app.settings.set("memory_enabled", False)


class _Scan(HTMLParser):
    def __init__(self):
        super().__init__(); self.inputs, self.ids, self.in_home = [], set(), 0; self.depth = 0; self.stack = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("area", "br", "img", "input", "link", "meta", "i", "path"):
            if tag == "input" or tag == "textarea":
                self.inputs.append(tag)
            if a.get("id"): self.ids.add(a["id"])
            return
        self.stack.append(a.get("id"))
        if a.get("id"): self.ids.add(a["id"])
        if tag in ("textarea", "select"): self.inputs.append(tag)

    def handle_endtag(self, tag):
        if self.stack and tag not in ("area", "br", "img", "input", "link", "meta", "i", "path"): self.stack.pop()


class UiStaticTests(unittest.TestCase):
    def setUp(self):
        self.html = (WEB / "index.html").read_text()
        self.scan = _Scan(); self.scan.feed(self.html)

    def test_home_has_no_chat_textbox_sidebar_or_profile(self):
        self.assertEqual(self.scan.inputs, [], "home page must contain no text inputs at all")
        for banned in ("<textarea", "<input", 'class="sidebar"', "profile", "<aside class=\"nav"):
            self.assertNotIn(banned, self.html.lower() if banned != "<input" else self.html)

    def test_voice_and_keyboard_controls_exist(self):
        for needed in ('id="mic"', 'aria-pressed="false"', 'data-open="chat"', 'id="caption"', 'aria-live="polite"', 'id="state-label"', 'id="chip-mic"', 'id="chip-net"'):
            self.assertIn(needed, self.html)
        self.assertIn("Created by Arshath", self.html)

    def test_secondary_views_exist_and_inputs_only_there(self):
        js = (WEB / "js" / "views.js").read_text()
        for v in ("chat", "agents", "research", "devices", "computer", "settings"):
            self.assertIn(f"{v}", js)
        self.assertIn("input", js)
        self.assertIn("openView", (WEB / "js" / "app.js").read_text())
        self.assertIn("closeView", (WEB / "js" / "app.js").read_text())

    def test_states_and_fallbacks_are_implemented(self):
        app = (WEB / "js" / "app.js").read_text()
        for s in ("LISTENING", "PROCESSING", "SPEAKING", "BACKEND OFFLINE", "ERROR", "NET · ONLINE", "NET · OFFLINE", "UNAVAILABLE"):
            self.assertIn(s, app)
        self.assertIn("press T to type", app)          # voice-unavailable fallback
        self.assertIn("onstart", (WEB / "js" / "speech.js").read_text())  # mic state only shown after real onstart
        browser_path = app.split("function toggleMic")[1].split("speech.stopSpeaking();")[1].split("speech.listen")[0]
        self.assertNotIn("setMode('listening')", browser_path)  # browser recogniser: only after its real onstart event

    def test_responsive_and_reduced_motion_css(self):
        css = (WEB / "style.css").read_text()
        self.assertIn("@media (max-width:560px)", css)
        self.assertIn("prefers-reduced-motion", css)
        self.assertIn("reduce-motion", css)

    def test_no_inline_script_or_innerhtml(self):
        self.assertNotIn("<script>", self.html)
        for f in (WEB / "js").glob("*.js"):
            self.assertIsNone(__import__("re").search(r"\.innerHTML|insertAdjacentHTML|document\.write|eval\(", f.read_text()), f.name)


if __name__ == "__main__":
    unittest.main()
