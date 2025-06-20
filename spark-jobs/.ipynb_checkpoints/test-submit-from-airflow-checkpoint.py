from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("SubmitSparkJobFromAirflowtoHDFS") \
    .master("spark://dc-spark-master:7077") \
    .getOrCreate()


data = [("Fajar", 25), ("Ayu", 30), ("Rizki", 22)]
columns = ["Name", "Age"]

df = spark.createDataFrame(data, columns)
df.show()

try:
    df.write.mode("overwrite").json("hdfs://dc-namenode:8020//user/shared-directory/submit_spark_airflow_json")
    print("write successfull!")
except Exception as e:
    print("failed to write to hdfs!")
    print(e)