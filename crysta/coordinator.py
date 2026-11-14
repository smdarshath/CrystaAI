"""Coordinator: plans subtasks, runs only the needed agents (with timeouts/cancel), composes real results."""
from __future__ import annotations

import logging
import re
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout

from . import nlp
from .agents.base import AgentContext, AgentResult
from .agents.registry import Registry
from .db import now

log = logging.getLogger("crysta.coordinator")


class Coordinator:
    def __init__(self, app):
        self.app = app
        self.registry = Registry(app.config.extensions_dir, lambda: app.settings.get("extensions_enabled"))
        self.pool = ThreadPoolExecutor(max_workers=6, thread_name_prefix="agent")
        self.history = deque(maxlen=50)
        self.cancels = {}
        self.contexts = {}
        self._lock = threading.Lock()

    def conv(self, conv_id):
        with self._lock:
            if len(self.contexts) > 100:
                self.contexts.pop(next(iter(self.contexts)))
            return self.contexts.setdefault(conv_id, {"turns": [], "last_topic": "", "last_urls": [], "last_video": None, "last_subtasks": []})

    def cancel(self, conv_id=None):
        for k, ev in list(self.cancels.items()):
            if conv_id in (None, k):
                ev.set()

    # ---- running agents
    def run_agent(self, sub, ctx):
        agent = self.registry.get(sub.agent)
        fut = self.pool.submit(agent.run, sub, ctx)
        try:
            res = fut.result(timeout=self.app.config.agent_timeout)
        except FutTimeout:
            ctx.cancel.set()
            res = AgentResult("failed", f"{agent.name} took too long and was stopped.", agent=agent.id)
        self.history.append({"agent": res.agent, "intent": sub.intent, "status": res.status, "ms": res.duration_ms, "at": now()})
        return res

    def _resolve(self, subs, conv):
        out = []
        for s in subs:
            if s.intent == "follow_more":
                topic = conv.get("last_topic")
                out.append(nlp.Subtask("research", "zykron", s.text, {"query": topic, "deep": True}) if topic else s)
            elif s.intent == "follow_do":
                prev = conv.get("last_subtasks") or []
                out += [nlp.Subtask(**p) for p in prev] if prev else [s]
            else:
                out.append(s)
        return out

    def _escalate(self, res, sub, ctx):
        if res.data.get("escalate") == "research" and ctx.settings.get("internet_enabled") and not ctx.llm.available():
            q = nlp._research_query(nlp.normalize(sub.text)) or sub.text
            r2 = self.run_agent(nlp.Subtask("research", "zykron", sub.text, {"query": q}), ctx)
            r2.summary = "I don't have that offline, so I searched the web.\n\n" + r2.summary
            return r2
        return res

    # ---- main entry
    def handle(self, text, conv_id="default", remote=False, can_control=False, deep=False):
        conv = self.conv(conv_id)
        cancel = threading.Event()
        self.cancels[conv_id] = cancel
        ctx = AgentContext(self.app.toolbox, self.app.settings, self.app.llm, conv, cancel, remote, can_control, deep)
        ext = self.registry.match_extension(text)
        subs = [nlp.Subtask("run", ext, text, {})] if ext else self._resolve(nlp.plan(text, conv), conv)
        results = []
        for sub in subs:
            if cancel.is_set():
                results.append(AgentResult("failed", "Cancelled.", agent=sub.agent))
                break
            if sub.intent in ("follow_more", "follow_do"):
                r = AgentResult("partial", "Do what? I don't have anything recent to continue.", agent="crysta", data={"clarify": True})
            else:
                r = self._escalate(self.run_agent(sub, ctx), sub, ctx)
            results.append(r)
        self._update_context(conv, subs, results, text)
        out = self.compose(results)
        out["subtasks"] = [{"intent": s.intent, "agent": s.agent} for s in subs]
        self._persist(conv_id, text, out, results)
        self.cancels.pop(conv_id, None)
        return out

    def run_single(self, sub, conv_id="research", remote=False, can_control=False, deep=False):
        conv = self.conv(conv_id)
        ctx = AgentContext(self.app.toolbox, self.app.settings, self.app.llm, conv, threading.Event(), remote, can_control, deep)
        res = self.run_agent(sub, ctx)
        self._update_context(conv, [sub], [res], sub.text)
        return self.compose([res])

    # ---- composition
    def compose(self, results):
        names = [self.registry.spec(r.agent)["name"] for r in results]
        if len(results) == 1:
            reply = results[0].summary
        else:
            reply = "I used " + " and ".join(dict.fromkeys(names)) + ".\n\n" + "\n\n".join(
                f"**{self.registry.spec(r.agent)['name']}** — {r.summary}" for r in results)
        statuses = [r.status for r in results]
        if "needs_confirmation" in statuses:
            status = "needs_confirmation"
        elif all(s == "failed" for s in statuses):
            status = "failed"
        elif all(s == "success" for s in statuses):
            status = "success"
        else:
            status = "partial"
        speech = " ".join((r.speech or r.summary)[:300] for r in results if r.status != "needs_confirmation")
        if "needs_confirmation" in statuses:
            speech += " I need your confirmation on screen before I do that."
        return {"reply": reply, "status": status, "speech": speech.strip(),
                "results": [dict(r.to_dict(), agent_name=n, ui_view=self.registry.spec(r.agent)["ui"].get("view")) for r, n in zip(results, names)],
                "ui_actions": [a for r in results for a in r.ui_actions],
                "confirmations": [r.confirmation for r in results if r.confirmation],
                "limitations": [l for r in results for l in r.limitations]}

    def _update_context(self, conv, subs, results, text):
        for s, r in zip(subs, results):
            topic = r.data.get("topic") or s.args.get("query")
            if topic and r.status != "failed":
                conv["last_topic"] = topic
            urls = [x["url"] for x in r.sources if x.get("url")]
            if urls:
                conv["last_urls"] = urls
        real = [s for s in subs if s.intent not in ("greet", "thanks", "about", "ui", "follow_more", "follow_do", "chat", "offline")]
        if real:
            conv["last_subtasks"] = [{"intent": s.intent, "agent": s.agent, "text": s.text, "args": s.args} for s in real]
        conv["turns"] = (conv["turns"] + [{"role": "user", "content": text},
                         {"role": "assistant", "content": results[-1].summary[:600] if results else ""}])[-12:]

    def _persist(self, conv_id, text, out, results):
        if not self.app.settings.get("memory_enabled"):
            return
        try:
            t = now()
            db = self.app.db
            db.execute("INSERT INTO messages(conversation_id,role,content,agent,created) VALUES(?,?,?,?,?)", (conv_id, "user", text, None, t))
            db.execute("INSERT INTO messages(conversation_id,role,content,agent,created) VALUES(?,?,?,?,?)", (conv_id, "assistant", out["reply"][:8000], "crysta", t))
            for r in results:
                db.execute("INSERT INTO agent_runs(conversation_id,agent,status,summary,duration_ms,created) VALUES(?,?,?,?,?,?)",
                           (conv_id, r.agent, r.status, r.summary[:300], r.duration_ms, t))
        except Exception:
            log.exception("could not persist conversation")
