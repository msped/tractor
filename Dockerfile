FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
# libpango/libcairo are required for WeasyPrint
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    libffi-dev \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    shared-mime-info \
    netcat-openbsd \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app/

# Copy entrypoint script and make it executable
COPY ./scripts/entrypoint.sh /app/scripts/
RUN chmod +x /app/scripts/entrypoint.sh

# Create directory for static files if it doesn't exist
RUN mkdir -p /app/staticfiles
RUN mkdir -p /app/mediafiles

# Set entrypoint
ENTRYPOINT ["/app/scripts/entrypoint.sh"]