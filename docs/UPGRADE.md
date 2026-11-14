# What changed in this upgrade

Existing project upgraded in place (not rebuilt). A copy of the previous version is in `backups/pre-upgrade-*`.

## Bugs fixed (root causes found by inspection/reproduction)

- **"VEGA hit an unexpected error"** — `Agent.tool(self, ctx, name, **kw)` clashed with tools that take a `name` argument, so every *open <app>* request raised `TypeError: got multiple values for argument 'name'`. The tool-name parameter is now positional-only. A regression test checks the message. (The old test passed only because it expected *a* failure.)

- **Confirmation dialog hidden behind full-screen workspaces** (z-index) — approvals could not be clicked. Fixed.

- **Lazy loading defeated** — `status()` instantiated all agents just to count them. Fixed (verified: only used agents load).

- **`stop()` could hang forever** if the server had not started (desktop shutdown). Fixed.

- **Literal "null" text** appeared in UI panels (DOM `append(null)`). Fixed globally.

- **Incorrect routing:** "explain orbital mechanics" went to a web search; "check laptop storage" was not recognised; an explicit "research …" containing words like *website* went to NOVA; identity questions got a generic answer. Fixed + tested.

- **Unnecessary internet searches** for conversational questions (about you/the assistant) — now answered locally.

- **Irrelevant research:** results unrelated to the question are dropped; Wikipedia is background only.

- **Hardware information:** replaced the small diagnostics with real, per-metric measurements (each marked unavailable with a reason when the OS hides it).

- Friendlier file errors (missing/forbidden folders, `~` when home isn't approved).


> I had no access to your own `crysta.log`; the VEGA cause above was found by reproducing the failing request path, not from your log.


## Existing features preserved
Orb home screen, voice/text flow, chat, settings, devices/pairing, permissions & audit panel, memory, tasks/reminders, calculator, offline knowledge, run.py server mode, all earlier tests (updated only where behaviour was intentionally changed: Wikipedia no longer primary; ORION returns a labelled template plan).


## Existing files modified (40)
- `README.md`
- `crysta/agents/astra.py`
- `crysta/agents/base.py`
- `crysta/agents/crysta.py`
- `crysta/agents/echo.py`
- `crysta/agents/nexus.py`
- `crysta/agents/nova.py`
- `crysta/agents/orion.py`
- `crysta/agents/registry.py`
- `crysta/agents/vega.py`
- `crysta/agents/volt.py`
- `crysta/agents/zykron.py`
- `crysta/app.py`
- `crysta/config.py`
- `crysta/coordinator.py`
- `crysta/db.py`
- `crysta/nlp.py`
- `crysta/server.py`
- `crysta/settings.py`
- `crysta/tools/calculator.py`
- `crysta/tools/computer.py`
- `crysta/tools/files.py`
- `crysta/tools/project.py`
- `crysta/tools/registry.py`
- `crysta/tools/textutil.py`
- `crysta/tools/web_search.py`
- `docs/AGENTS.md`
- `docs/ARCHITECTURE.md`
- `docs/RESEARCH.md`
- `docs/SECURITY.md`
- `docs/TROUBLESHOOTING.md`
- `tests/test_core.py`
- `tests/test_research.py`
- `tests/test_server_ui.py`
- `web/index.html`
- `web/js/app.js`
- `web/js/dom.js`
- `web/js/speech.js`
- `web/js/views.js`
- `web/style.css`


## New files (50)
- `.env.example`
- `.github/workflows/tests.yml`
- `.gitignore`
- `LICENSE`
- `crysta/agents/manifest.json`
- `crysta/lex.py`
- `crysta/tools/hardware.py`
- `crysta/tools/science.py`
- `crysta/tools/voice.py`
- `desktop-companion/README.md`
- `desktop.py`
- `docs/DESKTOP.md`
- `docs/EXTENSIONS.md`
- `extensions/README.md`
- `extensions/example_hello/agent.json`
- `extensions/example_hello/agent.py`
- `knowledge/science_topics.md`
- `models/README.md`
- `packaging/README.md`
- `packaging/linux/install.sh`
- `packaging/macos/CRYSTA.command`
- `packaging/windows/CRYSTA.vbs`
- `packaging/windows/install.ps1`
- `phone-companion/README.md`
- `requirements-desktop.txt`
- `requirements-optional.txt`
- `scripts/ui_test.py`
- `scripts/upgrade_from.py`
- `start-server.sh`
- `start.bat`
- `start.sh`
- `tests/test_upgrade.py`
- `web/crysta.svg`
- `web/css/astra.css`
- `web/css/echo.css`
- `web/css/nexus.css`
- `web/css/nova.css`
- `web/css/orion.css`
- `web/css/vega.css`
- `web/css/volt.css`
- `web/css/workspace.css`
- `web/css/zykron.css`
- `web/js/agents/astra.js`
- `web/js/agents/echo.js`
- `web/js/agents/nexus.js`
- `web/js/agents/nova.js`
- `web/js/agents/orion.js`
- `web/js/agents/vega.js`
- `web/js/agents/volt.js`
- `web/js/agents/zykron.js`