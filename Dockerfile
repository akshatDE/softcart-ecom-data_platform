# Shared application image for the SoftCart FastAPI service, Streamlit
# dashboard, and ad-hoc pipeline runs. The command is supplied per-service
# in docker-compose.yml.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/softcart

WORKDIR /opt/softcart

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY resources ./resources
COPY scripts ./scripts
COPY tests ./tests

RUN mkdir -p data/generated data/analytics logs

CMD ["python", "-m", "src.main.main", "--step", "all"]
