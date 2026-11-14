"""NOVA helpers: project inspection and a local error-explanation table (no AI needed)."""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path

from .files import SKIP_DIRS

MARKERS = {"package.json": "Node.js", "requirements.txt": "Python (pip)", "pyproject.toml": "Python project",
           "Cargo.toml": "Rust", "go.mod": "Go", "pom.xml": "Java (Maven)", "Dockerfile": "Docker",
           "index.html": "Static website", "README.md": "README present"}


def inspect(root: Path):
    counts, found, files = Counter(), {}, 0
    for dp, dns, fns in os.walk(root):
        depth = len(Path(dp).relative_to(root).parts)
        dns[:] = [d for d in dns if d not in SKIP_DIRS and not d.startswith(".")] if depth < 3 else []
        for f in fns:
            files += 1
            counts[Path(f).suffix.lower() or "(none)"] += 1
            if f in MARKERS and f not in found:
                found[f] = str(Path(dp) / f)
        if files > 5000:
            break
    info = {"root": str(root), "files_seen": files, "top_extensions": counts.most_common(6),
            "detected": [MARKERS[m] for m in found], "markers": found}
    pj = found.get("package.json")
    if pj:
        try:
            d = json.loads(Path(pj).read_text(encoding="utf-8"))
            info["npm_scripts"], info["npm_deps"] = list((d.get("scripts") or {}).keys()), list((d.get("dependencies") or {}).keys())[:12]
        except (OSError, ValueError):
            info["npm_note"] = "package.json exists but couldn't be parsed."
    return info


ERRORS = [
    (r"No module named ['\"]?([\w.\-]+)", "Python can't find the package '{0}'.",
     ["Install it: python -m pip install {0}", "If you use a virtual environment, activate it first.",
      "Check the name: the pip name can differ from the import name."]),
    (r"(EADDRINUSE|address already in use)", "That port is already used by another program.",
     ["Pick another port (Crysta: python run.py --port 8766).", "Find the program: 'lsof -i :PORT' (Mac/Linux) or 'netstat -ano' (Windows).", "Close that program rather than killing unknown processes."]),
    (r"(command not found|is not recognized as an internal or external command)", "The command isn't installed or isn't on your PATH.",
     ["Check the spelling.", "Install the tool, then open a new terminal so PATH refreshes."]),
    (r"(Permission denied|EACCES|Access is denied)", "The operating system blocked access to a file or port.",
     ["Check you own the file/folder.", "Avoid running with admin rights just to bypass this; fix the permissions instead."]),
    (r"(No such file or directory|ENOENT|FileNotFoundError|cannot find the (file|path))", "A file or folder in the error doesn't exist at that path.",
     ["Check spelling and the current folder (pwd / cd).", "Use the full path."]),
    (r"IndentationError", "Python found inconsistent indentation.", ["Use 4 spaces everywhere; don't mix tabs and spaces."]),
    (r"SyntaxError", "The code has a typo Python/JS can't parse.", ["Look at the line number in the error and the line above it (missing bracket, quote or colon)."]),
    (r"Cannot read propert(?:y|ies) of (undefined|null)", "JavaScript used a value that doesn't exist yet.",
     ["Check that the object is set before you use it.", "Use optional chaining: obj?.field"]),
    (r"ERESOLVE", "npm found conflicting dependency versions.", ["Read which two packages conflict.", "Try 'npm install --legacy-peer-deps' only if you understand the conflict."]),
    (r"(ENOSPC|No space left on device)", "The disk (or watcher limit) is full.", ["Check free space.", "Free space by removing files YOU recognise as unneeded; never delete system files."]),
    (r"(ImportError: cannot import name)", "The name you import isn't in that module (wrong version or typo).", ["Check the library version and spelling."]),
    (r"KeyError: ?['\"]?([\w\-]+)", "The dictionary has no key '{0}'.", ["Print the dictionary keys.", "Use .get('{0}') if the key is optional."]),
    (r"CORS", "The browser blocked a cross-site request.", ["Call the API from the same origin, or enable the right CORS headers on the server."]),
]


def explain_error(text):
    for pat, meaning, steps in ERRORS:
        m = re.search(pat, text, re.I)
        if m:
            groups = [g for g in m.groups() if g] or [""]
            return {"matched": True, "meaning": meaning.format(*groups), "steps": [s.format(*groups) for s in steps]}
    return {"matched": False}


def suggest_commands(root: Path):
    """Run/test commands suggested from files that really exist in the project (nothing is executed here)."""
    run, test = [], []
    if (root / "package.json").is_file():
        try:
            scripts = (json.loads((root / "package.json").read_text(encoding="utf-8")).get("scripts") or {})
        except (OSError, ValueError):
            scripts = {}
        for k in ("dev", "start"):
            if k in scripts:
                run.append({"label": f"npm run {k}", "command": f"npm run {k}"})
        if "test" in scripts:
            test.append({"label": "npm test", "command": "npm test"})
    if (root / "run.py").is_file() or (root / "main.py").is_file() or (root / "app.py").is_file():
        f = next(n for n in ("run.py", "main.py", "app.py") if (root / n).is_file())
        run.append({"label": f"python3 {f}", "command": f"python3 {f}"})
    if (root / "tests").is_dir() or any(root.glob("test_*.py")):
        test.append({"label": "python3 -m unittest", "command": "python3 -m unittest discover" if not (root / "tests").is_dir() else "python3 -m unittest discover -s tests"})
    if (root / "index.html").is_file():
        run.append({"label": "serve on :8000", "command": "python3 -m http.server 8000"})
    return {"root": str(root), "run": run, "test": test}
