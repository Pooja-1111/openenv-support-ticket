FROM python:3.10-slim

WORKDIR /app

# Install curl for HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose both common ports
EXPOSE 8080 8000

ENV PYTHONUNBUFFERED=1

# Healthcheck that covers both possibilities
HEALTHCHECK --interval=3s --timeout=2s --start-period=5s --retries=5 \
  CMD curl -f http://localhost:8080/ || curl -f http://localhost:8000/ || exit 1

CMD ["python3", "inference.py"]