FROM python:3.10-slim

WORKDIR /app

# Install curl for HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Match the app_port in README and the port in inference.py
EXPOSE 8080

ENV PYTHONUNBUFFERED=1

# Platform uses this to verify the server is ready
HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=10 \
  CMD curl -f http://localhost:8080/health || exit 1

CMD ["python", "inference.py"]