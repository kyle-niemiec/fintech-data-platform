FROM python:3.12-slim

WORKDIR /app

COPY services/pipeline-workers/workers/oltp_load_generator/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY services/pipeline-workers/workers/oltp_load_generator /app/workers/oltp_load_generator

ENV PYTHONPATH=/app
CMD ["python", "-m", "workers.oltp_load_generator.main"]
