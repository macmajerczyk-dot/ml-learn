FROM python:3.11-slim AS base

WORKDIR /app

# Install dependencies
COPY services/ml_worker/requirements.txt /app/services/ml_worker/requirements.txt
RUN pip install --no-cache-dir -r /app/services/ml_worker/requirements.txt

# Copy shared modules and worker service
COPY shared/ /app/shared/
COPY services/__init__.py /app/services/__init__.py
COPY services/ml_worker/ /app/services/ml_worker/

EXPOSE 8001

CMD ["python", "-m", "services.ml_worker.worker"]
