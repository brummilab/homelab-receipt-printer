FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    curl \
    procps \
    cron \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    python-escpos \
    "qrcode[pil]" \
    Pillow \
    psutil \
    requests \
    docker \
    flask

WORKDIR /app
COPY config.py webui.py healthcheck.py ./
COPY entrypoint.sh .
COPY templates/ templates/
RUN chmod +x entrypoint.sh

EXPOSE 8080

