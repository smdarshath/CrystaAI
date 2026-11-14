"""Toolbox: every capability agents can use. Sensitive tools go through the permission layer."""
from __future__ import annotations

import logging
from pathlib import Path

from ..db import now
from ..errors import CrystaError, NeedsConfirmation, ToolUnavailable
import json
from pathlib import Path

from . import calculator, computer, hardware, project, science, system_info, voice, web_search, youtube_research
from .files import FileTools
from .offline_knowledge import KnowledgeIndex

log = logging.getLogger("crysta.tools")
ECHO_KEYS = ("speak_responses", "voice_lang", "reduce_motion")


class Toolbox:
    def __init__(self, config, db, settings, audit, perm, llm):
        self.config, self.db, self.settings, self.audit, self.perm, self.llm = config, db, settings, audit, perm, llm
        self.files = FileTools(lambda: settings.get("approved_dirs"))
        self.knowledge = KnowledgeIndex(config.knowledge_dirs, self._notes_for_search)
        self.internet_probe = lambda: None

    def call(self, tool_name, /, **kw):
        fn = getattr(self, "t_" + tool_name, None)
        if fn is None:
            raise ToolUnavailable(f"Unknown tool: {tool_name}")
        return fn(**kw)

    # ---- helpers
    def _notes_for_search(self):
        return self.db.query("SELECT id,title,body FROM notes ORDER BY id DESC LIMIT 200") if self.settings.get("memory_enabled") else []

    def _online(self):
        if not self.settings.get("internet_enabled"):
            raise ToolUnavailable("Internet access is switched off in Settings.")

    def _gate(self, tool, kwargs, description, risk="low"):
        token = self.perm.pending.add(tool, kwargs, description, risk)
        raise NeedsConfirmation(token, description, risk, tool)

    # ---- offline / math
    def t_calculator(self, text):
        return calculator.calculate(text)

    def t_offline_search(self, query, k=3):
        return self.knowledge.search(query, k)

    # ---- web
    def t_web_search(self, query):
        self._online()
        return web_search.ddg_search(query)

    def t_wiki_search(self, query):
        self._online()
        return web_search.wiki_search(query)

    def t_fetch_page(self, url):
        self._online()
        return web_search.fetch_page(url)

    def t_youtube_search(self, query):
        self._online()
        return youtube_research.search(query)

    def t_youtube_video_info(self, url):
        self._online()
        return youtube_research.video_info(url)

    def t_youtube_transcript(self, url):
        self._online()
        return youtube_research.transcript(url)

    # ---- llm
    def t_llm_status(self):
        return self.llm.status()

    def t_llm_chat(self, messages, system=None):
        return self.llm.chat(messages, system)

    # ---- files
    def _read_gate(self, tool, kwargs, desc, confirmed):
        if self.settings.level("read_files") != "allow":
            self.perm.check("read_files", tool, kwargs, desc, "low", confirmed)

    def t_files_list(self, path="~", _confirmed=False):
        self._read_gate("files_list", {"path": path}, f"List the folder {path}", _confirmed)
        return self.files.list_dir(path)

    def t_files_read(self, path, _confirmed=False):
        self._read_gate("files_read", {"path": path}, f"Read the file {path}", _confirmed)
        return self.files.read_file(path)

    def t_files_find(self, name, root=None, _confirmed=False):
        self._read_gate("files_find", {"name": name, "root": root}, f"Search your files for '{name}'", _confirmed)
        return self.files.find(name, root)

    def t_files_write(self, path, content, _confirmed=False):
        p = self.files.resolve(path)
        desc = f"Write {len(content)} characters to {p}" + (" (this OVERWRITES an existing file)" if p.exists() else "")
        self.perm.check("write_files", "files_write", {"path": path, "content": content}, desc, "medium", _confirmed)
        if p.exists():
            self.perm.check("destructive", "files_write", {"path": path, "content": content}, desc, "high", _confirmed)
        r = self.files.write_file(path, content)
        self.audit.log("vega", "files_write", r["path"], "ok" if r["verified"] else "unverified")
        return {"ok": r["verified"], "message": f"Wrote {r['bytes']} bytes to {r['path']}" + ("" if r["verified"] else " - but I could not verify it."), **r}

    def t_files_delete(self, path, _confirmed=False):
        p = self.files.resolve(path)
        self.perm.check("destructive", "files_delete", {"path": path}, f"PERMANENTLY delete the file {p}", "high", _confirmed)
        r = self.files.delete_file(path)
        self.audit.log("vega", "files_delete", r["path"], "ok" if r["verified"] else "failed")
        return {"ok": r["verified"], "message": f"Deleted {r['path']}" if r["verified"] else "I tried, but the file still exists.", **r}

    # ---- computer
    def t_open_app(self, name, _confirmed=False):
        self.perm.check("open_apps", "open_app", {"name": name}, f"Open the app '{name}'", "low", _confirmed)
        r = computer.open_app(name)
        self.audit.log("vega", "open_app", name, "ok" if r["ok"] else "failed")
        return r

    def t_open_url(self, url, _confirmed=False):
        self.perm.check("open_apps", "open_url", {"url": url}, f"Open {url} in your browser", "low", _confirmed)
        r = computer.open_url(url)
        self.audit.log("vega", "open_url", url, "ok" if r["ok"] else "failed")
        return r

    def t_run_command(self, command, _confirmed=False):
        kind, argv = computer.classify_command(command)
        if kind == "blocked":
            self.audit.log("vega", "run_command", command, "blocked")
            raise CrystaError("That command is on Crysta's never-run list (admin/destructive/system power).")
        if kind == "safe" and self.settings.level("run_commands") != "deny":
            pass
        else:
            risk = "high" if kind == "destructive" else "medium"
            self.perm.check("run_commands", "run_command", {"command": command}, f"Run command: {command}", risk, _confirmed)
            if kind == "destructive":
                self.perm.check("destructive", "run_command", {"command": command}, f"Run command that can change or remove things: {command}", "high", _confirmed)
        r = computer.run(argv)
        self.audit.log("vega", "run_command", command, "ok" if r["ok"] else "failed")
        return r

    def t_keyboard(self, action, text="", x=None, y=None, _confirmed=False):
        self.perm.check("keyboard_mouse", "keyboard", {"action": action, "text": text, "x": x, "y": y},
                        f"Keyboard/mouse action: {action} {text[:60]}", "high", _confirmed)
        r = computer.keyboard(action, text, x, y, self.config.data_dir)
        self.audit.log("vega", "keyboard:" + action, text[:60], "ok" if r["ok"] else "failed")
        return r

    def t_screenshot(self, _confirmed=False):
        return self.t_keyboard("screenshot", _confirmed=_confirmed)

    def t_system_info(self):
        return system_info.collect(self.config.data_dir, self.config.port, self.llm.available())

    # ---- project / errors
    def t_project_inspect(self, path):
        return project.inspect(self.files.resolve(path))

    def t_explain_error(self, text):
        return project.explain_error(text)

    # ---- memory (explicit opt-in)
    def _need_memory(self):
        if not self.settings.get("memory_enabled"):
            raise ToolUnavailable("Memory is switched off. Say 'turn on memory' (or use Settings) if you want me to remember things.")

    def t_memory_set_enabled(self, enabled, _confirmed=False):
        if enabled and not _confirmed:
            self._gate("memory_set_enabled", {"enabled": True},
                       "Turn on memory: Crysta will store notes, memories and chat history in a local database on this computer. You can view, export or delete it any time.")
        self.settings.set("memory_enabled", bool(enabled))
        self.audit.log("nexus", "memory_enabled", str(enabled))
        return {"ok": True, "message": "Memory is now ON." if enabled else "Memory is now OFF. Existing items stay until you delete them."}

    def t_memory_save(self, key, value):
        self._need_memory()
        rid = self.db.execute("INSERT INTO memories(key,value,created) VALUES(?,?,?)", (key[:80], value[:2000], now()))
        return {"id": rid}

    def t_memory_list(self, query=None):
        rows = self.db.query("SELECT id,key,value,created FROM memories ORDER BY id DESC LIMIT 200")
        if query:
            q = query.lower()
            rows = [r for r in rows if q in r["key"].lower() or q in r["value"].lower()]
        return rows

    def t_memory_delete(self, id=None, scope=None, _confirmed=False):
        if scope == "all":
            if not _confirmed:
                self._gate("memory_delete", {"scope": "all"}, "Permanently delete ALL saved memories, notes and chat history stored by Crysta.", "high")
            for t in ("memories", "notes", "messages", "agent_runs", "conversations"):
                self.db.execute(f"DELETE FROM {t}")
            self.audit.log("nexus", "memory_delete_all")
            return {"deleted": "all"}
        if id is not None:
            self.db.execute("DELETE FROM memories WHERE id=?", (int(id),))
            return {"deleted": int(id)}
        raise CrystaError("Say which memory to delete.")

    def t_notes_add(self, title, body, category="general", project=None):
        self._need_memory()
        return {"id": self.db.execute("INSERT INTO notes(title,body,created,category,project) VALUES(?,?,?,?,?)",
                                      (title[:80], body[:5000], now(), (category or "general")[:30], (project or None)))}

    def t_notes_update(self, id, title=None, body=None, category=None, project=None):
        self._need_memory()
        for col, val in (("title", title), ("body", body), ("category", category), ("project", project)):
            if val is not None:
                self.db.execute(f"UPDATE notes SET {col}=? WHERE id=?", (str(val)[:5000], int(id)))
        return {"id": int(id)}

    def t_notes_delete(self, id):
        self.db.execute("DELETE FROM notes WHERE id=?", (int(id),))
        return {"deleted": int(id)}

    def t_notes_list(self):
        return self.db.query("SELECT id,title,body,created,category,project FROM notes ORDER BY id DESC LIMIT 300")

    def t_memory_search(self, query):
        q = f"%{query.lower()}%"
        mem = self.db.query("SELECT id,key,value,created FROM memories WHERE lower(key) LIKE ? OR lower(value) LIKE ? ORDER BY id DESC LIMIT 30", (q, q))
        notes = self.db.query("SELECT id,title,body,created,category,project FROM notes WHERE lower(title) LIKE ? OR lower(body) LIKE ? ORDER BY id DESC LIMIT 30", (q, q))
        return {"memories": mem, "notes": notes, "knowledge": self.knowledge.search(query, 3)}

    # ---- tasks / projects
    def t_task_add(self, title, due=None, project="General", kind="task", status="pending"):
        if kind not in ("task", "milestone") or status not in ("pending", "doing", "done"):
            raise CrystaError("Invalid task type or status.")
        t = now()
        return {"id": self.db.execute("INSERT INTO tasks(title,status,due,created,updated,project,kind) VALUES(?,?,?,?,?,?,?)",
                                      (title[:200], status, due, t, t, (project or "General")[:60], kind))}

    def t_task_list(self, project=None):
        sql = "SELECT id,title,status,due,project,kind,created FROM tasks"
        rows = self.db.query(sql + (" WHERE project=?" if project else "") + " ORDER BY status='done', due IS NULL, due, id", (project,) if project else ())
        return rows

    def t_task_update(self, id, title=None, status=None, due="__keep__", project=None, kind=None):
        if status is not None and status not in ("pending", "doing", "done"):
            raise CrystaError("Invalid status.")
        if kind is not None and kind not in ("task", "milestone"):
            raise CrystaError("Invalid type.")
        sets, vals = ["updated=?"], [now()]
        for col, v in (("title", title), ("status", status), ("project", project), ("kind", kind)):
            if v is not None:
                sets.append(f"{col}=?"); vals.append(str(v)[:200])
        if due != "__keep__":
            sets += ["due=?", "notified=0"]; vals.append(due)
        self.db.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id=?", (*vals, int(id)))
        return {"id": int(id)}

    def t_task_delete(self, id):
        self.db.execute("DELETE FROM tasks WHERE id=?", (int(id),))
        return {"deleted": int(id)}

    def t_task_done(self, id):
        return self.t_task_update(id, status="done")

    def t_projects(self):
        rows = self.db.query("SELECT project, COUNT(*) AS total, SUM(status='done') AS done FROM tasks GROUP BY project ORDER BY project")
        return [{"name": r["project"], "total": r["total"], "done": r["done"] or 0} for r in rows]

    # ---- research history (stored only when memory is on)
    def t_research_history_add(self, query, kind, status, summary, sources):
        if not self.settings.get("memory_enabled"):
            return {"saved": False}
        self.db.execute("INSERT INTO research_history(query,kind,status,summary,sources,created) VALUES(?,?,?,?,?,?)",
                        (query[:300], kind, status, summary[:6000], json.dumps(sources)[:20000], now()))
        return {"saved": True}

    def t_research_history_list(self):
        rows = self.db.query("SELECT id,query,kind,status,summary,sources,created FROM research_history ORDER BY id DESC LIMIT 50")
        for r in rows:
            try:
                r["sources"] = json.loads(r["sources"] or "[]")
            except ValueError:
                r["sources"] = []
        return rows

    def t_research_history_clear(self):
        self.db.execute("DELETE FROM research_history")
        return {"cleared": True}

    # ---- hardware / science / voice / logs
    def t_hardware(self):
        return hardware.snapshot(self.internet_probe())

    def t_science_library(self):
        return {"formulas": science.library(), "subjects": science.subjects(), "topics": science.topics(self.config.knowledge_dirs)}

    def t_science_solve(self, formula, values, target):
        return science.solve(formula, values, target)

    def t_science_plot(self, expr, lo=-10.0, hi=10.0):
        return science.plot(expr, lo, hi)

    def t_voice_status(self):
        return {"tts_engine": voice.tts_engine(), "stt": voice.stt_status(self.config.data_dir.parent / "models" if False else Path(__file__).resolve().parent.parent.parent / "models")}

    def t_voice_speak(self, text, lang="en", rate=1.0):
        return voice.speak(text, lang, rate)

    def t_voice_stop(self):
        voice.stop()
        return {"ok": True}

    def t_voice_listen(self):
        return voice.listen_once(Path(__file__).resolve().parent.parent.parent / "models")

    def t_logs_tail(self, lines=200):
        from ..settings import redact
        f = self.config.data_dir / "crysta.log"
        if not f.is_file():
            return {"lines": [], "note": "No log file yet."}
        text = f.read_text(encoding="utf-8", errors="replace").splitlines()[-int(lines):]
        return {"lines": [redact(l) for l in text]}

    def t_project_commands(self, path):
        return project.suggest_commands(self.files.resolve(path))

    # ---- file manager operations (permission-gated)
    def t_files_places(self):
        roots = self.files.roots()
        return {"approved": [str(r) for r in roots], "special": self.files.special_folders(), "project": str(self.files.find_project_folder() or "")}

    def t_files_info(self, path, _confirmed=False):
        self._read_gate("files_info", {"path": path}, f"Read details of {path}", _confirmed)
        return self.files.info(path)

    def t_files_image(self, path):
        self._read_gate("files_image", {"path": path}, f"Preview {path}", False)
        return self.files.raw_image(path)

    def t_files_mkdir(self, path, _confirmed=False):
        p = self.files.resolve(path)
        self.perm.check("write_files", "files_mkdir", {"path": path}, f"Create the folder {p}", "low", _confirmed)
        r = self.files.mkdir(path)
        self.audit.log("vega", "files_mkdir", r["path"], "ok" if r["verified"] else "unverified")
        return {"ok": r["verified"], "message": f"Created folder {r['path']}", **r}

    def t_files_rename(self, path, new_name, _confirmed=False):
        p = self.files.resolve(path)
        dest = p.parent / new_name
        if dest.exists():
            raise CrystaError(f"'{new_name}' already exists in that folder. Choose a different name.")
        self.perm.check("write_files", "files_rename", {"path": path, "new_name": new_name}, f"Rename {p.name} to {new_name}", "medium", _confirmed)
        r = self.files.rename(path, new_name)
        self.audit.log("vega", "files_rename", f"{p} -> {r['path']}", "ok" if r["verified"] else "unverified")
        return {"ok": r["verified"], "message": f"Renamed to {Path(r['path']).name}", **r}

    def _copy_move(self, op, src, dst, _confirmed):
        s, d = self.files.resolve(src), self.files.resolve(dst)
        target = d / s.name if d.is_dir() else d
        overwrite = target.exists()
        if overwrite and s.is_dir():
            raise CrystaError(f"A folder named '{target.name}' already exists there. Rename or choose another destination.")
        desc = f"{'Copy' if op == 'copy' else 'Move'} {s} to {target}" + (" - this OVERWRITES an existing file" if overwrite else "")
        self.perm.check("write_files", "files_" + op, {"src": src, "dst": dst}, desc, "medium", _confirmed)
        if overwrite:
            self.perm.check("destructive", "files_" + op, {"src": src, "dst": dst}, desc, "high", _confirmed)
            target.unlink()
        r = getattr(self.files, op)(src, dst)
        self.audit.log("vega", "files_" + op, f"{s} -> {r['path']}", "ok" if r["verified"] else "unverified")
        return {"ok": r["verified"], "message": f"{'Copied' if op == 'copy' else 'Moved'} to {r['path']}", **r}

    def t_files_copy(self, src, dst, _confirmed=False):
        return self._copy_move("copy", src, dst, _confirmed)

    def t_files_move(self, src, dst, _confirmed=False):
        return self._copy_move("move", src, dst, _confirmed)

    def t_files_open(self, path, _confirmed=False):
        p = self.files.resolve(path)
        self.perm.check("open_apps", "files_open", {"path": path}, f"Open {p} with its default app", "low", _confirmed)
        r = computer.open_path(str(p))
        self.audit.log("vega", "files_open", str(p), "ok" if r["ok"] else "failed")
        return r

    # ---- voice settings (ECHO)
    def t_settings_get(self):
        return {k: self.settings.get(k) for k in ECHO_KEYS}

    def t_settings_set(self, key, value):
        if key not in ECHO_KEYS:
            raise CrystaError("Voice agent can only change voice settings.")
        self.settings.set(key, value)
        return {key: value}
