FROM pytorch/pytorch:2.12.1-cuda12.6-cudnn9-runtime

ARG AEGIS_UID=10001
ARG AEGIS_GID=10001
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/aegis-venv \
    PATH=/opt/aegis-venv/bin:$PATH \
    HF_HOME=/var/cache/huggingface \
    AEGIS_SERVICES_CONFIG=/etc/aegis/services.yaml

RUN apt-get update \
    && apt-get install --yes --no-install-recommends python3.12-venv \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid ${AEGIS_GID} aegis \
    && useradd --uid ${AEGIS_UID} --gid ${AEGIS_GID} --create-home aegis \
    && python -m venv --system-site-packages ${VIRTUAL_ENV} \
    && mkdir -p /app /etc/aegis /var/cache/huggingface \
    && chown -R aegis:aegis /app /etc/aegis /var/cache/huggingface ${VIRTUAL_ENV}

WORKDIR /app
COPY --chown=aegis:aegis pyproject.toml README.md ./
COPY --chown=aegis:aegis aegis ./aegis

# The isolated venv can see the official image's matching CUDA-enabled torch build.
# This avoids modifying its PEP 668-managed Python environment. --no-deps prevents
# unrelated AEGIS desktop/Windows dependencies entering this server image.
RUN python -m pip install --no-cache-dir --upgrade pip "setuptools<82" wheel \
    && python -m pip install --no-cache-dir --no-deps . \
    && python -m pip install --no-cache-dir "FlagEmbedding==1.3.5" "transformers==4.48.3" "fastapi>=0.110,<1" "uvicorn[standard]>=0.27,<1" "pydantic>=2,<3" "pyyaml>=6,<7"

USER aegis:aegis
EXPOSE 8090
CMD ["python", "-m", "uvicorn", "aegis.remote.server.app:app", "--host", "0.0.0.0", "--port", "8090", "--no-access-log"]
