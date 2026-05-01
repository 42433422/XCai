FROM python:3.11-slim

# 可选：国内构建加速。docker compose 构建 api 时在 .env 中设 APT_MIRROR=https://mirrors.aliyun.com
# 或 https://mirrors.tuna.tsinghua.edu.cn（不要尾斜杠；勿含 &、| 等特殊字符以免 sed 出错）
ARG APT_MIRROR=

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN set -ex \
  && if [ -n "$APT_MIRROR" ]; then \
       MIRROR=$(echo "$APT_MIRROR" | sed 's|/$||'); \
       for f in /etc/apt/sources.list /etc/apt/sources.list.d/*.sources; do \
         [ -f "$f" ] || continue; \
         sed -i \
           -e "s|http://deb.debian.org/debian-security|${MIRROR}/debian-security|g" \
           -e "s|https://deb.debian.org/debian-security|${MIRROR}/debian-security|g" \
           -e "s|http://deb.debian.org/debian|${MIRROR}/debian|g" \
           -e "s|https://deb.debian.org/debian|${MIRROR}/debian|g" \
           "$f" 2>/dev/null || true; \
       done; \
     fi \
  && apt-get update \
  && apt-get install -y --no-install-recommends gcc libpq-dev \
  && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY modman ./modman
COPY modstore_server ./modstore_server
COPY scripts ./scripts

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e ".[web,knowledge]"

EXPOSE 8765

CMD ["python", "-m", "uvicorn", "modstore_server.app:app", "--host", "0.0.0.0", "--port", "8765"]
