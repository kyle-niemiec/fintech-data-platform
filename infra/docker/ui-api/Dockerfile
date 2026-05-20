FROM python:3.12-slim

WORKDIR /app

COPY infra/python-reqs/ui-api.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY services/workers/ui-api /app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
