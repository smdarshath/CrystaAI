"""Local knowledge search over bundled/user .md/.txt files and saved notes (keyword + IDF scoring)."""
from __future__ import annotations

import math
import re
from pathlib import Path

from .textutil import keywords


class KnowledgeIndex:
    def __init__(self, dirs, notes_provider=None):
        self.dirs = [Path(d) for d in dirs]
        self.notes_provider = notes_provider
        self._sig, self._chunks = None, []

    def _signature(self):
        sig = []
        for d in self.dirs:
            if d.is_dir():
                for p in sorted(d.rglob("*")):
                    if p.suffix.lower() in (".md", ".txt") and p.is_file():
                        sig.append((str(p), p.stat().st_mtime))
        return tuple(sig)

    def _build(self, sig):
        chunks = []
        for path, _ in sig:
            try:
                text = Path(path).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for para in re.split(r"\n\s*\n", text):
                para = para.strip()
                if len(para) > 30:
                    chunks.append((Path(path).name, para[:1200]))
        return chunks

    def search(self, query, k=3):
        sig = self._signature()
        if sig != self._sig:
            self._sig, self._chunks = sig, self._build(sig)
        chunks = list(self._chunks)
        if self.notes_provider:
            try:
                chunks += [(f"note:{n['title'] or n['id']}", n["body"]) for n in self.notes_provider()]
            except Exception:
                pass
        terms = set(keywords(query))
        if not terms or not chunks:
            return []
        docs = [(src, text, set(keywords(text))) for src, text in chunks]
        n = len(docs)
        idf = {t: math.log(1 + n / (1 + sum(1 for d in docs if t in d[2]))) for t in terms}
        total = sum(idf.values()) or 1
        out = []
        for src, text, ks in docs:
            matched = terms & ks
            if matched:
                out.append({"source": src, "text": text, "score": round(sum(idf[t] for t in matched) / total, 3)})
        out.sort(key=lambda r: -r["score"])
        return out[:k]
