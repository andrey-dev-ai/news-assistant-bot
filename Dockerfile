# Railway Dockerfile for AI News Assistant Bot
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create data directory for SQLite
RUN mkdir -p /app/data

# Run the scheduler (24/7 operation)
CMD ["python", "scheduler.py"]
