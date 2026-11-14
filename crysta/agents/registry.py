"""Agent registry: manifest-driven, lazy-loading, with validated third-party extensions.

Built-in agents are described in manifest.json and imported only when first used (saves RAM on small machines).
Extensions live in extensions/<folder>/agent.json and are loaded only if validated AND enabled in Settings."""
from __future__ import annotations

import importlib
import importlib.util
import inspect
import json
import logging
import re
from pathlib import Path

from .base import Agent

log = logging.getLogger("crysta.registry")
ROOT = Path(__file__).resolve().parent
REQUIRED = ("id", "name", "description", "module", "class", "ui", "capabilities", "permissions")
ID_RE = re.compile(r"^[a-z][a-z0-9_]{2,19}$")


def known_tools():
    from ..tools.registry import Toolbox
    return {n[2:] for n in dir(Toolbox) if n.startswith("t_")}


def validate_manifest(m, base_dir, builtin_ids=()):
    """Return a list of problems (empty list = valid)."""
    errs = []
    if not isinstance(m, dict):
        return ["manifest must be a JSON object"]
    for k in REQUIRED:
        if k not in m:
            errs.append(f"missing '{k}'")
    if errs:
        return errs
    if not isinstance(m["id"], str) or not ID_RE.match(m["id"]):
        errs.append("id must be 3-20 chars: lowercase letters, digits, underscore, starting with a letter")
    if m.get("id") in builtin_ids:
        errs.append("id clashes with a built-in agent")
    for k in ("name", "description"):
        if not isinstance(m[k], str) or not (0 < len(m[k]) <= 300):
            errs.append(f"'{k}' must be a short string")
    if not isinstance(m["ui"], dict) or not isinstance(m["ui"].get("title"), str):
        errs.append("ui must be an object with a title")
    if not isinstance(m["capabilities"], list) or not all(isinstance(c, str) for c in m["capabilities"]):
        errs.append("capabilities must be a list of strings")
    perms = m["permissions"]
    if not isinstance(perms, list) or not all(isinstance(p, str) for p in perms):
        errs.append("permissions must be a list of tool names")
    else:
        unknown = set(perms) - known_tools()
        if unknown:
            errs.append("unknown tools requested: " + ", ".join(sorted(unknown)))
    if not isinstance(m["module"], str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*\.py", m["module"]):
        errs.append("module must be a plain .py file name inside the extension folder")
    elif not (Path(base_dir) / m["module"]).is_file():
        errs.append(f"module file {m['module']} not found")
    if not isinstance(m["class"], str) or not m["class"].isidentifier():
        errs.append("class must be a Python class name")
    trig = m.get("triggers", [])
    if not isinstance(trig, list) or len(trig) > 10 or not all(isinstance(t, str) and 2 <= len(t) <= 40 for t in trig):
        errs.append("triggers must be up to 10 short phrases")
    return errs


class Registry:
    def __init__(self, extensions_dir=None, enabled=lambda: []):
        self.specs = {m["id"]: dict(m, builtin=True) for m in json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))}
        self._loaded = {}
        self.extensions_dir = Path(extensions_dir) if extensions_dir else None
        self._enabled = enabled
        self.extension_report = []
        self.scan_extensions()

    # ---- extensions
    def scan_extensions(self):
        for sid in [i for i, s in self.specs.items() if not s.get("builtin")]:
            self.specs.pop(sid); self._loaded.pop(sid, None)
        self.extension_report = []
        if not self.extensions_dir or not self.extensions_dir.is_dir():
            return
        for d in sorted(p for p in self.extensions_dir.iterdir() if p.is_dir()):
            f = d / "agent.json"
            if not f.is_file():
                continue
            try:
                m = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError) as e:
                self.extension_report.append({"folder": d.name, "valid": False, "errors": [f"agent.json unreadable: {e}"]})
                continue
            errs = validate_manifest(m, d, {i for i, s in self.specs.items() if s.get("builtin")})
            if not errs and m["id"] in self.specs:
                errs = ["duplicate extension id"]
            rep = {"folder": d.name, "id": m.get("id"), "valid": not errs, "errors": errs, "enabled": False}
            if not errs:
                rep["enabled"] = m["id"] in self._enabled()
                self.specs[m["id"]] = dict(m, builtin=False, dir=str(d), enabled=rep["enabled"])
            self.extension_report.append(rep)

    # ---- access
    def ids(self):
        return [i for i, s in self.specs.items() if s.get("builtin") or s.get("enabled")]

    def spec(self, agent_id):
        return self.specs[agent_id]

    def get(self, agent_id):
        if agent_id in self._loaded:
            return self._loaded[agent_id]
        spec = self.specs.get(agent_id)
        if not spec or not (spec.get("builtin") or spec.get("enabled")):
            raise KeyError(f"Unknown or disabled agent: {agent_id}")
        if spec.get("builtin"):
            cls = getattr(importlib.import_module(f"{__package__}.{spec['module']}"), spec["class"])
        else:
            path = Path(spec["dir"]) / spec["module"]
            modspec = importlib.util.spec_from_file_location(f"crysta_ext_{agent_id}", path)
            mod = importlib.util.module_from_spec(modspec)
            modspec.loader.exec_module(mod)
            cls = getattr(mod, spec["class"])
            if not (inspect.isclass(cls) and issubclass(cls, Agent)):
                raise TypeError("extension class must subclass crysta.agents.base.Agent")
        agent = cls()
        if not spec.get("builtin"):  # enforce the manifest's declared permissions
            agent.id, agent.name = spec["id"], spec["name"].upper()
            agent.permitted_tools = frozenset(spec["permissions"])
        self._loaded[agent_id] = agent
        return agent

    def all(self):
        return [self.get(i) for i in self.ids()]

    def loaded_ids(self):
        return sorted(self._loaded)

    def listing(self):
        out = []
        for i in self.ids():
            s = self.specs[i]
            out.append({"id": i, "name": s["name"], "title": s.get("title", s["ui"]["title"]), "description": s["description"], "capabilities": s["capabilities"],
                        "ui_view": s["ui"].get("view"), "builtin": s.get("builtin", False), "loaded": i in self._loaded,
                        "permitted_tools": sorted(self._loaded[i].permitted_tools) if i in self._loaded else s.get("permissions")})
        return out

    def match_extension(self, text):
        low = text.lower()
        for i in self.ids():
            s = self.specs[i]
            if not s.get("builtin") and any(t.lower() in low for t in s.get("triggers", [])):
                return i
        return None
