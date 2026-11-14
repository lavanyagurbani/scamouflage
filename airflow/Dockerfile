FROM apache/airflow:2.11.1-python3.11

USER root
RUN mkdir -p /opt/dbt /opt/airflow/state /opt/airflow/dbt-target \
    && chown -R airflow:root /opt/dbt /opt/airflow/state /opt/airflow/dbt-target
USER airflow

# Isolate dbt's older dependency graph from Airflow. No runtime pip installs.
COPY --chown=airflow:root dbt-requirements.txt /tmp/dbt-requirements.txt
RUN python -m venv /opt/dbt \
    && /opt/dbt/bin/python -m pip install --no-user --no-cache-dir -r /tmp/dbt-requirements.txt \
    && /opt/dbt/bin/python -m pip check \
    && /opt/dbt/bin/dbt --version

# Only this small airflow/ directory is the Docker build context; no ADC or data.
COPY --chown=airflow:root init_user.py /opt/airflow/init_user.py
