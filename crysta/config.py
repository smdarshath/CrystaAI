"""Configuration from environment variables (and an optional .env file)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")


def default_data_dir():
    """Portable by default (<app>/data, so existing data is kept). If the app folder is read-only
    (e.g. installed system-wide) fall back to the platform's per-user data folder."""
    portable = ROOT / "data"
    try:
        portable.mkdir(exist_ok=True)
        probe = portable / ".write_test"
        probe.write_text("x"); probe.unlink()
        return portable
    except OSError:
        import platform
        home = Path.home()
        if platform.system() == "Windows":
            return Path(os.environ.get("APPDATA", home / "AppData" / "Roaming")) / "CRYSTA-AI"
        if platform.system() == "Darwin":
            return home / "Library" / "Application Support" / "CRYSTA-AI"
        return Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share")) / "crysta-ai"


class Config:
    def __init__(self, **overrides):
        env = os.environ.get
        self.host = env("CRYSTA_HOST", "127.0.0.1")
        self.port = int(env("CRYSTA_PORT", "8765"))
        self.data_dir = Path(env("CRYSTA_DATA_DIR", "")).expanduser() if env("CRYSTA_DATA_DIR") else default_data_dir()
        self.session_token = ""  # set by the desktop launcher: only the app's own window can use the API
        self.web_dir = ROOT / "web"
        self.knowledge_dirs = [ROOT / "knowledge", self.data_dir / "knowledge"]
        self.user_name = env("CRYSTA_USER_NAME", "Arshad")
        self.creator = env("CRYSTA_CREATOR", "Arshath")
        self.extensions_dir = Path(env("CRYSTA_EXTENSIONS_DIR", str(ROOT / "extensions")))
        self.ollama_url = env("CRYSTA_OLLAMA_URL", "http://127.0.0.1:11434")
        self.ollama_model = env("CRYSTA_OLLAMA_MODEL", "")
        self.openai_base = env("CRYSTA_OPENAI_BASE", "")
        self.openai_key = env("CRYSTA_OPENAI_KEY", "")
        self.openai_model = env("CRYSTA_OPENAI_MODEL", "")
        self.tls_cert = env("CRYSTA_TLS_CERT", "")
        self.tls_key = env("CRYSTA_TLS_KEY", "")
        self.allowed_hosts = [h.strip().lower() for h in env("CRYSTA_ALLOWED_HOSTS", "").split(",") if h.strip()]
        self.agent_timeout = int(env("CRYSTA_AGENT_TIMEOUT", "60"))
        for k, v in overrides.items():
            setattr(self, k, v)
