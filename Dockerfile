FROM python:3.10-slim

WORKDIR /app

# Install curl for HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# README.md says app_port: 8000
EXPOSE 8000

ENV PYTHONUNBUFFERED=1

# Faster healthcheck targeting port 8000
HEALTHCHECK --interval=3s --timeout=2s --start-period=5s --retries=5 \
  CMD curl -f http://localhost:8000/health || exit 1

# Explicitly use python3
CMD ["python3", "inference.py"]