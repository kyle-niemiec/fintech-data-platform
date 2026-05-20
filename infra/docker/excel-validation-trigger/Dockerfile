FROM python:3.12-slim

WORKDIR /app

COPY infra/python-reqs/excel-validation-trigger.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY services/libs /app/meridian/libs
COPY services/workers/excel_validation_trigger /app/workers/excel_validation_trigger

ENV PYTHONPATH=/app
CMD ["python", "-m", "workers.excel_validation_trigger.main"]
