FROM python:3.10-slim

WORKDIR /app

# Install curl for Docker HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose ALL possible ports
EXPOSE 7860 8080 8000 80 3000

ENV PYTHONUNBUFFERED=1

# Docker HEALTHCHECK - the platform uses this to verify the container is alive
HEALTHCHECK --interval=5s --timeout=5s --start-period=10s --retries=12 \
  CMD curl -f http://localhost:7860/health || curl -f http://localhost:8080/health || exit 1

# Use exec form to ensure proper signal handling
CMD ["python", "inference.py"]