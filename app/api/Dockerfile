FROM python:3.11-slim

WORKDIR /app

# e540 等国内环境：Docker 构建时 deb.debian.org 易超时，换阿里云镜像并加重试
RUN set -eux; \
    for f in /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list; do \
      [ -f "$f" ] && sed -i \
        -e 's|deb.debian.org|mirrors.aliyun.com|g' \
        -e 's|security.debian.org|mirrors.aliyun.com|g' \
        "$f" || true; \
    done; \
    apt-get update; \
    apt-get install -y --no-install-recommends -o Acquire::Retries=5 \
      gcc libpq-dev \
      libreoffice-writer libreoffice-core fonts-noto-cjk fonts-wqy-zenhei; \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com .

COPY . .

RUN mkdir -p /data/uploads

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
