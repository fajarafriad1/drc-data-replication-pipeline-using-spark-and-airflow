from pyspark.sql import SparkSession
import os

# -------------------- Utilities --------------------

def load_env(filepath):
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.split("#", 1)[0].strip()
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

# -------------------- Main Sync Logic --------------------

try:
    # ✅ Load environment file relative to script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(script_dir, "drc-project.env")
    if not os.path.exists(env_path):
        raise FileNotFoundError(f"❌ drc-project.env not found at: {env_path}")

    load_env(env_path)
    print(f"✅ Loaded env from {env_path}")

    # ✅ Build HDFS paths
    PRIMARY_DC_PATH = build_hdfs_path("PRIMARY_DC", "HDFS_PATH", "FILENAME")
    SECONDARY_DC_PATH = build_hdfs_path("SECONDARY_DC", "HDFS_PATH", "FILENAME")

    # ✅ Start Spark
    spark = SparkSession.builder \
        .appName("SyncToDRC") \
        .master("spark://drc-project-primary-dc-spark-master:7077") \
        .config("spark.eventLog.enabled", "true") \
        .config("spark.eventLog.dir", "file:///opt/airflow/spark-events") \
        .config("spark.hadoop.fs.hdfs.impl", "org.apache.hadoop.hdfs.DistributedFileSystem") \
        .config("spark.hadoop.fs.hdfs.impl.disable.cache", "true") \
        .config("spark.hadoop.dfs.client.use.datanode.hostname", "true") \
        .getOrCreate()

    jvm = spark._jvm
    hadoop_conf = spark._jsc.hadoopConfiguration()

    # ✅ Check source file
    src_exists, _, src_path = check_hdfs_path_exists(jvm, hadoop_conf, PRIMARY_DC_PATH)
    if not src_exists:
        raise FileNotFoundError(f"❌ Source path does not exist: {src_path}")
    print(f"✅ Source path found: {src_path}")

    # ✅ Read source file (PARQUET)
    df = spark.read.parquet(PRIMARY_DC_PATH)
    df.show(5, truncate=False)

    # ✅ Check and write to target
    tgt_exists, _, tgt_path = check_hdfs_path_exists(jvm, hadoop_conf, SECONDARY_DC_PATH)
    if tgt_exists:
        print(f"⚠️ Target path already exists: {tgt_path} — Overwriting.")
    else:
        print(f"✅ Target path does not exist — Writing new file.")

    print(f"➡️ Writing data to: {tgt_path}")
    df.write.mode("overwrite").parquet(SECONDARY_DC_PATH)

    # ✅ Validate
    record_count = spark.read.parquet(SECONDARY_DC_PATH).count()
    print(f"✅ Write successful to {SECONDARY_DC_PATH}. Record count: {record_count}")

except Exception as e:
    print(f"❌ Error occurred during sync: {e}")
    raise

finally:
    try:
        spark.stop()
        print("🛑 Spark session has been stopped.")
    except NameError:
        print("⚠️ Spark session was never created.")
    except Exception as stop_err:
        print(f"⚠️ Error while stopping Spark session: {stop_err}")
