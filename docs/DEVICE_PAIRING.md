# Device pairing

1. Start Crysta with `python3 run.py --lan`. It prints your LAN address and warns that HTTP is unencrypted.
2. On the laptop: Devices → *Create pairing code* (valid 5 minutes, one use).
3. On the phone, open the printed address. Crysta redirects you to the pairing page (`/pair.html`): enter the code and a name for the phone.
4. On the laptop, approve the request, optionally allowing computer control (off by default).
5. Disconnect any device, or use **Emergency stop**, from the laptop at any time.

Security: wrong codes are rate-limited (5 per 5 minutes per IP); tokens are random 256-bit, stored hashed, handed over once; same Wi-Fi alone grants nothing.

**Encryption:** plain HTTP on a LAN can be read by others on that network. For real encryption set `CRYSTA_TLS_CERT` / `CRYSTA_TLS_KEY` (e.g. `openssl req -x509 -newkey rsa:2048 -nodes -keyout key.pem -out cert.pem -days 365 -subj /CN=crysta`), or reach Crysta through a trusted tunnel such as Tailscale. Never port-forward it to the internet.

**Limitations (honest):** no native Android app; no automatic discovery (you type the address); a phone can chat/research and—only if allowed—request computer actions that still need approval on the laptop.
