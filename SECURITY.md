# Security

## Threat model

This system sits **inside** a smart grid operations network, receiving traffic telemetry from smart meters and DAPs. It is not internet-facing by design.

| Threat | Impact | Mitigated? |
|---|---|---|
| Adversarial inputs crafted to evade IF/RF | Model bypass | Partial — ensemble reduces single-model evasion surface |
| Model poisoning during retrain | Degraded detection | No — retrain endpoint has no auth by default |
| Alert log tampering | False audit trail | No — SQLite file, no write audit |
| Data exfiltration via API | Raw traffic leaks | No — endpoints are unauthenticated by default |
| DoS against the IDS itself | Detector goes down | Partial — uvicorn rate limiting configurable |

---

## Current security posture (default)

- **No authentication** on any endpoint. Suitable for air-gapped lab/staging only.
- **No TLS**. Run behind an nginx reverse proxy with TLS in production.
- **CORS** is open (`*`). Lock it down to the NiceGUI host in production.
- SQLite file at `models/alerts.db` is readable by any process with FS access.

---

## Production hardening checklist

```bash
# 1. API key auth — add to backend/config.py
API_KEY=your-secret-here           # set in .env

# 2. Lock CORS in backend/main.py
allow_origins=["http://your-nicegui-host:8080"]

# 3. TLS — nginx snippet
server {
    listen 443 ssl;
    ssl_certificate     /etc/ssl/certs/grid-ids.crt;
    ssl_certificate_key /etc/ssl/private/grid-ids.key;
    location / { proxy_pass http://localhost:8000; }
}

# 4. Restrict retrain endpoint
# Add Depends(verify_api_key) to POST /train

# 5. SQLite → Postgres for multi-instance or audit requirements
# Swap aiosqlite for asyncpg in db.py
```

---

## Model security

**Adversarial robustness**: An attacker who knows IF's contamination rate can craft traffic that sits just inside the decision boundary. The ensemble partially mitigates this — evading IF does not guarantee evading RF residual thresholding. A future improvement is to add a canary feature (e.g., request inter-arrival jitter) that is hard to spoof simultaneously.

**Model artefact integrity**: `models/saved/ensemble_detector.pkl` is a Python pickle. Do not load pickle files from untrusted sources. If the model file is delivered over a network, sign it with `hashlib.sha256` and verify before loading.

```python
# Verify before loading
import hashlib, pathlib
expected = "abc123..."   # known good hash stored separately
actual = hashlib.sha256(pathlib.Path("models/saved/ensemble_detector.pkl").read_bytes()).hexdigest()
assert actual == expected, "Model file tampered"
```

---

## Reporting a vulnerability

Open a GitHub issue with the label `security`. For sensitive disclosures, email the maintainer directly. Do not post exploit code publicly before a patch is available.
