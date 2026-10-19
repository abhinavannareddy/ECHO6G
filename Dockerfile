FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY echo6g ./echo6g
RUN pip install --no-cache-dir . \
    && useradd --system --uid 10001 --create-home appuser

USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8080/healthz', timeout=2)" || exit 1

ENTRYPOINT ["echo6g-web"]
CMD ["--host", "0.0.0.0", "--port", "8080"]
