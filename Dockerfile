FROM python:3.10-slim

WORKDIR /app

# Install curl for HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

ENV PYTHONUNBUFFERED=1

# Super simple healthcheck
HEALTHCHECK --interval=5s --timeout=3s --start-period=2s --retries=5 \
  CMD curl -f http://localhost:8080/ || exit 1

CMD ["python", "inference.py"]