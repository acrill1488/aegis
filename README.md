# AEGIS

AEGIS is a local modular AI platform. Image Generation is production-ready and
OCR Platform is the active vertical.

Network service endpoints are resolved through the centralized configuration:
`F:\AI_WORKSPACE\config\services.yaml`. Override its location with
`AEGIS_SERVICES_CONFIG`, the common server with `AEGIS_SERVER_HOST` and
`AEGIS_SERVER_SCHEME`, or individual services with
`AEGIS_OLLAMA_BASE_URL`, `AEGIS_UNLIMITED_OCR_BASE_URL`, and
`AEGIS_COMFYUI_BASE_URL`.

Inspect effective values with `aegis config show` and diagnose all services with
`aegis config doctor`.
