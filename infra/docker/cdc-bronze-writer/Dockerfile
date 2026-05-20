FROM python:3.12-slim

WORKDIR /app

COPY infra/python-reqs/cdc-bronze-writer.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY services/libs /app/meridian/libs
COPY services/workers/cdc_bronze_writer /app/workers/cdc_bronze_writer

ENV PYTHONPATH=/app
CMD ["python", "-m", "workers.cdc_bronze_writer.main"]
