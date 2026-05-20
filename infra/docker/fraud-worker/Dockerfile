FROM python:3.12-slim

WORKDIR /app

COPY infra/python-reqs/fraud-worker.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY services/libs /app/meridian/libs
COPY services/workers/fraud_worker /app/workers/fraud_worker

ENV PYTHONPATH=/app
CMD ["python", "-m", "workers.fraud_worker.main"]
