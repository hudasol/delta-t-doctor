# syntax=docker/dockerfile:1.7
#
# Stage 1 needs the network: it downloads every dependency as a wheel, each checked against the sha256 in requirements.lock, and builds
# the project's own wheel. Stage 2 installs with networking disabled (RUN --network=none) and only from those wheels, so the runtime
# image is assembled offline from hash-checked artefacts.

FROM python:3.13-slim AS wheels
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY requirements.lock ./
RUN pip download --require-hashes --only-binary=:all: --no-deps -r requirements.lock -d /wheels
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip wheel --no-deps -w /wheels .

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DTD_MAX_CONCURRENT=2
WORKDIR /app
COPY requirements.lock ./
COPY --from=wheels /wheels /wheels
RUN --network=none pip install --no-index --find-links /wheels --require-hashes -r requirements.lock \
 && pip install --no-index --no-deps /wheels/deltat_doctor-*.whl \
 && rm -rf /wheels \
 && useradd --no-create-home --shell /usr/sbin/nologin --uid 10001 app
USER 10001

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health').status==200 else 1)"
CMD ["deltat-doctor", "serve", "--host", "0.0.0.0", "--port", "8000"]
