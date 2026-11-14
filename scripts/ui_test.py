#!/usr/bin/env python3
"""End-to-end UI test (needs: pip install playwright && playwright install chromium). Starts its own isolated server.
Run: python3 scripts/ui_test.py   — it only reports a step as passed if the browser really did it."""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parent.parent
tmp = Path(tempfile.mkdtemp(prefix="crysta-ui-"))
work = tmp / "work"; work.mkdir()
(work / "hello.py").write_text('print("hello from nova")\n'); (work / "notes.txt").write_text("alpha beta gamma\n")
import base64; (work / "pic.png").write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="))
import socket
_s = socket.socket(); _s.bind(("127.0.0.1", 0)); port = _s.getsockname()[1]; _s.close()
env = dict(os.environ, CRYSTA_DATA_DIR=str(tmp / "data"), CRYSTA_PORT=str(port))
srv = subprocess.Popen([sys.executable, str(ROOT / "run.py"), "--no-browser", "--port", str(port)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=ROOT)
BASE = f"http://127.0.0.1:{port}"
def api(path, method="GET", body=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None, method=method, headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=10).read().decode())
for _ in range(40):
    try: api("/api/health"); break
    except Exception: time.sleep(0.25)
api("/api/settings", "PATCH", {"approved_dirs": [str(work)], "internet_enabled": False})
results = []
PG = {}
def reset():
    pg = PG.get("pg")
    if not pg: return
    try: pg.evaluate("(()=>{if(!document.getElementById('confirm').hidden)document.getElementById('confirm-no').click();document.querySelector('.ws-back')?.click();if(!document.getElementById('overlay').hidden)document.getElementById('close').click();})()"); pg.wait_for_timeout(300)
    except Exception: pass
def step(name, fn):
    try: fn(); results.append((name, True, ""))
    except Exception as e: results.append((name, False, str(e).splitlines()[0][:160])); reset()

def confirm(pg, approve=True):
    pg.wait_for_selector("#confirm:not([hidden])", timeout=5000); pg.click("#confirm-yes" if approve else "#confirm-no"); pg.wait_for_selector("#confirm[hidden]", state="attached", timeout=5000)

with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1366, "height": 768}); errs = []; pg.set_default_timeout(8000)
    PG['pg'] = pg
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "ERR_" not in m.text and "Failed to load resource" not in m.text else None)
    pg.goto(BASE); pg.wait_for_timeout(1200)
    def openws(a): pg.click(f"[data-open={a}]"); pg.wait_for_selector(f"#ws-{a}"); pg.wait_for_timeout(500)
    def back(): pg.click(".ws:visible .ws-back"); pg.wait_for_selector("#workspace[hidden]", state="attached")

    step("home: no textbox/sidebar, mic + 8 agent buttons", lambda: (expect(pg.locator("#home input, #home textarea")).to_have_count(0), expect(pg.locator(".hud-nav [data-open]")).to_have_count(11), expect(pg.locator("#mic")).to_be_visible()))

    # ---- VOLT
    def volt():
        openws("volt"); pg.wait_for_selector(".v-tile .g-text"); txt = pg.inner_text("#ws-volt"); assert "CPU" in txt and "MEMORY" in txt and "STORAGE" in txt
        assert "BATTERY" in txt and ("UNAVAILABLE" in txt or "%" in txt); assert pg.locator(".v-tile .g-text").first.text_content().endswith("%")
        api_mem = api("/api/hardware")["memory"]["total"]; assert str(round(api_mem / 1073741824, 1))[:2] in txt  # real total RAM shown
        back()
    step("VOLT: real CPU/RAM/storage/battery tiles, back to CRYSTA", volt)

    # ---- VEGA (default permissions: writes must ask)
    def vega():
        openws("vega"); pg.wait_for_selector(".f-row:has-text('hello.py')")
        pg.click(".f-row:has-text('notes.txt')"); pg.wait_for_selector(".f-preview pre:has-text('alpha beta')"); assert "Permissions" in pg.inner_text(".f-info") or "notes.txt" in pg.inner_text(".f-info")
        pg.click(".f-row:has-text('pic.png')"); pg.wait_for_selector(".f-preview img")
        pg.click("button:has-text('＋ Folder')"); pg.fill(".f-dbox input", "docs"); pg.click(".f-dbox button:has-text('OK')"); confirm(pg); pg.wait_for_selector(".f-row:has-text('docs')"); assert (work / "docs").is_dir()
        pg.click(".f-row:has-text('docs')"); pg.click("button:has-text('Rename')"); pg.fill(".f-dbox input", "papers"); pg.click(".f-dbox button:has-text('OK')"); confirm(pg); pg.wait_for_selector(".f-row:has-text('papers')"); assert (work / "papers").is_dir() and not (work / "docs").exists()
        pg.click(".f-row:has-text('notes.txt')"); pg.click("button:has-text('Copy')"); pg.dblclick(".f-row:has-text('papers')"); pg.wait_for_selector(".f-empty"); pg.click("button:has-text('Paste')"); confirm(pg); pg.wait_for_selector(".f-row:has-text('notes.txt')"); assert (work / "papers" / "notes.txt").read_text() == "alpha beta gamma\n"
        pg.click(".f-row:has-text('notes.txt')"); pg.click("button:has-text('Delete')"); confirm(pg, approve=False); assert (work / "papers" / "notes.txt").exists()
        pg.click("button:has-text('Delete')"); confirm(pg); pg.wait_for_selector(".f-empty"); assert not (work / "papers" / "notes.txt").exists()
        back()
    step("VEGA: browse, preview text+image, create/rename/copy/delete with confirmations (verified on disk)", vega)

    # ---- NOVA
    def nova():
        openws("nova"); pg.wait_for_selector(".n-node:has-text('hello.py')"); pg.click(".n-node:has-text('hello.py')"); pg.wait_for_selector(".n-tab.on:has-text('hello.py')")
        assert 'hello from nova' in pg.input_value(".n-ta"); assert pg.inner_text(".n-gutter").strip().startswith("1")
        pg.click("button:has-text('▶ Run')"); confirm(pg); pg.wait_for_selector(".n-termout .out:has-text('hello from nova')", timeout=8000)
        pg.fill(".n-termin", "echo terminal-works"); pg.press(".n-termin", "Enter"); pg.wait_for_selector(".n-termout .out:has-text('terminal-works')")
        (work / "bad.py").write_text("import nopkg_xyz\n"); pg.fill(".n-termin", f'python3 "{work / "bad.py"}"'); pg.press(".n-termin", "Enter"); confirm(pg)
        pg.wait_for_selector(".n-prob", timeout=8000); assert "nopkg_xyz" in pg.inner_text(".n-prob") or "install" in pg.inner_text(".n-prob").lower()
        pg.click(".n-ptab:has-text('LOGS')"); pg.wait_for_selector(".n-pane:not([hidden]) pre")
        pg.click(".n-ta"); pg.keyboard.type("# edit"); pg.click("button:has-text('💾 Save')"); confirm(pg); pg.wait_for_timeout(400)
        assert (work / "hello.py").read_text().startswith("# edit") or "# edit" in (work / "hello.py").read_text()
        back()
    step("NOVA: explorer, editor, run (confirm), terminal, error → problems explanation, logs, save", nova)

    # ---- ZYKRON (internet disabled in this test → must be honest, no fabricated results)
    def zykron():
        openws("zykron"); pg.click(".z-tab:has-text('YOUTUBE')"); assert pg.locator(".z-go").inner_text() == "FIND VIDEOS"; pg.click(".z-tab:has-text('WEB')")
        pg.fill(".z-form input", "student competitions 2026"); pg.click(".z-go"); pg.wait_for_selector(".z-status.failed", timeout=15000)
        txt = pg.inner_text(".z-answer"); assert "switched off" in txt.lower() or "internet" in txt.lower(); assert pg.locator(".z-card").count() == 0
        back()
    step("ZYKRON: tabs work; with internet off it says so and fabricates nothing", zykron)

    # ---- ASTRA
    def astra():
        openws("astra"); pg.click(".a-nav button:has-text('Electronics')"); pg.wait_for_selector(".a-read:has-text('mA')", timeout=5000)
        pg.select_option(".a-work select >> nth=0", label="Ohm's law"); pg.select_option(".a-work select >> nth=1", value="I")
        pg.fill("input[aria-label='Voltage in V']", "12"); pg.fill("input[aria-label='Resistance in Ω']", "4"); pg.click("button:has-text('SOLVE')"); pg.wait_for_selector(".a-work .a-read:has-text('I = 3')")
        pg.click(".a-nav button:has-text('Mathematics')"); pg.wait_for_selector("input[aria-label='Function of x']"); pg.fill("input[aria-label='Function of x']", "x^2-4"); pg.click("button:has-text('PLOT')"); pg.wait_for_selector(".a-read:has-text('y from')")
        pg.fill("input[aria-label='Calculator']", "20% of 150"); pg.click("button:has-text('CALCULATE')"); pg.wait_for_selector(".a-work .a-read:has-text('30')")
        pg.click(".a-nav button:has-text('Astronomy')"); pg.click(".a-ttl:has-text('Black holes')"); assert "event horizon" in pg.inner_text(".a-tbody").lower()
        back()
    step("ASTRA: diagram, formula solver (I=3 A), plotter, calculator, knowledge panel", astra)

    # ---- ECHO
    def echo():
        openws("echo"); assert "MICROPHONE" in pg.inner_text(".e-mic"); assert "null" not in pg.inner_text("#ws-echo").lower().split("language")[0]
        pg.select_option(".e-right select >> nth=1", "ta-IN"); pg.wait_for_timeout(500); assert api("/api/settings")["settings"]["voice_lang"] == "ta-IN"
        sl = pg.locator("input[aria-label=SPEED]"); sl.fill("1.5"); sl.dispatch_event("change"); pg.wait_for_timeout(500); assert api("/api/settings")["settings"]["speech_rate"] == 1.5
        pg.click("button:has-text('▶ SPEAK')"); pg.wait_for_timeout(800)   # honest result either way
        assert pg.inner_text(".e-heard").strip() != ""
        pg.select_option(".e-right select >> nth=1", "en-IN"); pg.wait_for_timeout(300); back()
    step("ECHO: mic status, language + speed persist to settings, speak test reports honestly", echo)

    # ---- NEXUS
    def nexus():
        openws("nexus"); pg.wait_for_selector(".x-banner:not([hidden])"); pg.click("button:has-text('Turn on memory')"); confirm(pg); pg.wait_for_selector(".x-banner[hidden]", state="attached")
        pg.click("button:has-text('NEW NOTE')"); pg.fill(".x-form input >> nth=0", "Rocket idea"); pg.fill(".x-form textarea", "Build a water rocket for the science fair"); pg.fill(".x-form input >> nth=1", "project"); pg.click(".x-box button:has-text('Save')")
        pg.wait_for_selector(".x-card:has-text('water rocket')"); pg.fill(".x-search", "rocket"); pg.wait_for_selector(".x-found:has-text('1 note')"); pg.fill(".x-search", "")
        pg.wait_for_timeout(500); assert pg.locator(".x-ev").count() >= 1
        pg.click(".x-card:has-text('water rocket') button:has-text('🗑')"); pg.click(".x-box button:has-text('Delete')"); pg.wait_for_selector(".x-card:has-text('water rocket')", state="detached")
        back()
    step("NEXUS: memory off banner → enable (confirm) → create/search/timeline/delete note", nexus)

    # ---- ORION
    def orion():
        openws("orion"); pg.fill("input[aria-label='New task title']", "Write report"); pg.click(".o-add button:has-text('ADD')"); pg.wait_for_selector(".o-col[data-status=pending] .o-card:has-text('Write report')")
        pg.click(".o-card:has-text('Write report') button[aria-label='Move right']"); pg.wait_for_selector(".o-col[data-status=doing] .o-card:has-text('Write report')")
        pg.click(".o-card:has-text('Write report') button[aria-label='Move right']"); pg.wait_for_selector(".o-col[data-status=done] .o-card:has-text('Write report')"); assert "100%" in pg.inner_text(".o-ring")
        pg.click("button:has-text('Generate starter plan')"); pg.wait_for_selector(".o-ms:has-text('Define the goal')"); assert pg.locator(".o-ms").count() == 6; assert pg.locator(".o-bar").count() >= 6
        pg.drag_and_drop(".o-card.ms >> nth=0", ".o-col[data-status=doing]"); pg.wait_for_selector(".o-col[data-status=doing] .o-card.ms", timeout=5000)
        back()
    step("ORION: add task, kanban moves, progress ring, starter plan roadmap + timeline, drag & drop", orion)

    # ---- routing through CRYSTA chat/voice text path
    def routing():
        pg.keyboard.press("t"); pg.wait_for_selector("input[aria-label='Message to Crysta']")
        def say(t): pg.fill("input[aria-label='Message to Crysta']", t); pg.press("input[aria-label='Message to Crysta']", "Enter"); pg.wait_for_timeout(900)
        say("What is your name?"); assert "My name is CRYSTA" in pg.inner_text(".log")
        say("Who made you?"); assert "Arshath" in pg.inner_text(".log")
        say("un peyar enna"); assert pg.inner_text(".log").count("My name is CRYSTA") >= 2
        say("open volt"); pg.wait_for_selector("#ws-volt"); back()
        pg.keyboard.press("t"); say("nova thira"); pg.wait_for_selector("#ws-nova"); back()
        pg.keyboard.press("t"); say("settings thira"); pg.wait_for_selector("#overlay[data-view=settings]"); pg.click("#close"); pg.wait_for_selector("#overlay[hidden]", state="attached")
    step("Routing: identity (English/Tanglish), 'open volt', 'nova thira', 'settings thira' open real interfaces", routing)

    def no_dup():
        for a in ["zykron","nova","astra","vega","echo","nexus","orion","volt"]:
            openws(a); assert pg.locator(".ws").count() == 1 and pg.get_attribute(".ws", "data-agent") == a; back()
    step("No agent shows another agent's interface", no_dup)
    step("No JavaScript errors during the whole run", lambda: (_ for _ in ()).throw(AssertionError("; ".join(errs[:3]))) if errs else None)
    b.close()
srv.terminate(); shutil.rmtree(tmp, ignore_errors=True)
for n, ok, why in results: print(("PASS " if ok else "FAIL ") + n + ("" if ok else f"   <- {why}"))
print(f"\n{sum(o for _, o, _ in results)}/{len(results)} UI steps passed")
sys.exit(0 if all(o for _, o, _ in results) else 1)
