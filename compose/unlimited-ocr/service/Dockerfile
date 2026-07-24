FROM nvidia/cuda:12.9.1-cudnn-runtime-ubuntu24.04

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3.12 python3-pip python3.12-venv libglib2.0-0 libgl1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN python3.12 -m pip install --break-system-packages -r /app/requirements.txt

COPY app.py /app/app.py
COPY runtime_config.py /app/runtime_config.py

EXPOSE 8190
CMD ["python3.12", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8190"]
