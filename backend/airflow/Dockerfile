FROM apache/airflow:2.10.4-python3.12

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

USER airflow

COPY airflow/requirements.txt /tmp/worker-requirements.txt
RUN pip install --no-cache-dir -r /tmp/worker-requirements.txt

# Place our shared libs on PYTHONPATH so DAGs can
# `from libs.platform_events...` and `from libs.excel_validation...`.
COPY --chown=airflow:airflow libs /opt/airflow/platform_libs/libs
ENV PYTHONPATH=/opt/airflow/platform_libs:${PYTHONPATH}

COPY --chown=airflow:airflow airflow/dags /opt/airflow/dags
