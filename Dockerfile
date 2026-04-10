FROM python:3.10-slim

WORKDIR /app

# Install curl for HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Multi-port coverage
EXPOSE 8000 8080 7860

ENV PYTHONUNBUFFERED=1

# Universal healthcheck
HEALTHCHECK --interval=3s --timeout=2s --start-period=5s --retries=5 \
  CMD curl -f http://localhost:8000/ || curl -f http://localhost:8080/ || curl -f http://localhost:7860/ || exit 1

CMD ["python3", "inference.py"]