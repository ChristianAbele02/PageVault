# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x     | ✅ Yes    |

## Scope

PageVault is designed for **personal, local use on a trusted network**. It does not implement authentication or HTTPS by default. Do not expose it directly to the public internet without a reverse proxy (e.g. nginx + Let's Encrypt) and proper access controls.

## Reporting a Vulnerability

If you discover a security vulnerability, please **do not open a public GitHub issue**.

Instead, email **christian.abele@uni-bielefeld.de** (replace with your actual contact) with:
- A description of the vulnerability
- Steps to reproduce
- Potential impact

You can expect an acknowledgement within **48 hours** and a patch or workaround within **7 days** for confirmed issues.

## Known Limitations

- No built-in authentication — anyone on the same network can access the app
- SQLite WAL mode is used; the database file should not be world-readable
- The `SECRET_KEY` default value in `app.py` must be changed in any production/networked deployment
