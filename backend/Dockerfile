FROM python:3.12-slim

# Install SpatiaLite and spatial dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libsqlite3-mod-spatialite \
        libsqlite3-0 \
        libproj-dev \
        libgeos-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Use /home for persistent SQLite storage on Azure App Service
ENV DATABASE_URL=sqlite:////home/data/pacman.db

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
