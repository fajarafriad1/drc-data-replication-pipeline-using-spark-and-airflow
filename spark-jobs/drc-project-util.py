import os

def load_env(filepath):
    """
    Manually load environment variables from a .env file.
    """
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

def get_env_variable(key, default=None, required=False):
    """
    Get an environment variable.
    If required and missing, raise an error.
    """
    value = os.environ.get(key, default)
    if value is None and required:
        raise EnvironmentError(f"Missing required environment variable: {key}")
    return value

def build_hdfs_path(dc_uri_key, path_key, filename_key):
    """
    Build full HDFS path from 3 env variable keys.
    Example: build_hdfs_path("PRIMARY_DC", "HDFS_PATH", "FILENAME")
    """
    base = get_env_variable(dc_uri_key, required=True)
    folder = get_env_variable(path_key, required=True)
    filename = get_env_variable(filename_key, required=True)
    return base + folder + filename

def check_hdfs_path_exists(jvm, hadoop_conf, path_str):
    """
    Check if an HDFS path exists using JVM FileSystem API.
    Returns: (exists: bool, fs_object, path_object)
    """
    uri = jvm.java.net.URI(path_str)
    fs = jvm.org.apache.hadoop.fs.FileSystem.get(uri, hadoop_conf)
    hdfs_path = jvm.org.apache.hadoop.fs.Path(path_str)
    return fs.exists(hdfs_path), fs, hdfs_path
