FROM gcc:12-bookworm AS cpp-build
WORKDIR /src
COPY echo6g/native/ ./native/
RUN g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic -Werror \
      -I native native/main.cpp native/engine.cpp -o /build-echo6g-engine \
    && g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic -Werror \
      -I native native/engine.cpp native/test_engine.cpp -o /build-echo6g-tests \
    && /build-echo6g-tests

FROM python:3.12-slim-bookworm AS test
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    ECHO6G_ENGINE=/usr/local/bin/echo6g-engine
COPY . /app
COPY --from=cpp-build /build-echo6g-engine /usr/local/bin/echo6g-engine
RUN python -m unittest discover -s tests -v

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    ECHO6G_ENGINE=/usr/local/bin/echo6g-engine

WORKDIR /app
COPY README.md pyproject.toml ./
COPY echo6g ./echo6g
COPY --from=cpp-build /build-echo6g-engine /usr/local/bin/echo6g-engine
RUN useradd --system --uid 10001 --create-home appuser

USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8080/healthz', timeout=2)" || exit 1

ENTRYPOINT ["python", "-m", "echo6g.web"]
CMD ["--host", "0.0.0.0", "--port", "8080"]
