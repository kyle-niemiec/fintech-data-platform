FROM apache/airflow:2.10.4-python3.12

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

USER airflow

COPY services/pipeline-orchestrator/requirements.txt /tmp/worker-requirements.txt
RUN pip install --no-cache-dir -r /tmp/worker-requirements.txt

# Place shared lib files on PYTHONPATH so DAGs can import `meridian.libs.*`.
COPY --chown=airflow:airflow services/libs /opt/airflow/meridian/libs
ENV PYTHONPATH=/opt/airflow:${PYTHONPATH}

COPY --chown=airflow:airflow services/pipeline-orchestrator/dags /opt/airflow/dags
