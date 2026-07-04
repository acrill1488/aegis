\# Docker + NVIDIA GPU Setup



\## Server



AEGIS-SRV



\## Components



\- Docker Engine

\- Docker Compose Plugin

\- NVIDIA Container Toolkit



\## GPU test



```bash

docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi

