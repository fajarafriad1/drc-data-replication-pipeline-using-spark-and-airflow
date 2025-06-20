
# 🔄 DRC Data Replication Pipeline  
### Using Apache Spark, HDFS & Airflow in a Simulated Disaster Recovery Cluster

A containerized data engineering solution that replicates transactional data from a **Data Center (DC)** to a **Disaster Recovery Center (DRC)**. This project uses **Apache Spark** for data processing, **HDFS** for storage, and **Apache Airflow** for orchestrating the ETL pipeline. 

This project is designed for learning, simulation, or as a base for enterprise-grade disaster recovery pipelines.

---

## 📌 Overview

This project simulates a real-world disaster recovery setup where data generated in a primary cluster is automatically synced to a secondary backup cluster (DRC). It includes:

- Spark jobs to generate and replicate data  
- HDFS clusters for both Primary and Secondary DCs  
- Airflow DAGs for orchestration and monitoring  
- Docker-based deployment for ease of use

---

## 🏗️ Architecture

```text
+-----------------------------+
|     Apache Airflow DAG     |
| +-----------------------+  |
| | Generate PARQUET Data |  |  
| +-----------------------+  |
| | Submit Spark Job      |  |
| +-----------------------+  |
| | Validate Output       |  |
+-------------|---------------+
              |
              v
+-----------------------------+   sync to   +-----------------------------+
| Primary DC (HDFS + Spark)  |  ----------> | Secondary DC (HDFS / DRC)   |
+-----------------------------+             +-----------------------------+
```

---

## ⚙️ Services

| Service                         | Role                    | Port(s)       | Profile       |
|---------------------------------|--------------------------|---------------|---------------|
| HDFS NameNode (Primary DC)      | Storage Manager          | 11870, 11020  | primary-dc    |
| HDFS DataNode (Primary DC)      | Data Storage Node        | 11864         | primary-dc    |
| Spark Master                    | Job Driver               | 11190, 11077  | primary-dc    |
| Spark Worker                    | Job Executor             | 11191         | primary-dc    |
| Airflow Webserver               | ETL Orchestrator UI      | 11080         | primary-dc    |
| Airflow Scheduler               | DAG Trigger              | (internal)    | primary-dc    |
| PostgreSQL                      | Airflow Backend          | (internal)    | primary-dc    |
| HDFS NameNode (Secondary DC)    | Backup Storage Manager   | 21870, 21020  | secondary-dc  |
| HDFS DataNode (Secondary DC)    | Backup Data Storage      | 21864         | secondary-dc  |

---

## 📁 Project Structure

```
drc-project/
├── airflow/                            # DAGs, logs, plugins
│   └── dags/
│       ├── bank-transaction-hdfs-ingest-dag.py
│       └── dcr-sync-dag.py
├── spark-jobs/                         # PySpark job scripts
│   ├── bank-transaction-hdfs-ingest-script.py
|   ├── dcr-sync-script.py
│   └── dcr-project.env
├── spark/                              # Spark app directory (bind mounted)
├── hadoop-primary/                     # HDFS for primary DC
├── hadoop-secondary/                   # HDFS for secondary DRC
├── postgres/                           # PostgreSQL volume
├── Dockerfile.airflow                  # Custom Airflow image
├── Dockerfile.spark                    # Custom Spark image
├── Dockerfile.hadoop-namenode
├── Dockerfile.hadoop-datanode
├── docker-compose.yml                  # Service definitions
├── requirements.txt                    # Spark job dependencies
├── requirements-airflow.txt            # Airflow-specific dependencies
└── README.md
```

---

## 🔧 Prerequisites

- Docker & Docker Compose
- 8 GB RAM or more recommended
- Ports 11080, 11870, 21870 etc. available

---


## 🚀 Getting Started

### 1. Clone the repository
```bash
git clone https://github.com/fajarafriad1/drc-data-replication-pipeline-using-spark-and-airflow.git
cd drc-data-replication-pipeline-using-spark-and-airflow
```

### 2. Build and start services

Build and start the Primary DC services:

```bash
docker compose --profile primary-dc up --build
```
Wait until the build and startup complete. Then build and start the Secondary DC services:

```bash
docker compose --profile secondary-dc up --build
```
### 3. Create HDFS Shared Directory

After both HDFS clusters are running, open a terminal in the NameNode containers and create the shared directory.

#### 🔹 Primary DC

```bash
docker exec -it drc-project-primary-dc-namenode hdfs dfs -mkdir -p /user/shared-directory/ && \
docker exec -it drc-project-primary-dc-namenode hdfs dfs -chmod -R 777 /user/shared-directory/
```

#### 🔹 Secondary DC

```bash
docker exec -it drc-project-secondary-dc-namenode hdfs dfs -mkdir -p /user/shared-directory/ && \
docker exec -it drc-project-secondary-dc-namenode hdfs dfs -chmod -R 777 /user/shared-directory/
```

### 4. Access Airflow

Open Airflow in your browser:

📍 http://localhost:11080

- **Username**: `admin`
- **Password**: `admin`


### 5. Fix Folder Permissions (Optional but Recommended)

If you encounter permission errors like:

```text
PermissionError: [Errno 13] Permission denied: ...'
```

Run the following:

```bash
sudo chmod -R 777 ./hadoop-primary/namenode ./hadoop-primary/datanode
sudo chmod -R 777 ./hadoop-secondary/namenode ./hadoop-secondary/datanode
sudo chmod -R 777 ./airflow/dags
sudo chmod -R 777 ./spark-jobs
```

This ensures Airflow and Spark containers can access necessary volumes.

---

## 📋 Airflow DAGs (Example Usecase)

### 🟢 `bank-transaction-hdfs-ingest-dag`
- Generates dummy bank transactions and convert to dataframe using PySpark  
- Writes output as PARQUET to Primary HDFS

### 🔁 `dcr-sync-dag`
- Waits for the first job to finish (using ExternalTaskSensor in Airflow)
- Reads PARQUET from Primary DC HDFS  
- Writes replicated data to DRC (Secondary DC HDFS)

---

## 🔌 Airflow Spark Connection Configuration

To enable **Apache Airflow** to submit Spark jobs, create a Spark connection via the **Airflow UI** or using the **Airflow CLI/API**.

> Navigate to **Admin → Connections** and add the following configuration:

| **Field**         | **Value**                                                                 |
|-------------------|---------------------------------------------------------------------------|
| **Connection Id** | `spark_client_conn`                                                       |
| **Connection Type** | `Spark` *(Install provider: `apache-airflow-providers-apache-spark`)* |
| **Host**          | `spark://drc-project-primary-dc-spark-master`                             |
| **Port**          | `7077`                                                                    |
| **Deploy Mode**   | `client` *(Options: `client` or `cluster`)*                               |
| **Spark Binary**  | `spark-submit` *(Options: `spark-submit`, `spark2-submit`, `spark3-submit`)* |
| **YARN Queue**    | *(optional, leave blank if not using YARN)*                               |
| **Description**   | Spark connection for submitting jobs from Airflow                         |


This connection is used by the `SparkSubmitOperator` in your Airflow DAGs to launch Spark jobs against the Spark master running in the **Primary DC** container.

---

## 🧪 Sample .env (`drc-project.env`)

```env
# Primary Data Center HDFS URI
PRIMARY_DC=hdfs://drc-project-primary-dc-namenode:8020/

# Secondary Data Center HDFS URI
SECONDARY_DC=hdfs://drc-project-secondary-dc-namenode:8020/

# Directory path in HDFS
HDFS_PATH=/user/shared-directory/

# Name of the transaction data file
FILENAME=bank_transactions.parquet
```

---

## 🧰 Built With

- [Apache Spark](https://spark.apache.org/)
- [Apache Airflow](https://airflow.apache.org/)
- [Hadoop HDFS](https://hadoop.apache.org/)
- [Docker Compose](https://docs.docker.com/compose/)

---

## 📄 License

This project is licensed under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).

---

## 🙋‍♂️ Author

**Fajar Afriadi**  
_Data Engineer_
📫 [LinkedIn](https://www.linkedin.com/in/fajar-afriadi/)
