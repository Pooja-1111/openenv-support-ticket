# Use 3.11 to satisfy the requirement mentioned in the logs
FROM python:3.11-slim

WORKDIR /app

# Install dependencies (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your script
COPY inference.py .

# Expose the standard port
EXPOSE 8080

# Platform uses this to verify the server is ready
HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=10 \
  CMD curl -f http://localhost:8080/ || exit 1

# Standard hackathon entry point
CMD ["python", "inference.py"]