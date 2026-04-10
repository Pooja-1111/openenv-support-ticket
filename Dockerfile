# Use 3.11 as requested by the warnings
FROM python:3.11-slim

WORKDIR /app

# Ensure we have no dependency issues
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONUNBUFFERED=1

COPY . .

# Expose the ports we are listening on
EXPOSE 7860
EXPOSE 8080

# Run the script
CMD ["python", "inference.py"]