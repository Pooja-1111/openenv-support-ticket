# This line fixes the "upgrade to 3.11" warning
FROM python:3.11-slim

WORKDIR /app

# Ensure we have no dependency issues
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure standard ports are open
EXPOSE 8080
EXPOSE 7860

ENV PYTHONUNBUFFERED=1

CMD ["python", "inference.py"]