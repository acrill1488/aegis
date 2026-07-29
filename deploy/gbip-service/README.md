# Integration-001 Ubuntu GBIP service

This deployment exposes the existing AEGIS `ResourceSnapshot` contract through
three authenticated, read-only endpoints: `GET /v1/health`,
`GET /v1/discover`, and `GET /v1/snapshot`.

The service performs one probe pass per request. It has no cache, polling,
reservation, ledger, admission, or scheduling behavior. CPU, RAM, mounted disks,
NVIDIA GPU/VRAM, Docker, Ollama, and Ollama model discovery execute only on the
Ubuntu host. The bind address is a required `services.yaml` value and wildcard
binds are rejected by the CLI.

## Ubuntu configuration

Create `/etc/aegis/services.yaml` (replace `192.168.1.12` with the Ubuntu LAN
address if needed):

```yaml
schema_version: 1
server:
  scheme: http
  host: 127.0.0.1
services:
  ollama: {port: 11434, base_url: http://127.0.0.1:11434}
  unlimited_ocr: {port: 8190, base_url: http://127.0.0.1:8190}
  comfyui: {port: 8188, base_url: http://127.0.0.1:8188}
paths: {}
greenboost:
  enabled: false
  server:
    enabled: true
    node_id: ubuntu-primary
    host: 192.168.1.12
    port: 8091
    token_env: AEGIS_GREENBOOST_API_KEY
```

`greenboost.enabled` remains `false` on the server so its own probe composition
stays in legacy/local mode; the server endpoint explicitly selects the Ubuntu
probes and never calls GBIP recursively.

## Install and run

```bash
cd /opt/AEGIS
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
sudo install -m 0644 deploy/gbip-service/aegis-gbip.service /etc/systemd/system/aegis-gbip.service
sudo install -m 0600 deploy/gbip-service/aegis-gbip.env.example /etc/aegis/gbip.env
sudoedit /etc/aegis/gbip.env
sudo systemctl daemon-reload
sudo systemctl enable --now aegis-gbip
sudo systemctl status aegis-gbip --no-pager
```

The example environment file intentionally contains no secret. Generate one,
store it only in `/etc/aegis/gbip.env`, and allow TCP/8091 only from the Windows
workstation in the Ubuntu firewall.

## Smoke tests on Ubuntu

```bash
set -a; . /etc/aegis/gbip.env; set +a
curl --fail --silent --show-error -H "Authorization: Bearer ${AEGIS_GREENBOOST_API_KEY}" http://192.168.1.12:8091/v1/health
curl --fail --silent --show-error -H "Authorization: Bearer ${AEGIS_GREENBOOST_API_KEY}" http://192.168.1.12:8091/v1/discover
curl --fail --silent --show-error -H "Authorization: Bearer ${AEGIS_GREENBOOST_API_KEY}" http://192.168.1.12:8091/v1/snapshot
```

## Windows client configuration

Add this exact top-level block to `F:\AI_WORKSPACE\config\services.yaml`:

```yaml
greenboost:
  enabled: true
  base_url: http://192.168.1.12:8091
  api_key: null
  connect_timeout: 5
  read_timeout: 30
  write_timeout: 30
  pool_timeout: 5
  retries: 0
  probes:
    enabled: true
    local_system: {enabled: true}
    nvidia: {enabled: true}
    services: {enabled: true, timeout_seconds: 2}
    models: {enabled: true, timeout_seconds: 3}
    remote: {enabled: true}
    fail_on_required_probe_error: false
```

Set the secret only in the Windows process environment:

```powershell
$env:AEGIS_GREENBOOST_API_KEY = '<same-secret-as-ubuntu>'
.venv\Scripts\python.exe -m aegis.cli.main greenboost health
.venv\Scripts\python.exe -m aegis.cli.main greenboost discover
.venv\Scripts\python.exe -m aegis.cli.main greenboost snapshot --remote
.venv\Scripts\python.exe -m aegis.cli.main cluster nodes
.venv\Scripts\python.exe -m aegis.cli.main cluster snapshot --json
```

When `greenboost.enabled` is false, the pre-existing local probe composition is
retained. When it is true, Windows collects only workstation CPU/RAM/GPU plus
the remote GBIP snapshot; it does not inspect local Docker, Ollama, or models.
