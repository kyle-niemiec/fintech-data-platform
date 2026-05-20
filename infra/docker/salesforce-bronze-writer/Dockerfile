FROM python:3.12-slim

WORKDIR /app

COPY infra/python-reqs/salesforce-bronze-writer.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY services/libs /app/meridian/libs
COPY services/workers/salesforce_bronze_writer /app/workers/salesforce_bronze_writer

ENV PYTHONPATH=/app
CMD ["python", "-m", "workers.salesforce_bronze_writer.main"]
