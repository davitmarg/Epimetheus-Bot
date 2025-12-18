FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for data persistence
RUN mkdir -p /app/chroma_db

# Expose the API port
EXPOSE 8000

# Run the application
# By default, runs all services (bot, updater, api)
# To run a specific service, override CMD:
#   CMD ["python", "main.py", "bot"]      # Run only bot
#   CMD ["python", "main.py", "updater"]   # Run only updater
#   CMD ["python", "main.py", "api"]       # Run only API service
CMD ["python", "main.py"]

