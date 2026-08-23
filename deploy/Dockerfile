# The engine has no Python dependencies, so the image is the runtime plus the
# source. The dashboard is built in a separate stage and copied in, which keeps
# Node out of the final image.

FROM node:22-alpine AS dashboard
WORKDIR /build
COPY dashboard/package.json dashboard/package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY dashboard/ ./
RUN npm run build

FROM python:3.13-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DB_PATH=/data/jobseeker.db \
    LETTERS_DIR=/data/letters \
    CV_DIR=/data/cv \
    PORT=8000

WORKDIR /app

# A non root user, and /data is where the Azure Files volume gets mounted.
RUN useradd --create-home --uid 10001 jobseeker \
    && mkdir -p /data && chown -R jobseeker:jobseeker /data /app

COPY --chown=jobseeker:jobseeker jobseeker/ ./jobseeker/
COPY --chown=jobseeker:jobseeker data/ ./data/
COPY --chown=jobseeker:jobseeker --from=dashboard /build/dist ./dashboard/dist

USER jobseeker
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=4s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request,os,sys; \
        req=urllib.request.Request(f'http://127.0.0.1:{os.environ.get(\"PORT\",8000)}/api/health', \
        headers={'Authorization': 'Bearer ' + os.environ.get('API_TOKEN','')}); \
        sys.exit(0 if urllib.request.urlopen(req, timeout=3).status == 200 else 1)"

CMD ["sh", "-c", "python3 -m jobseeker serve --host 0.0.0.0 --port ${PORT}"]
