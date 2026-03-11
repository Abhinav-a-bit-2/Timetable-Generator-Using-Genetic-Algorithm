# Base image with Python installed
FROM python:3.11-slim

# make sure apt install for tkinter (needed for GUI if someone uses it outside container)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       python3-tk \
    && rm -rf /var/lib/apt/lists/*

# set working directory
WORKDIR /app

# copy requirements first for caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# copy application sources
COPY . /app

# allow overriding database file via environment variable (used by code)
ENV TIMETABLE_DB=/app/timetable.db

# make sure database will be initialized when image is built (optional)
RUN python - <<'PYCODE'
import db_operations
try:
    db_operations.initialize_database()
    print("Database initialized")
except Exception as e:
    print("Failed to initialize database:", e)
PYCODE

# by default open an interactive shell
ENTRYPOINT ["python", "main.py"]
