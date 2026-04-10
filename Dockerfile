FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose ALL possible ports
EXPOSE 8080 80 8000 3000

ENV PYTHONUNBUFFERED=1

# Use exec form to ensure proper signal handling
CMD ["python", "inference.py"]