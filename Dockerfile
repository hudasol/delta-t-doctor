FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DTD_MAX_CONCURRENT=2
WORKDIR /app

# Dependencies come from the pinned lock file, not from open version ranges.
COPY requirements-lock.txt ./
RUN pip install -r requirements-lock.txt
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-deps . && useradd --no-create-home --shell /usr/sbin/nologin --uid 10001 app
USER 10001

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health').status==200 else 1)"
CMD ["deltat-doctor", "serve", "--host", "0.0.0.0", "--port", "8000"]
