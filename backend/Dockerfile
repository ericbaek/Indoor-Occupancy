FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_DEBUG=false \
    DATABASE_PATH=/app/instance/occupancy.db

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN mkdir -p /app/instance

EXPOSE 5000

# BLE state is intentionally in memory, so use one worker with multiple
# threads. Multiple workers would each hold a different Left/Right count.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "30", "app:create_app()"]
