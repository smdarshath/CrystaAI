"""Tests for the upgrade: root-cause regression, identity/routing (EN/Tamil/Tanglish), research ranking, hardware,
files, science, migration, lazy registry/extensions, desktop runtime."""
import http.client
import json
import os
import sqlite3
import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

from helpers import DDG_HTML, PAGE, WIKI_JSON, make_app

from crysta import lex, nlp
from crysta.agents.registry import Registry, validate_manifest
from crysta.db import Database, SCHEMA_V1
from crysta.errors import NetworkError, ToolNotPermitted
from crysta.server import make_server
from crysta.tools import hardware, science, web_search

ROOT = Path(__file__).resolve().parent.parent


class RootCauseRegression(unittest.TestCase):
    """'VEGA hit an unexpected error' came from Agent.tool(ctx, name, **kw) colliding with open_app(name=...)."""

    def test_open_app_no_longer_crashes(self):
        app = make_app()
        r = app.coordinator.handle("open totally-fake-app-xyz", "x")
        self.assertEqual(r["status"], "failed")
        self.assertNotIn("unexpected error", r["reply"].lower())
        self.assertRegex(r["reply"], r"(couldn't find|No graphical desktop)")

    def test_tools_may_take_a_name_argument(self):
        app = make_app()
        from crysta.agents.base import AgentContext
        ctx = AgentContext(app.toolbox, app.settings, app.llm, {})
        vega = app.coordinator.registry.get("vega")
        try:
            vega.tool(ctx, "open_app", name="x" * 5)
        except TypeError as e:
            self.fail(f"tool() argument collision is back: {e}")
        except Exception:
            pass  # any normal tool error is fine


class IdentityAndRouting(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.co = self.app.coordinator

    def route(self, text):
        return [(s.intent, s.agent) for s in nlp.plan(text, {})]

    def test_spec_examples(self):
        for text, agent in [("Search for student competitions", "zykron"), ("Fix Python errors", "nova"), ("Explain orbital mechanics", "astra"),
                            ("Open my project folder", "vega"), ("Find my saved project notes", "nexus"), ("Plan my project", "orion"), ("Check laptop storage", "volt")]:
            self.assertEqual(self.route(text)[0][1], agent, text)
        self.assertEqual(self.route("Change voice"), [("ui", "crysta")])

    def test_identity_answers_locally(self):
        with mock.patch.object(web_search, "http_get", side_effect=AssertionError("network must not be used")):
            r = self.co.handle("What is your name?", "i")
            self.assertEqual(r["reply"], "My name is CRYSTA.")
            r = self.co.handle("Who made you?", "i")
            self.assertEqual(r["reply"], "I was made by Arshath.")
        self.assertEqual({h["agent"] for h in self.co.history}, {"crysta"})

    def test_creator_is_configurable(self):
        app = make_app(creator="Someone Else")
        self.assertEqual(app.coordinator.handle("who created you", "i")["reply"], "I was made by Someone Else.")

    def test_tamil_and_tanglish(self):
        cases = {"un peyar enna": "identity_name", "உன் பெயர் என்ன": "identity_name", "unna yaaru senjadhu": "identity_creator", "உன்னை யார் உருவாக்கினார்": "identity_creator",
                 "maanavar pottigal thedu": "research", "மாணவர் போட்டிகள் தேடு": "research", "python error fix pannu": "code", "orbital mechanics vilakku": "science",
                 "laptop storage evlo irukku": "diagnose", "battery evlo irukku": "diagnose", "en project plan pannu": "plan", "volt kaatu": "ui", "nova thira": "ui", "home ku po": "ui"}
        for text, intent in cases.items():
            self.assertEqual(self.route(text)[0][0], intent, text)
        self.assertEqual(nlp.plan("maanavar pottigal thedu", {})[0].args["query"], "student competitions")

    def test_english_input_is_not_mangled_by_the_lexicon(self):
        for t in ("Research the best way to build my local AI website", "what is the speed of light", "open my laptop files"):
            self.assertEqual(lex.translate(t), t)

    def test_simple_conversation_never_searches(self):
        with mock.patch.object(web_search, "http_get", side_effect=AssertionError("network must not be used")):
            for t in ("how are you", "do you speak Tamil", "what can you do", "what time is it", "what is today's date", "hello", "are you online"):
                r = self.co.handle(t, "s")
                self.assertEqual([x["agent"] for x in r["results"]], ["crysta"], t)
        self.assertIn("It's", self.co.handle("what time is it", "s")["reply"])

    def test_open_each_agent_interface(self):
        for a in ("zykron", "nova", "astra", "vega", "echo", "nexus", "orion", "volt"):
            for phrase in (f"open {a}", f"{a}"):
                r = self.co.handle(phrase, "u")
                self.assertEqual(r["ui_actions"], [{"type": "open_view", "view": a}], phrase)
        for phrase, view in [("open the file manager", "vega"), ("show hardware monitor", "volt"), ("open research agent", "zykron"), ("open kanban", "orion"), ("go home", "home"), ("show agents", "agents")]:
            self.assertEqual(self.co.handle(phrase, "u")["ui_actions"][0]["view"], view, phrase)

    def test_each_result_knows_its_interface(self):
        r = self.co.handle("calculate 2+2", "u")
        self.assertEqual(r["results"][0]["ui_view"], "astra")


class ZykronUpgrade(unittest.TestCase):
    OFFICIAL = "<html><head><title>National Science Olympiad 2026 - Registration</title></head><body><p>The National Science Olympiad for students opens registration soon. The last date to apply is 15 March 2026 for all student teams.</p><a href='/register'>Register now</a><a href='/about'>About us</a></body></html>"
    BLOG = "<html><head><title>Student competitions blog</title></head><body><p>Student competitions are fun events. The deadline is 30 March 2026 according to some people.</p></body></html>"
    DDG = ('<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fblog.example.com%2Fcomps">Student competitions blog</a><a class="result__snippet">Student competitions are fun.</a>'
           '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Folympiad.science.gov%2Fnso">National Science Olympiad 2026 student competition</a><a class="result__snippet">Official student competition registration.</a>'
           '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.quora.com%2Fq">Student competitions quora</a><a class="result__snippet">Student competitions what are they</a>'
           '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fcars.example.net%2Fx">Used cars for sale</a><a class="result__snippet">Cheap cars and trucks</a>')

    def setUp(self):
        self.app = make_app()
        for p in (mock.patch.object(web_search, "is_public_url", return_value=True), mock.patch.object(web_search, "robots_allows", return_value=True)):
            p.start(); self.addCleanup(p.stop)

        def get(url, **kw):
            routes = {"duckduckgo": self.DDG, "olympiad.science.gov": self.OFFICIAL, "blog.example.com": self.BLOG, "wikipedia.org/w/api": WIKI_JSON}
            for k, v in routes.items():
                if k in url:
                    return {"status": 200, "text": v, "content_type": "text/html", "url": url, "truncated": False}
            raise NetworkError("no route " + url)
        p = mock.patch.object(web_search, "http_get", get); p.start(); self.addCleanup(p.stop)

    def test_official_first_irrelevant_dropped_dates_and_registration_found(self):
        r = self.app.coordinator.handle("Search for student competitions", "z")
        res = r["results"][0]
        cards = res["data"]["cards"]
        self.assertEqual(cards[0]["host"], "olympiad.science.gov")
        self.assertEqual(cards[0]["tier"], "official")
        self.assertFalse(any("cars" in c["host"] for c in cards), "irrelevant result must be dropped")
        self.assertTrue(any("15 March 2026" in d for d in cards[0]["deadlines"]))
        self.assertTrue(any(l["href"].endswith("/register") for l in cards[0]["reg_links"]))
        self.assertIn("Registration / application links", res["summary"])
        self.assertIn("Key dates found", res["summary"])
        self.assertIn("different dates", res["summary"])       # 15 March (official) vs 30 March (blog) is surfaced, not hidden
        self.assertIn("Verification", res["summary"])
        self.assertTrue(any("dropped as not relevant" in l for l in res["limitations"]))

    def test_wikipedia_is_never_primary(self):
        r = self.app.coordinator.handle("research black holes", "w")   # only DDG junk + wiki available
        cards = r["results"][0]["data"]["cards"]
        wiki = [c for c in cards if "wikipedia" in c["host"]]
        self.assertTrue(all(c["tier"].startswith("encyclopedia") for c in wiki))
        self.assertNotEqual(r["results"][0]["status"], "success")        # background alone is not enough for 'success'

    def test_competition_query_gets_year_and_official_search_terms(self):
        seen = []
        orig = web_search.http_get
        def spy(url, **kw):
            seen.append((kw.get("data") or b"").decode()); return orig(url, **kw)
        with mock.patch.object(web_search, "http_get", spy):
            self.app.coordinator.handle("search for student competitions", "q")
        joined = " ".join(seen)
        self.assertIn("official", joined)
        self.assertIn("registration", joined)


class HardwareTests(unittest.TestCase):
    def test_snapshot_is_real_or_explicitly_unavailable(self):
        s = hardware.snapshot(True)
        total = s["memory"]["total"]
        if sys.platform.startswith("linux"):
            meminfo = int(next(l for l in open("/proc/meminfo") if l.startswith("MemTotal")).split()[1]) * 1024
            self.assertEqual(total, meminfo)
        self.assertTrue(s["disks"])
        import shutil
        d = shutil.disk_usage(s["disks"][0]["mount"])
        self.assertEqual(s["disks"][0]["total"], d.total)
        for key in ("usage", "temperature", "model"):
            m = s["cpu"][key]
            self.assertTrue(m["available"] or m["reason"], key)       # never a bare/invented value
            if not m["available"]:
                self.assertIsNone(m["value"])
        b = s["battery"]
        self.assertTrue(b["available"] or b["reason"])
        if b["available"]:
            self.assertTrue(0 <= b["percent"] <= 100)
        self.assertEqual(s["system"]["architecture"], __import__("platform").machine())
        self.assertEqual(s["system"]["cores_logical"], os.cpu_count())

    def test_volt_reports_unavailable_honestly(self):
        app = make_app()
        fake = hardware.snapshot(True)
        fake["battery"] = {"available": False, "reason": "No battery exposed (test)."}
        fake["cpu"]["temperature"] = {"available": False, "value": None, "unit": None, "reason": "No sensor (test)."}
        with mock.patch.object(hardware, "snapshot", return_value=fake):
            r = app.coordinator.handle("check laptop storage", "v")
        self.assertIn("Battery: unavailable (No battery exposed (test).)", r["reply"])
        self.assertIn("unavailable (No sensor (test).)", r["reply"])
        self.assertEqual(r["results"][0]["agent"], "volt")


class FileManagerOps(unittest.TestCase):
    def setUp(self):
        self.app = make_app(); self.w = self.app.tmp / "work"; self.t = self.app.toolbox
        self.app.settings.set("autonomy", "trusted")    # skip routine prompts; destructive ones must still ask

    def test_create_rename_copy_move(self):
        self.assertTrue(self.t.call("files_mkdir", path="a")["ok"])
        (self.w / "a" / "f.txt").write_text("hi")
        self.assertTrue(self.t.call("files_rename", path="a/f.txt", new_name="g.txt")["ok"])
        self.assertTrue(self.t.call("files_copy", src="a/g.txt", dst="a/h.txt")["ok"])
        self.t.call("files_mkdir", path="b")
        self.assertTrue(self.t.call("files_move", src="a/h.txt", dst="b")["ok"])
        self.assertEqual((self.w / "b" / "h.txt").read_text(), "hi")
        self.assertFalse((self.w / "a" / "h.txt").exists())

    def test_rename_never_overwrites(self):
        (self.w / "x").write_text("1"); (self.w / "y").write_text("2")
        from crysta.errors import CrystaError
        with self.assertRaises(CrystaError):
            self.t.call("files_rename", path="x", new_name="y")
        self.assertEqual((self.w / "y").read_text(), "2")

    def test_copy_over_existing_file_asks(self):
        from crysta.errors import NeedsConfirmation
        (self.w / "x").write_text("new"); (self.w / "y").write_text("old")
        with self.assertRaises(NeedsConfirmation):
            self.t.call("files_copy", src="x", dst="y")
        self.assertEqual((self.w / "y").read_text(), "old")

    def test_delete_rules(self):
        from crysta.errors import CrystaError, NeedsConfirmation
        (self.w / "full").mkdir(); (self.w / "full" / "f").write_text("x"); (self.w / "empty").mkdir()
        with self.assertRaises(NeedsConfirmation):
            self.t.call("files_delete", path="empty")
        self.t.call("files_delete", path="empty", _confirmed=True)
        self.assertFalse((self.w / "empty").exists())
        with self.assertRaises(CrystaError):
            self.t.call("files_delete", path="full", _confirmed=True)       # non-empty folders are refused outright
        self.assertTrue((self.w / "full" / "f").exists())

    def test_outside_approved_and_info_and_image(self):
        from crysta.errors import PathNotAllowed
        with self.assertRaises(PathNotAllowed):
            self.t.call("files_mkdir", path="../escape")
        (self.w / "p.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 20); (self.w / "n.txt").write_text("x")
        self.assertEqual(self.t.call("files_image", path="p.png")[0], "image/png")
        from crysta.errors import CrystaError
        with self.assertRaises(CrystaError):
            self.t.call("files_image", path="n.txt")
        info = self.t.call("files_info", path="n.txt")
        self.assertEqual((info["name"], info["size"], info["type"]), ("n.txt", 1, "file"))

    def test_project_folder_found_by_name(self):
        (self.w / "my-project-x").mkdir()
        self.assertTrue(self.t.call("files_places")["project"].endswith("my-project-x"))
        r = self.app.coordinator.handle("open my project folder", "p")
        self.assertIn("my-project-x", r["reply"])


class ScienceTests(unittest.TestCase):
    def test_solver_values(self):
        self.assertAlmostEqual(science.solve("escape_velocity", {"M": 5.972e24, "r": 6.371e6}, "v")["result"], 11186, delta=2)
        self.assertAlmostEqual(science.solve("ohm", {"V": 12, "R": 4}, "I")["result"], 3.0)
        self.assertAlmostEqual(science.solve("schwarzschild", {"M": 1.989e30}, "rs")["result"], 2953, delta=2)
        self.assertAlmostEqual(science.solve("orbital_period", {"a": 1.495978707e11, "M": 1.989e30}, "T")["result"] / 86400, 365.25, delta=0.5)
        self.assertAlmostEqual(science.solve("ideal_gas", {"V": 0.0224, "n": 1, "T": 273.15}, "P")["result"], 101325, delta=300)

    def test_solver_errors_are_clear(self):
        from crysta.errors import CrystaError
        with self.assertRaises(CrystaError):
            science.solve("ohm", {"V": 12}, "I")
        with self.assertRaises(CrystaError):
            science.solve("ohm", {"V": 12, "R": 0}, "I")
        with self.assertRaises(CrystaError):
            science.solve("nope", {}, "x")

    def test_plot_is_safe(self):
        self.assertEqual(len(science.plot("x^2", -2, 2, 4)["points"]), 5)
        from crysta.errors import CrystaError
        with self.assertRaises(CrystaError):
            science.plot("__import__('os').system('echo hi')")

    def test_topics_and_library_cover_subjects(self):
        lib = make_app().toolbox.call("science_library")
        self.assertTrue({"Astronomy", "Electronics", "Mechanics", "Mathematics"} <= set(lib["subjects"]))
        self.assertTrue(any("Kepler" in t["title"] for t in lib["topics"]))


class MigrationTests(unittest.TestCase):
    def test_v1_database_is_upgraded_without_losing_data(self):
        import tempfile
        d = Path(tempfile.mkdtemp()) / "crysta.db"
        con = sqlite3.connect(d); con.executescript(SCHEMA_V1); con.execute("PRAGMA user_version=1")
        con.execute("INSERT INTO notes(title,body,created) VALUES('old','kept note',1)"); con.execute("INSERT INTO tasks(title,status,created,updated) VALUES('old task','pending',1,1)")
        con.execute("INSERT INTO settings(key,value) VALUES('user_name','\"Keep Me\"')"); con.commit(); con.close()
        db = Database(d)
        self.assertEqual(db.one("SELECT body,category FROM notes")["body"], "kept note")
        self.assertEqual(db.one("SELECT project,kind FROM tasks")["project"], "General")
        self.assertEqual(db.one("SELECT value FROM settings WHERE key='user_name'")["value"], '"Keep Me"')
        self.assertTrue(d.with_name("crysta.db.bak-v1").exists(), "a backup of the old database must be kept")
        self.assertEqual(db.one("PRAGMA user_version")["user_version"], 2)
        db.close(); Database(d).close()   # reopening an upgraded DB is a no-op


class RegistryTests(unittest.TestCase):
    def mk_ext(self, root, name, manifest=None, code=None):
        d = root / name; d.mkdir(parents=True)
        m = {"id": "weather", "name": "Weather", "description": "x", "module": "agent.py", "class": "WeatherAgent", "ui": {"title": "Weather"},
             "capabilities": ["forecast"], "permissions": ["calculator"], "triggers": ["weather forecast"]}
        m.update(manifest or {})
        (d / "agent.json").write_text(json.dumps(m))
        (d / "agent.py").write_text(code or "from crysta.agents.base import Agent\nclass WeatherAgent(Agent):\n    system_instruction='w'\n    def do_run(self, sub, ctx):\n        return self.ok('sunny (extension)')\n")
        return d

    def test_builtin_agents_are_lazy(self):
        reg = Registry()
        self.assertEqual(reg.loaded_ids(), [])
        self.assertEqual(len(reg.listing()), 9)
        reg.get("volt")
        self.assertEqual(reg.loaded_ids(), ["volt"])

    def test_status_and_listing_do_not_load_agents(self):
        app = make_app()
        app.status(); app.coordinator.registry.listing()
        self.assertEqual(app.coordinator.registry.loaded_ids(), [])
        app.coordinator.handle("calculate 1+1", "l")
        self.assertEqual(app.coordinator.registry.loaded_ids(), ["astra"])

    def test_manifest_validation(self):
        import tempfile
        base = Path(tempfile.mkdtemp()); (base / "agent.py").write_text("x=1")
        good = {"id": "my_agent", "name": "A", "description": "d", "module": "agent.py", "class": "A", "ui": {"title": "t"}, "capabilities": [], "permissions": ["calculator"]}
        self.assertEqual(validate_manifest(good, base), [])
        bad = [dict(good, id="Bad Id"), dict(good, id="vega"), dict(good, permissions=["run_command_anything"]), dict(good, module="../evil.py"),
               dict(good, module="missing.py"), dict(good, **{"class": "not valid"}), {k: v for k, v in good.items() if k != "ui"}, dict(good, triggers=["x"] * 20)]
        for b in bad:
            self.assertTrue(validate_manifest(b, base, builtin_ids={"vega"}), b)

    def test_extension_loads_only_when_valid_and_enabled(self):
        import tempfile
        ext = Path(tempfile.mkdtemp()); self.mk_ext(ext, "weather"); self.mk_ext(ext, "broken", {"id": "BAD ID"})
        enabled = []
        reg = Registry(ext, lambda: enabled)
        rep = {r["folder"]: r for r in reg.extension_report}
        self.assertTrue(rep["weather"]["valid"] and not rep["weather"]["enabled"])
        self.assertFalse(rep["broken"]["valid"])
        self.assertNotIn("weather", reg.ids())
        with self.assertRaises(KeyError):
            reg.get("weather")
        enabled.append("weather"); reg.scan_extensions()
        self.assertIn("weather", reg.ids())
        self.assertEqual(reg.get("weather").permitted_tools, frozenset({"calculator"}))   # manifest permissions are enforced
        self.assertEqual(reg.match_extension("what's the weather forecast"), "weather")

    def test_extension_is_routed_by_the_coordinator_and_cannot_use_other_tools(self):
        import tempfile
        ext = Path(tempfile.mkdtemp())
        self.mk_ext(ext, "weather", code="from crysta.agents.base import Agent\nclass WeatherAgent(Agent):\n    system_instruction='w'\n    def do_run(self, sub, ctx):\n        self.tool(ctx, 'run_command', command='ls')\n        return self.ok('x')\n")
        app = make_app(extensions_dir=ext); app.settings.set("extensions_enabled", ["weather"]); app.coordinator.registry.scan_extensions()
        r = app.coordinator.handle("weather forecast please", "e")
        self.assertEqual(r["results"][0]["agent"], "weather")
        self.assertEqual(r["status"], "failed")
        self.assertIn("not permitted", r["reply"])


class OfflineBehaviour(unittest.TestCase):
    def test_local_features_work_with_internet_off(self):
        app = make_app(); app.settings.set("internet_enabled", False)
        with mock.patch.object(web_search, "http_get", side_effect=AssertionError("no network")):
            for text in ("calculate 12*12", "check laptop storage", "list files in .", "what time is it", "what is your name", "explain orbital mechanics", "plan my project", "remind me to rest in 5 minutes"):
                r = app.coordinator.handle(text, "o")
                self.assertNotEqual(r["status"], "failed", text)
            r = app.coordinator.handle("research black holes", "o")
        self.assertEqual(r["status"], "failed"); self.assertIn("switched off", r["reply"])


class VoiceEndpoints(unittest.TestCase):
    def test_no_fake_voice_endpoints(self):
        app = make_app()
        srv = make_server(app, "127.0.0.1", 0); threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            def post(path):
                c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1]); c.request("POST", path, "{}" if path != "/api/voice/speak" else json.dumps({"text": "hi"}), {"Content-Type": "application/json"})
                r = c.getresponse(); return r.status, json.loads(r.read())
            from crysta.tools import voice
            if not voice.tts_engine():
                st, body = post("/api/voice/speak")
                self.assertEqual((st, body["error"]["code"]), (501, "not_available"))
            st, body = post("/api/voice/listen")
            if not voice.stt_status(ROOT / "models")["available"]:
                self.assertEqual((st, body["error"]["code"]), (501, "not_available"))
        finally:
            srv.shutdown(); srv.server_close()


class DesktopRuntime(unittest.TestCase):
    def test_lifecycle_session_secret_and_clean_shutdown(self):
        import importlib, tempfile
        os.environ["CRYSTA_DATA_DIR"] = tempfile.mkdtemp()
        sys.path.insert(0, str(ROOT))
        desktop = importlib.import_module("desktop")
        rt = desktop.Runtime(); url = rt.start()
        try:
            c = http.client.HTTPConnection("127.0.0.1", rt.port, timeout=5)
            c.request("GET", "/api/status"); r = c.getresponse(); r.read(); self.assertEqual(r.status, 401)   # other local programs are locked out
            c.request("GET", "/"); r = c.getresponse(); r.read(); self.assertEqual(r.status, 401)
            c.request("GET", "/?s=wrong"); r = c.getresponse(); r.read(); self.assertEqual(r.status, 401)
            c.request("GET", "/?s=" + rt.cfg.session_token); r = c.getresponse(); r.read()
            self.assertEqual(r.status, 302)
            cookie = r.getheader("Set-Cookie").split(";")[0]
            self.assertIn("HttpOnly", r.getheader("Set-Cookie"))
            c.request("GET", "/api/status", headers={"Cookie": cookie}); r = c.getresponse(); r.read(); self.assertEqual(r.status, 200)
            c.request("GET", "/", headers={"Cookie": cookie}); r = c.getresponse(); self.assertIn(b"CRYSTA AI", r.read())
            self.assertTrue(rt.lock.exists())
            with self.assertRaises(RuntimeError):                # a second window/instance is refused with a clear message
                desktop.Runtime()
        finally:
            rt.stop()
        self.assertFalse(rt.lock.exists())
        import socket
        with self.assertRaises(OSError):
            socket.create_connection(("127.0.0.1", rt.port), timeout=1)
        rt.stop()   # stopping twice is safe
        del os.environ["CRYSTA_DATA_DIR"]

    def test_gui_detection_and_error_helper_do_not_crash(self):
        import importlib
        sys.path.insert(0, str(ROOT))
        desktop = importlib.import_module("desktop")
        gui, label = desktop.available_gui()
        self.assertIn(gui, (None, "webview", "gtk"))
        with mock.patch.object(desktop.subprocess, "run"), mock.patch("shutil.which", return_value=None):
            desktop.show_error("t", "m")

    def test_data_dir_prefers_existing_portable_folder(self):
        from crysta.config import ROOT as R, default_data_dir
        self.assertEqual(default_data_dir(), R / "data")


if __name__ == "__main__":
    unittest.main()
