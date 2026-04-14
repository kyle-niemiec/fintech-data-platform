FROM python:3.12-slim

WORKDIR /app

COPY workers/excel_bronze_writer/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY libs /app/libs
COPY workers/excel_bronze_writer /app/workers/excel_bronze_writer

ENV PYTHONPATH=/app
CMD ["python", "-m", "workers.excel_bronze_writer.main"]
