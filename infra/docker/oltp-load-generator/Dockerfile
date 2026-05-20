FROM python:3.12-slim

WORKDIR /app

COPY infra/python-reqs/oltp-load-generator.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY services/workers/oltp_load_generator /app/workers/oltp_load_generator

ENV PYTHONPATH=/app
CMD ["python", "-m", "workers.oltp_load_generator.main"]
