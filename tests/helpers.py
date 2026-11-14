import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crysta.app import App  # noqa: E402
from crysta.config import Config  # noqa: E402


def make_app(**cfg):
    tmp = Path(tempfile.mkdtemp(prefix="crysta-test-"))
    app = App(Config(data_dir=tmp / "data", host="127.0.0.1", port=0, **cfg), quiet=True)
    app.tmp = tmp
    (tmp / "work").mkdir()
    app.settings.set("approved_dirs", [str(tmp / "work")])
    return app


DDG_HTML = """<html><body>
<div class="result"><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2Fblack-holes&rut=x">Black holes explained</a>
<a class="result__snippet">A black hole is a region of spacetime where gravity is so strong that nothing can escape.</a></div>
<div class="result"><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fscience.example.net%2Fbh">Black hole basics</a>
<a class="result__snippet">Black holes form when massive stars collapse at the end of their lives.</a></div></body></html>"""
WIKI_JSON = json.dumps({"query": {"pages": {"1": {"title": "Black hole", "index": 1, "extract":
    "A black hole is a region of spacetime where gravity is so strong that nothing, not even light, can escape from it. "
    "The boundary of no escape is called the event horizon."}}}})


def PAGE(t):
    return (f"<html><head><title>{t}</title></head><body><nav>menu</nav><p>A black hole is an object whose gravity is so strong that light "
            "cannot escape from inside the event horizon. Black holes can form when a massive star collapses at the end of its life.</p>"
            "<script>evil()</script></body></html>")
