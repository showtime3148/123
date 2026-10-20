FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GCE_STATE_DIR=/var/data/gce

RUN --mount=type=secret,id=build_ca,mode=0444 \
    set -eu; \
    sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources; \
    set --; \
    if [ -f /run/secrets/build_ca ]; then set -- -o Acquire::https::CaInfo=/run/secrets/build_ca; fi; \
    apt-get "$@" -o APT::Update::Error-Mode=any update \
    && DEBIAN_FRONTEND=noninteractive apt-get "$@" install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng fonts-dejavu-core gosu tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 gce \
    && useradd --uid 10001 --gid gce --no-create-home gce

WORKDIR /app
COPY requirements.txt .
RUN --mount=type=secret,id=build_ca,mode=0444 \
    if [ -f /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi; \
    python -m pip install --no-cache-dir -r requirements.txt
COPY --chown=gce:gce app ./app
COPY --chown=gce:gce data ./data
COPY --chown=gce:gce public ./public
COPY --chown=gce:gce scripts/serve.py scripts/container-entrypoint.sh ./scripts/
COPY --chown=gce:gce tests ./tests
RUN mkdir -p /var/data/gce && chown -R gce:gce /var/data/gce

EXPOSE 10000
ENTRYPOINT ["sh", "/app/scripts/container-entrypoint.sh"]
