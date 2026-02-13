FROM python:3.11-slim AS base

WORKDIR /app

# Install dependencies
COPY services/gateway/requirements.txt /app/services/gateway/requirements.txt
RUN pip install --no-cache-dir -r /app/services/gateway/requirements.txt

# Copy shared modules and gateway service
COPY shared/ /app/shared/
COPY services/__init__.py /app/services/__init__.py
COPY services/gateway/ /app/services/gateway/

EXPOSE 8000

CMD ["uvicorn", "services.gateway.app:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
