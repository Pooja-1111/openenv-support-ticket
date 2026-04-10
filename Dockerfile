FROM python:3.10-slim

WORKDIR /app

# Install curl for healthcheck and system deps
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install ALL dependencies (root + backend)
COPY requirements.txt .
COPY backend/requirements.txt ./backend_requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r backend_requirements.txt

COPY . .

EXPOSE 7860 8080 8000 80 3000

ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=5s --timeout=5s --start-period=15s --retries=12 \
  CMD curl -f http://localhost:8000/ || exit 1

CMD ["python", "inference.py"]