"""Agent base class, structured results and the per-request context."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import asdict, dataclass, field

from ..errors import (Cancelled, CrystaError, NeedsConfirmation, PermissionDenied, ToolNotPermitted, ToolUnavailable)

log = logging.getLogger("crysta.agents")
STATUSES = ("success", "partial", "failed", "needs_confirmation")


@dataclass
class AgentResult:
    status: str
    summary: str
    agent: str = ""
    data: dict = field(default_factory=dict)
    sources: list = field(default_factory=list)
    limitations: list = field(default_factory=list)
    ui_actions: list = field(default_factory=list)
    confirmation: dict | None = None
    speech: str = ""
    duration_ms: int = 0

    def to_dict(self):
        return asdict(self)


class AgentContext:
    def __init__(self, toolbox, settings, llm, conv, cancel=None, remote=False, can_control=False, deep=False):
        self.toolbox, self.settings, self.llm, self.conv = toolbox, settings, llm, conv
        self.cancel = cancel or threading.Event()
        self.remote, self.can_control, self.deep = remote, can_control, deep

    def check_cancel(self):
        if self.cancel.is_set():
            raise Cancelled("Cancelled.")


class Agent:
    id = ""
    name = ""
    description = ""
    system_instruction = ""
    permitted_tools: frozenset = frozenset()
    input_schema: dict = {"intent": "str", "args": "dict", "text": "str"}
    output_format = "AgentResult(status, summary, data, sources, limitations, ui_actions, confirmation)"

    def tool(self, ctx, tool_name, /, **kw):
        if tool_name not in self.permitted_tools:
            raise ToolNotPermitted(f"{self.name} is not permitted to use the tool '{tool_name}'.")
        ctx.check_cancel()
        return ctx.toolbox.call(tool_name, **kw)

    def ok(self, summary, **kw):
        return AgentResult("success", summary, **kw)

    def partial(self, summary, **kw):
        return AgentResult("partial", summary, **kw)

    def fail(self, summary, **kw):
        return AgentResult("failed", summary, **kw)

    def clarify(self, question):
        return AgentResult("partial", question, data={"clarify": True})

    def llm_answer(self, ctx, user_text, extra_context=""):
        """Ask the optional local model; returns text or None if no model is available."""
        if not ctx.llm.available():
            return None
        msgs = [m for m in ctx.conv.get("turns", [])[-6:]] + [{"role": "user", "content": (extra_context + "\n\n" if extra_context else "") + user_text}]
        return self.tool(ctx, "llm_chat", messages=msgs, system=self.system_instruction)

    def info(self):
        return {"id": self.id, "name": self.name, "description": self.description,
                "system_instruction": self.system_instruction, "permitted_tools": sorted(self.permitted_tools),
                "input_schema": self.input_schema, "output_format": self.output_format}

    def run(self, sub, ctx):
        t0 = time.time()
        handler = getattr(self, "do_" + sub.intent, None)
        try:
            if handler is None:
                res = self.fail(f"{self.name} doesn't handle '{sub.intent}'.")
            else:
                res = handler(sub, ctx)
        except NeedsConfirmation as nc:
            res = AgentResult("needs_confirmation", nc.description,
                              confirmation={"token": nc.token, "description": nc.description, "risk": nc.risk, "tool": nc.tool})
        except Cancelled:
            res = self.fail("Cancelled before it finished.")
        except PermissionDenied as e:
            res = self.fail(str(e) or "Permission denied.")
        except ToolNotPermitted as e:
            res = self.fail(str(e))
        except (ToolUnavailable, CrystaError) as e:
            res = self.fail(str(e))
        except Exception:
            log.exception("%s crashed on %s", self.name, sub.intent)
            res = self.fail(f"{self.name} hit an unexpected error. The details are in the log file.")
        res.agent = self.id
        res.duration_ms = int((time.time() - t0) * 1000)
        return res
