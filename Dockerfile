FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# libpango/libcairo required for WeasyPrint
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    libffi-dev \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    netcat-openbsd \
    libpq-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

COPY ./scripts/entrypoint.sh /app/scripts/
RUN chmod +x /app/scripts/entrypoint.sh

RUN mkdir -p /app/staticfiles /app/mediafiles

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
