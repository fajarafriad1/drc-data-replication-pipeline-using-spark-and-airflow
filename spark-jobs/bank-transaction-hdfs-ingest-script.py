from pyspark.sql import SparkSession
from datetime import datetime, timedelta
import random
import os

# -------------------- Utilities --------------------

def load_env(filepath):
    """
    Manually load environment variables from a .env file.
    Supports lines like: KEY=VALUE or KEY=VALUE # comment
    """
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.split("#", 1)[0].strip()  # Remove inline comment
                if key:
                    os.environ[key] = value

def get_env_variable(key, default=None, required=False):
    value = os.environ.get(key, default)
    if value is None and required:
        raise EnvironmentError(f"Missing required environment variable: {key}")
    return value

def build_hdfs_path(dc_uri_key, path_key, filename_key):
    base = get_env_variable(dc_uri_key, required=True)
    folder = get_env_variable(path_key, required=True)
    filename = get_env_variable(filename_key, required=True)
    return base + folder + filename

def check_hdfs_path_exists(jvm, hadoop_conf, path_str):
    uri = jvm.java.net.URI(path_str)
    fs = jvm.org.apache.hadoop.fs.FileSystem.get(uri, hadoop_conf)
    hdfs_path = jvm.org.apache.hadoop.fs.Path(path_str)
    return fs.exists(hdfs_path), fs, hdfs_path

# -------------------- Main Job --------------------

try:
    # 🔍 Resolve .env path based on script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(script_dir, "drc-project.env")

    if not os.path.exists(env_path):
        raise FileNotFoundError(f"❌ drc-project.env not found at: {env_path}")

    load_env(env_path)
    print(f"✅ Environment loaded from {env_path}")

    # Build full HDFS path from env
    PRIMARY_DC_PATH = build_hdfs_path("PRIMARY_DC", "HDFS_PATH", "FILENAME")

    # Create Spark session
    spark = SparkSession.builder \
        .appName("ProduceAndWriteDataToPrimaryDC") \
        .master("spark://drc-project-primary-dc-spark-master:7077") \
        .config("spark.eventLog.enabled", "true") \
        .config("spark.eventLog.dir", "file:///opt/airflow/spark-events") \
        .config("spark.hadoop.fs.hdfs.impl", "org.apache.hadoop.hdfs.DistributedFileSystem") \
        .config("spark.hadoop.fs.hdfs.impl.disable.cache", "true") \
        .config("spark.hadoop.dfs.client.use.datanode.hostname", "true") \
        .getOrCreate()

    # Generate dummy data
    transaction_types = ["DEPOSIT", "WITHDRAWAL", "TRANSFER", "PAYMENT"]
    accounts = [f"ACCT{str(i).zfill(5)}" for i in range(1, 21)]
    base_date = datetime(2025, 6, 1)
    data = []

    for i in range(100):
        txn_id = f"TXN{i+1:04d}"
        account = random.choice(accounts)
        txn_type = random.choice(transaction_types)
        amount = round(random.uniform(10000, 500000), 2)
        rand_days = random.randint(0, 12)
        rand_seconds = random.randint(0, 86399)
        txn_datetime = base_date + timedelta(days=rand_days, seconds=rand_seconds)
        txn_timestamp = txn_datetime.strftime("%Y-%m-%d %H:%M:%S")
        data.append((txn_id, account, txn_type, amount, txn_timestamp))

    columns = ["transaction_id", "account_number", "transaction_type", "amount", "transaction_timestamp"]
    df = spark.createDataFrame(data, columns)

    # Check if HDFS path exists
    hadoop_conf = spark._jsc.hadoopConfiguration()
    jvm = spark._jvm
    exists, fs, hdfs_path = check_hdfs_path_exists(jvm, hadoop_conf, PRIMARY_DC_PATH)

    if exists:
        print(f"⚠️ PARQUET path already exists: {PRIMARY_DC_PATH}, continuing to overwrite.")
    else:
        print(f"✅ Path does not exist. Proceeding to write: {PRIMARY_DC_PATH}")

    # Write to HDFS
    df.write.mode("overwrite").parquet(PRIMARY_DC_PATH)
    record_count = spark.read.parquet(PRIMARY_DC_PATH).count()
    print(f"✅ Write successful to {PRIMARY_DC_PATH}. Record count: {record_count}")


except Exception as e:
    print("❌ Error occurred during Spark job execution:")
    print(e)
    raise

finally:
    try:
        spark.stop()
        print("🛑 Spark session has been stopped.")
    except NameError:
        print("⚠️ Spark was never created.")
    except Exception as stop_err:
        print(f"⚠️ Error while stopping Spark: {stop_err}")
