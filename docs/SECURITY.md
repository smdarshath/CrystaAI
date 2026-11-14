# Security & privacy

**Network exposure.** By default the server binds to 127.0.0.1 only. `--lan` exposes it to your network; then only paired devices (bearer token) can call the API, and many endpoints (settings, audit, memory, pairing management, emergency stop) are *local-only*. The Host header is checked (DNS-rebinding defence) and cross-origin POSTs are rejected.

**Permissions.** Six categories (read files, write files, open apps, run commands, keyboard/mouse, destructive), each `allow` / `confirm` / `deny`. Defaults: read & open apps = allow; everything else = confirm. "Destructive" can never be `allow`. "Full-control mode" removes prompts for write/open/run/keyboard but deletes, overwrites and risky commands still ask.

**Confirmations** are pending actions held in memory for 120 s, single-use, and can only be approved through the on-screen Approve button (voice cannot approve; web content cannot approve).

**Files.** Only inside approved folders; paths are resolved (so `..` and symlinks are caught) before checking. Writes are atomic and verified by re-reading. Delete handles single files only.

**Commands.** No shell is used. One plain command at a time (`; & | > < `` $(`) are rejected). A never-run list (sudo, mkfs, dd to devices, shutdown/reboot, curl|sh, format/del /s…) is always blocked. Read-only commands (`ls`, `pwd`, `git status`, `python --version`…) run without prompting; anything else asks. Output and runtime are capped. **This is a safety net, not a sandbox** — an approved command runs with your user's rights.

**Untrusted content.** Web pages/captions are data only: they are never executed, can't call tools, and can't change settings (there is a test for this). The page fetcher refuses private/loopback addresses (SSRF), honours robots.txt, and caps size.

**Secrets.** Paired-device tokens are stored hashed (SHA-256) and shown once. Audit/log text is redacted for token/password/key patterns. API keys live in `.env` (git-ignored), never in front-end code.

**Privacy.** Nothing leaves the machine except: web/YouTube requests you trigger, optional OpenAI-compatible endpoint if you configure one, and — in Chrome/Edge — the browser's own speech recognition (which may send audio to the browser vendor). Memory is off by default; view/export/delete in Settings.

**Known limits.** `--lan` without TLS is plain HTTP (see DEVICE_PAIRING.md). The audit log is local and deletable by the user. pyautogui actions can't be verified visually.

## Added in the desktop upgrade
- **Session secret (desktop mode):** every API call must carry the app window's secret cookie; other local programs/pages get 401. (Server mode keeps the earlier model: loopback is trusted, Host/Origin are checked.)
- **File manager:** operations stay inside approved folders; create/rename/copy/move ask by default (or run silently in Full-control mode); overwriting or deleting always asks; rename never overwrites; folders are deleted only when empty; image preview is limited to png/jpg/gif/webp ≤ 5 MB.
- **Terminal in NOVA** uses the same rules as before: one plain command, never-run list, confirmation for anything not read-only.
- **Extensions** are validated and opt-in (see EXTENSIONS.md) but are trusted code once enabled.
