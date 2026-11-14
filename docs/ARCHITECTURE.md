# Architecture

**Desktop mode:** `desktop.py` → native window (pywebview or GTK/WebKit2) → loopback server inside the same process (session secret) → same code below. `run.py` is the server-only/browser mode.

**Lazy agents:** `agents/manifest.json` describes the nine built-in agents; each module is imported on first use. Extensions in `extensions/` are validated and opt-in.

**Workspaces:** `web/js/agents/<id>.js` + `web/css/<id>.css` are loaded on demand per agent; each builds its own layout.

```
Browser UI (web/, plain JS modules)  ──HTTP/JSON──►  crysta/server.py (stdlib ThreadingHTTPServer)
                                                         │
                                                  Coordinator ── nlp.plan()
                                                         │
                          ┌──────────┬──────────┬────────┴───┬──────────┬─────────┐
                       CRYSTA     ZYKRON      NOVA ASTRA   VEGA ECHO   NEXUS ORION VOLT   (agents/)
                          └────────────── Toolbox (tools/registry.py) ──────────────┘
                                   │ permission layer (permissions.py) + audit log
        SQLite (db.py) · files (approved dirs) · computer.py · web_search.py · youtube_research.py · llm.py (optional)
```

**Why no frameworks?** The project was built and tested in an environment without package installs. Using only the Python standard library means `python run.py` works on any machine with Python 3.9+, with nothing to install and no supply-chain surface. A React/FastAPI port is possible later; the agent/tool layers don't depend on the web layer.

**Layers of intelligence (as specified):** 1) deterministic tools (calculator, units, system info) → 2) local knowledge search (`knowledge/*.md` + your notes) → 3) optional local model (Ollama / OpenAI-compatible) → 4) web research. Without a model, open-ended reasoning is *not* faked; the app says so.

**Data:** `data/crysta.db` (SQLite, schema versioned via `PRAGMA user_version`; never reset at startup). Tables: conversations, messages, memories, notes, tasks, agent_runs, device_pairs, settings, audit_events. Chat/memory writes happen only when Memory is ON.

**Not implemented:** WebSockets (plain request/response is used), wake word, offline speech-to-text, native Android app, multi-computer companion.
