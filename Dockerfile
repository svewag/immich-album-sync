FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml /app/
COPY src /app/src

RUN pip install --no-cache-dir .

ENV IMMICH_ALBEN_CONFIG=/config/config.yaml

ENTRYPOINT ["python", "-m", "immich_alben"]
