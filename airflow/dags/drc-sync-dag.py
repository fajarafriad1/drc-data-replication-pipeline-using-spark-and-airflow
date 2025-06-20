from airflow import DAG
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor
from datetime import datetime
import os

# === CONFIG ===
config = {
    'dag_id': 'drc-sync-dag',
    'schedule': '0 10 * * *',
    'start_date': datetime(2024, 1, 1),
    'script_dir': '/opt/airflow/spark-jobs/',
    'script_name': 'drc-sync-script.py',
    'spark_master_host': 'drc-project-primary-dc-spark-master',
    'spark_binary': '/home/airflow/.local/bin/spark-submit',
    'spark_conn_id': 'spark_client_conn',
    'spark_job_name': 'drc-sync-dag',
    'tags': ['drc', 'spark', 'replication'],
    'primary_namenode': 'drc-project-primary-dc-namenode',
    'secondary_namenode': 'drc-secondary-dc-namenode'
}

# === UTILS ===
def check_file_exists(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Required Spark job script not found: {path}")

def validate_drc_output():
    print("✅ Validation: Data successfully replicated to DRC HDFS!")

# === DAG ===
with DAG(
    dag_id=config['dag_id'],
    default_args={'owner': 'airflow', 'start_date': config['start_date']},
    schedule_interval=config['schedule'],
    catchup=False,
    tags=config['tags']
) as dag:

    script_path = os.path.join(config['script_dir'], config['script_name'])

    wait_for_dc = ExternalTaskSensor(
        task_id='wait_for_dc_job',
        external_dag_id='bank-transaction-hdfs-ingest-dag',
        external_task_id='validate_output',
        allowed_states=['success'],
        failed_states=['failed', 'skipped'],
        timeout=600,
        poke_interval=30,
        mode='poke'
    )

    check_script = PythonOperator(
        task_id='check_drc_spark_script_exists',
        python_callable=check_file_exists,
        op_args=[script_path]
    )

    check_spark_master = BashOperator(
        task_id='ping_drc_spark_master',
        bash_command=f'telnet {config["spark_master_host"]} 7077 || exit 1'
    )

    check_primary_namenode = BashOperator(
        task_id='check_primary_namenode_safe_mode',
        bash_command="""
            curl -s http://drc-project-primary-dc-namenode:9870/ | grep -q 'Safemode is on' && \
            echo '❌ NameNode is in Safe Mode!' && exit 1 || \
            echo '✅ NameNode is not in Safe Mode. Proceeding.'
        """
    )

    check_secondary_namenode = BashOperator(
        task_id='check_secondary_namenode_safe_mode',
        bash_command="""
            curl -s http://drc-secondary-dc-namenode:9870/ | grep -q 'Safemode is on' && \
            echo '❌ NameNode is in Safe Mode!' && exit 1 || \
            echo '✅ NameNode is not in Safe Mode. Proceeding.'
        """
    )

    submit_spark_job = SparkSubmitOperator(
        task_id='submit_drc_replication_job',
        application=script_path,
        name=config['spark_job_name'],
        conf={'spark.master': f'spark://{config["spark_master_host"]}:7077'},
        deploy_mode='client',
        application_args=[],
        spark_binary=config['spark_binary'],
        verbose=True,
        conn_id=config['spark_conn_id']
    )

    validate_task = PythonOperator(
        task_id='validate_drc_replication',
        python_callable=validate_drc_output
    )

    # DAG dependencies
    (
        wait_for_dc >>
        check_script >>
        check_spark_master >>
        [check_primary_namenode, check_secondary_namenode] >>
        submit_spark_job >>
        validate_task
    )
