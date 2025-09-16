FROM python:3.11-slim AS builder

# Install build dependencies and PostgreSQL client tools
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    build-essential \
    libssl-dev \
    libc-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and entrypoint script first
COPY ./requirements.txt ./requirements.txt
COPY ./entrypoint.sh /app/entrypoint.sh
# COPY . /app

# Ensure entrypoint.sh is executable
RUN chmod +x ./entrypoint.sh

# Install Python dependencies
RUN pip install --user --no-cache-dir -r requirements.txt

# Copy the rest of the application
# COPY . /app

# Set the entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]