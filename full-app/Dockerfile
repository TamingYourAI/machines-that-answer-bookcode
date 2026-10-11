# Open Voice Agents: one image, one process. Local models are not included (see
# docs/providers.md); hosted providers and the browser's voice need nothing more.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OVA_DATA_DIR=/data
WORKDIR /app
COPY pyproject.toml requirements.lock README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir -c requirements.lock ".[server,webrtc,pdf]"
RUN useradd --create-home ova && mkdir -p /data && chown ova /data
USER ova
VOLUME ["/data"]
EXPOSE 8080
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz')"
CMD ["ova", "serve", "--host", "0.0.0.0", "--port", "8080"]
