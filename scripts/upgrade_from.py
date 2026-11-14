#!/usr/bin/env python3
"""Carry your data and settings from an OLD CRYSTA folder into this upgraded one. Nothing in the old folder is changed.

    python3 scripts/upgrade_from.py /path/to/old/crysta-ai

Copies (never overwriting something that already exists here): data/ (database, logs), .env, extensions/, models/.
The database is upgraded automatically on first start (a .bak-v1 backup of it is kept)."""
import shutil
import sys
import time
from pathlib import Path

NEW = Path(__file__).resolve().parent.parent


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    old = Path(sys.argv[1]).expanduser().resolve()
    if not (old / "crysta").is_dir() or old == NEW:
        sys.exit(f"{old} doesn't look like an old CRYSTA folder (no 'crysta' package inside), or it is this folder.")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    done = []
    for item in ("data", ".env", "extensions", "models"):
        src, dst = old / item, NEW / item
        if not src.exists():
            continue
        if src.is_file():
            if not dst.exists():
                shutil.copy2(src, dst); done.append(f"copied {item}")
            else:
                done.append(f"kept existing {item} (not overwritten)")
            continue
        dst.mkdir(exist_ok=True)
        for f in src.rglob("*"):
            rel = f.relative_to(src)
            if "__pycache__" in rel.parts or f.name in ("desktop.lock",):
                continue
            target = dst / rel
            if f.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            elif not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, target)
                done.append(f"copied {item}/{rel}")
    db = NEW / "data" / "crysta.db"
    if db.exists():
        shutil.copy2(db, NEW / "data" / f"crysta.db.pre-upgrade-{stamp}")
        done.append(f"backup of your database saved as data/crysta.db.pre-upgrade-{stamp}")
    print("\n".join(done) or "Nothing to copy.")
    print("\nDone. Start the app; your database will be upgraded in place automatically.")


if __name__ == "__main__":
    main()
