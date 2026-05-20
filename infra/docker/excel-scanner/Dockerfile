FROM python:3.12-slim

WORKDIR /app

COPY infra/python-reqs/excel-scanner.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY services/libs /app/meridian/libs
COPY services/workers/excel_scanner /app/workers/excel_scanner

ENV PYTHONPATH=/app
CMD ["python", "-m", "workers.excel_scanner.main"]
