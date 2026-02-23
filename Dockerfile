FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY setup-networks.sh ./
RUN chmod +x setup-networks.sh

RUN mkdir -p /data/cache

ENV PYTHONUNBUFFERED=1

EXPOSE 8001

ENTRYPOINT ["./setup-networks.sh"]
