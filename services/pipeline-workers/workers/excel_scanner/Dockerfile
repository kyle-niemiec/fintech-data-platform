FROM python:3.12-slim

WORKDIR /app

COPY services/pipeline-workers/workers/excel_scanner/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY platform/libs /app/libs
COPY services/pipeline-workers/workers/excel_scanner /app/workers/excel_scanner

ENV PYTHONPATH=/app
CMD ["python", "-m", "workers.excel_scanner.main"]
