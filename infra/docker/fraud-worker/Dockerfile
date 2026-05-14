FROM python:3.12-slim

WORKDIR /app

COPY services/pipeline-workers/workers/fraud_worker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY platform/libs /app/libs
COPY services/pipeline-workers/workers/fraud_worker /app/workers/fraud_worker

ENV PYTHONPATH=/app
CMD ["python", "-m", "workers.fraud_worker.main"]
