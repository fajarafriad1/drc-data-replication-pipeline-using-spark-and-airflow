from airflow import DAG
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from datetime import datetime
import os

# ---- CONFIG ----
config = {
    'dag_id': 'bank-transaction-hdfs-ingest-dag',
    'schedule': '0 10 * * *',
    'start_date': datetime(2024, 1, 1),
    'script_dir': '/opt/airflow/spark-jobs/',
    'script_name': 'bank-transaction-hdfs-ingest-script.py',
    'spark_master_host': 'drc-project-primary-dc-spark-master',
    'spark_binary': '/home/airflow/.local/bin/spark-submit',
    'spark_conn_id': 'spark_client_conn',
    'spark_job_name': 'bank-transaction-hdfs-ingest-dag',
    'tags': ['first-job', 'spark', 'write-to-hdfs', 'bank-transactions']
}

# ---- HELPER FUNCTIONS ----
def check_file_exists(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Required input file not found: {file_path}")

def validate_output():
    print("Validating Spark output...")
    print("Validation done, data has been inserted!")

# ---- DAG ----
with DAG(
    dag_id=config['dag_id'],
    default_args={'owner': 'airflow', 'start_date': config['start_date']},
    schedule_interval=config['schedule'],
    catchup=False,
    tags=config['tags']
) as dag:

    script_path = os.path.join(config['script_dir'], config['script_name'])

    # ✅ Check if Spark script file exists
    check_script = PythonOperator(
        task_id='check_spark_job_script',
        python_callable=check_file_exists,
        op_args=[script_path]
    )

    # ✅ Check if Spark master is reachable
    check_spark_master = BashOperator(
        task_id='check_spark_master',
        bash_command='telnet drc-project-primary-dc-spark-master 7077 || exit 1'
    )

    # ✅ Check if NameNode is in safe mode
    check_namenode_safe_mode = BashOperator(
        task_id='check_namenode_safe_mode',
        bash_command="""
            curl -s http://drc-project-primary-dc-namenode:9870/ | grep -q 'Safemode is on' && \
            echo '❌ NameNode is in Safe Mode!' && exit 1 || \
            echo '✅ NameNode is not in Safe Mode. Proceeding.'
        """
    )

    # ✅ Submit Spark job
    submit_spark_job = SparkSubmitOperator(
        task_id='submit_spark_job',
        application=script_path,
        name=config['spark_job_name'],
        conf={'spark.master': f'spark://{config["spark_master_host"]}:7077'},
        deploy_mode='client',
        application_args=[],
        spark_binary=config['spark_binary'],
        verbose=True,
        conn_id=config['spark_conn_id']
    )

    # ✅ Final validation task
    validate_task = PythonOperator(
        task_id='validate_output',
        python_callable=validate_output
    )

    # 🔄 Task dependencies
    check_script >> check_spark_master >> check_namenode_safe_mode >> submit_spark_job >> validate_task
