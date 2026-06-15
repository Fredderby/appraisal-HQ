# Use official Python image
FROM python:3.11-slim

# Set working directory to /app
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy EVERYTHING from current folder into /app
COPY . .

# Expose port 8080
EXPOSE 8080

# ✅ FIXED: Exact path, no mistakes
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]