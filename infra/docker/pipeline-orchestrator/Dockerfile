FROM apache/airflow:3.2.1-python3.12

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

USER airflow

COPY infra/python-reqs/pipeline-orchestrator.txt /tmp/worker-requirements.txt
RUN AIRFLOW_VERSION="$(python -c 'import airflow; print(airflow.__version__)')" \
    && pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" -r /tmp/worker-requirements.txt

# Place shared lib files on PYTHONPATH so DAGs can import `meridian.libs.*`.
COPY --chown=airflow:airflow services/libs /opt/airflow/meridian/libs
ENV PYTHONPATH=/opt/airflow:/opt/airflow/dags:${PYTHONPATH}

COPY --chown=airflow:airflow services/pipeline /opt/airflow/dags
