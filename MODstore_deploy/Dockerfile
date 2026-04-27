FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY modman ./modman
COPY modstore_server ./modstore_server

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e ".[web,knowledge]"

EXPOSE 8765

CMD ["python", "-m", "uvicorn", "modstore_server.app:app", "--host", "0.0.0.0", "--port", "8765"]
