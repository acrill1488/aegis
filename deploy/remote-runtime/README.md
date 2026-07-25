# AEGIS Remote Runtime deployment

This isolated stack runs the repository's `aegis.remote.server` and routes embedding requests through `EmbeddingRuntime` to the existing `BGEM3Provider`. It does not contain Ollama, ComfyUI, OCR, an NVIDIA driver, model files, or a model download build step.

The image is based on the official `pytorch/pytorch:2.12.1-cuda12.6-cudnn9-runtime` tag. The host needs Docker Engine, Docker Compose, a compatible NVIDIA driver, and NVIDIA Container Toolkit. CUDA and PyTorch come from the official image; do not install a driver in the container.

Application packages are installed into `/opt/aegis-venv`, an isolated virtual environment created with access to the base image's CUDA-enabled PyTorch. The build does not modify the base image's PEP 668-managed Python environment and does not use `--break-system-packages`.

FlagEmbedding is pinned to 1.3.5 with Transformers 4.48.3. FlagEmbedding 1.3.5 predates its Transformers v5 compatibility work, so the v4 pin prevents import-time API removal while leaving the official PyTorch/CUDA build unchanged.

## Configure and start with GPU

Copy `.env.example` to `.env`, generate a strong token, and create `config/services.yaml`. The server binds to `0.0.0.0` inside the container; by default Compose publishes port 8090 only on host loopback. Set `AEGIS_REMOTE_BIND_ADDRESS` to the compute node's LAN address when LAN access is intended and protect that port with the host firewall.

```sh
docker compose config --quiet
docker compose up -d aegis-remote-runtime
curl http://127.0.0.1:8090/v1/health
```

The bearer token is supplied only through `AEGIS_REMOTE_TOKEN`. A Docker secret may instead be injected by an external deployment wrapper that exports it before process start. Neither token nor model is built into the image.

`BAAI/bge-m3` is initialized by the existing lazy provider only on the first embedding inference request. Hugging Face data persists in the `huggingface-cache` volume; health and image build do not contact Hugging Face.

## CPU fallback

Start only the CPU profile service (the default GPU service must not be running because both publish port 8090):

```sh
docker compose --profile cpu up -d aegis-remote-runtime-cpu
```

## Existing AEGIS network

This Compose project creates no Ollama, ComfyUI, or OCR services. To attach it to an existing external network without changing those containers, create a small local override:

```yaml
services:
  aegis-remote-runtime:
    networks: [aegis]
networks:
  aegis:
    external: true
    name: ${AEGIS_DOCKER_NETWORK:-aegis}
```

Run Compose with both files. No Docker socket, host network, privileged mode, driver, or model bind is required.
