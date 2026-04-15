FROM python:3.12-slim

WORKDIR /app

COPY services/pipeline-workers/workers/cdc_bronze_writer/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY platform/libs /app/libs
COPY services/pipeline-workers/workers/cdc_bronze_writer /app/workers/cdc_bronze_writer

ENV PYTHONPATH=/app
CMD ["python", "-m", "workers.cdc_bronze_writer.main"]
