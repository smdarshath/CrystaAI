"""File tools restricted to user-approved directories (symlink/`..` safe)."""
from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

from ..errors import CrystaError, PathNotAllowed

MAX_READ = 200_000
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".cache", ".venv", "venv"}


class FileTools:
    def __init__(self, dirs_getter):
        self._dirs = dirs_getter

    def roots(self):
        return [Path(d).expanduser().resolve() for d in self._dirs()]

    def resolve(self, p):
        roots = self.roots()
        if not roots:
            raise PathNotAllowed("No folders are approved yet. Add one in Computer settings.")
        path = Path(str(p).strip().strip('"').strip("'")).expanduser()
        if str(p).strip() in ("", "~") and not any(path.resolve() == r or r in path.resolve().parents for r in roots):
            path = roots[0]          # "my files" when home itself isn't approved -> the first approved folder
        if not path.is_absolute():
            home_try = (Path.home() / path).resolve()
            first = (roots[0] / path).resolve()
            path = home_try if (not first.exists() and home_try.exists()) else first
        path = path.resolve()
        for r in roots:
            try:
                path.relative_to(r)
                return path
            except ValueError:
                continue
        raise PathNotAllowed(f"That location is outside the folders you approved ({', '.join(str(r) for r in roots[:3])}). "
                             "Add it under Computer → Approved folders if you want me to use it.")

    def _inside(self, p):
        for r in self.roots():
            try:
                p.resolve().relative_to(r)
                return True
            except ValueError:
                pass
        return False

    def special_folders(self):
        out = []
        for name in ("Desktop", "Documents", "Downloads", "Pictures", "Music", "Videos"):
            d = Path.home() / name
            if d.is_dir() and self._inside(d):
                out.append({"name": name, "path": str(d)})
        return out

    def find_project_folder(self):
        roots = self.roots()
        for r in roots:
            for depth_dir in [r] + [d for d in sorted(r.iterdir()) if d.is_dir() and not d.name.startswith(".")][:80] if r.is_dir() else []:
                if "project" in depth_dir.name.lower() and depth_dir != r:
                    return depth_dir
        return None

    def info(self, path):
        import mimetypes, stat as st_mod
        p = self.resolve(path)
        if not p.exists():
            raise CrystaError(f"That doesn't exist: {p}")
        s = p.stat()
        return {"path": str(p), "name": p.name, "type": "folder" if p.is_dir() else "file", "size": s.st_size if p.is_file() else None,
                "modified": s.st_mtime, "created": getattr(s, "st_ctime", None), "mime": mimetypes.guess_type(p.name)[0],
                "permissions": st_mod.filemode(s.st_mode), "readable": os.access(p, os.R_OK), "writable": os.access(p, os.W_OK),
                "items": len(list(p.iterdir())) if p.is_dir() and os.access(p, os.R_OK) else None}

    def mkdir(self, path):
        p = self.resolve(path)
        if p.exists():
            raise CrystaError(f"That already exists: {p}")
        p.mkdir(parents=True)
        return {"path": str(p), "verified": p.is_dir()}

    @staticmethod
    def _check_name(name):
        if not name or "/" in name or "\\" in name or name in (".", "..") or len(name) > 200:
            raise CrystaError("A new name must be a plain file name (no slashes).")
        return name

    def rename(self, path, new_name):
        p = self.resolve(path)
        dest = self.resolve(p.parent / self._check_name(new_name))
        if not p.exists():
            raise CrystaError(f"That doesn't exist: {p}")
        p.rename(dest)
        return {"path": str(dest), "verified": dest.exists() and not p.exists()}

    def copy(self, src, dst):
        import shutil
        s, d = self.resolve(src), self.resolve(dst)
        if d.is_dir():
            d = d / s.name
        if not s.exists():
            raise CrystaError(f"That doesn't exist: {s}")
        if s.is_dir():
            if d == s or str(d).startswith(str(s) + os.sep):
                raise CrystaError("A folder can't be copied into itself.")
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)
        return {"path": str(d), "verified": d.exists()}

    def move(self, src, dst):
        import shutil
        s, d = self.resolve(src), self.resolve(dst)
        if d.is_dir():
            d = d / s.name
        if not s.exists():
            raise CrystaError(f"That doesn't exist: {s}")
        if s.is_dir() and str(d).startswith(str(s) + os.sep):
            raise CrystaError("A folder can't be moved into itself.")
        shutil.move(str(s), str(d))
        return {"path": str(d), "verified": d.exists() and not s.exists()}

    def target_exists(self, src_or_dir, dst, name_only=False):
        d = self.resolve(dst)
        if d.is_dir():
            d = d / self.resolve(src_or_dir).name
        return d.exists()

    IMG = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}

    def raw_image(self, path):
        p = self.resolve(path)
        mime = self.IMG.get(p.suffix.lower())
        if not mime or not p.is_file():
            raise CrystaError("Only png, jpg, gif and webp images can be previewed.")
        if p.stat().st_size > 5_000_000:
            raise CrystaError("That image is larger than 5 MB.")
        return mime, p.read_bytes()

    def list_dir(self, path="~"):
        p = self.resolve(path)
        if not p.exists():
            raise CrystaError(f"That folder doesn't exist: {p}")
        if not p.is_dir():
            raise CrystaError(f"That is a file, not a folder: {p}")
        try:
            entries = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))[:500]
        except PermissionError:
            raise CrystaError(f"The operating system doesn't let me open this folder: {p}")
        items = []
        for e in entries:
            try:
                st = e.stat()
                items.append({"name": e.name, "type": "folder" if e.is_dir() else "file",
                              "size": st.st_size if e.is_file() else None, "modified": st.st_mtime})
            except OSError:
                continue
        return {"path": str(p), "parent": str(p.parent) if p != p.parent and self._inside(p.parent) else None, "items": items}

    def read_file(self, path):
        p = self.resolve(path)
        if not p.is_file():
            raise CrystaError("That file doesn't exist.")
        if p.stat().st_size > MAX_READ:
            raise CrystaError("That file is too large to read here (limit 200 KB).")
        raw = p.read_bytes()
        if b"\x00" in raw:
            raise CrystaError("That looks like a binary file, so I won't print it.")
        return {"path": str(p), "text": raw.decode("utf-8", "replace")}

    def write_file(self, path, content):
        if isinstance(content, str) and len(content) > 2_000_000:
            raise CrystaError("That is too large to write (limit 2 MB).")
        p = self.resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(p.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp, p)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        ok = p.is_file() and p.read_text(encoding="utf-8") == content  # verify outcome
        return {"path": str(p), "bytes": len(content.encode("utf-8")), "verified": ok}

    def delete_file(self, path):
        p = self.resolve(path)
        if p.is_dir():
            if any(p.iterdir()):
                raise CrystaError("I only delete empty folders. Empty it first (or delete it yourself in your file manager).")
            p.rmdir()
            return {"path": str(p), "verified": not p.exists()}
        if not p.is_file():
            raise CrystaError("That doesn't exist.")
        p.unlink()
        return {"path": str(p), "verified": not p.exists()}

    def find(self, name, root=None, limit=30, max_seconds=5):
        base = self.resolve(root or "~")
        needle, hits, end = name.lower(), [], time.time() + max_seconds
        for dp, dns, fns in os.walk(base):
            dns[:] = [d for d in dns if d not in SKIP_DIRS and not d.startswith(".")]
            for f in fns + dns:
                if needle in f.lower():
                    hits.append(str(Path(dp) / f))
            if len(hits) >= limit or time.time() > end:
                break
        return {"root": str(base), "matches": hits[:limit], "complete": time.time() <= end and len(hits) < limit}
