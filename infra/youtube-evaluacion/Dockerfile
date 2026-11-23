FROM debian:trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg python3 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY medir.py /medir.py
ENTRYPOINT ["python3", "/medir.py"]
