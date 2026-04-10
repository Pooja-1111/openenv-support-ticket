FROM python:3.10-slim

WORKDIR /app

# Install curl for HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Match the port in inference.py
EXPOSE 8080

ENV PYTHONUNBUFFERED=1

# Healthcheck targeting the internal server
HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=10 \
  CMD curl -f http://localhost:8080/ || exit 1

# Launch the script (daemon uses threading internally)
CMD ["python3", "inference.py"]