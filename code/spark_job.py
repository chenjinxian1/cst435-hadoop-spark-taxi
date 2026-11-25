#!/usr/bin/env python3
"""PySpark implementation of the same three analytics jobs.

  spark-submit --master yarn --py-files mapper.py spark_job.py \
      --job demand --api rdd --input hdfs:///input/S --output hdfs:///out/x

--api rdd : RDD API, re-uses parse()/map_record() from mapper.py, so the
            logic is identical to the Hadoop Streaming version
            (flatMap = map phase, reduceByKey = combine + shuffle + reduce).
--api df  : DataFrame API; same filters expressed as Spark SQL so they run
            inside the JVM (Catalyst optimiser, no Python per-record cost).

Both write "<key>\t<v1,v2,...>" text lines, the same format as reducer.py,
so outputs can be compared with scripts/compare_outputs.py.
"""
import argparse

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql import types as T


def run_rdd(spark, job, inp, out, partitions):
    import mapper  # shipped with --py-files

    def to_pairs(line):
        rec = mapper.parse(line)
        if rec is None:
            return []
        return list(mapper.map_record(job, rec))

    def add(a, b):
        return tuple(x + y for x, y in zip(a, b))

    lines = spark.sparkContext.textFile(inp)
    result = lines.flatMap(to_pairs).reduceByKey(add, numPartitions=partitions)
    result.map(lambda kv: f"{kv[0]}\t{mapper.fmt(kv[1])}").saveAsTextFile(out)


SCHEMA = T.StructType([
    T.StructField("pickup_datetime", T.StringType()),
    T.StructField("pu", T.StringType()),
    T.StructField("do", T.StringType()),
    T.StructField("dist", T.StringType()),
    T.StructField("fare", T.StringType()),
    T.StructField("tip", T.StringType()),
    T.StructField("total", T.StringType()),
    T.StructField("payment", T.StringType()),
])


def run_df(spark, job, inp, out, partitions):
    spark.conf.set("spark.sql.shuffle.partitions", partitions)
    df = spark.read.csv(inp, schema=SCHEMA, header=False)
    df = df.select(
        F.substring("pickup_datetime", 12, 2).cast("int").alias("hour"),
        F.col("pu").cast("int").alias("pu"),
        F.col("do").cast("int").alias("do"),
        F.col("dist").cast("double").alias("dist"),
        F.col("fare").cast("double").alias("fare"),
        F.col("tip").cast("double").alias("tip"),
        F.coalesce(F.col("payment").cast("double").cast("int"), F.lit(0)).alias("payment"),
    )
    # Same validation rules as mapper.parse(); header lines become NULL and drop out.
    df = df.where(
        F.col("hour").between(0, 23) & F.col("pu").between(1, 265)
        & F.col("do").between(1, 265)
        & (F.col("dist") > 0) & (F.col("dist") < 100)
        & (F.col("fare") > 0) & (F.col("fare") < 1000) & (F.col("tip") >= 0)
    )

    pad3 = lambda c: F.lpad(F.col(c).cast("string"), 3, "0")
    if job == "demand":
        key = F.concat_ws("|", pad3("pu"), F.lpad(F.col("hour").cast("string"), 2, "0"))
        res = df.groupBy(key.alias("k")).agg(F.count("*").alias("n"))
        line = F.concat_ws("\t", "k", F.col("n").cast("string"))
    elif job == "routes":
        key = F.concat_ws("|", pad3("pu"), pad3("do"))
        res = df.groupBy(key.alias("k")).agg(F.count("*").alias("n"))
        line = F.concat_ws("\t", "k", F.col("n").cast("string"))
    elif job == "fare":
        d = F.col("dist")
        bucket = (F.when(d < 1, "00-01mi").when(d < 2, "01-02mi").when(d < 5, "02-05mi")
                  .when(d < 10, "05-10mi").when(d < 20, "10-20mi").otherwise("20-100mi"))
        cc = F.col("payment") == 1
        res = df.groupBy(bucket.alias("k")).agg(
            F.count("*").alias("n"),
            F.sum("fare").alias("fare_sum"),
            F.sum(F.when(cc, 1).otherwise(0)).alias("cc_n"),
            F.sum(F.when(cc, F.col("fare")).otherwise(0.0)).alias("cc_fare"),
            F.sum(F.when(cc, F.col("tip")).otherwise(0.0)).alias("cc_tip"),
        )
        vec = F.concat_ws(",", F.col("n").cast("string"), F.format_string("%.2f", "fare_sum"),
                          F.col("cc_n").cast("string"), F.format_string("%.2f", "cc_fare"),
                          F.format_string("%.2f", "cc_tip"))
        line = F.concat_ws("\t", "k", vec)
    else:
        raise ValueError(job)
    res.select(line.alias("value")).write.text(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True, choices=["demand", "routes", "fare"])
    ap.add_argument("--api", default="rdd", choices=["rdd", "df"])
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--partitions", type=int, default=8)
    a = ap.parse_args()

    spark = SparkSession.builder.appName(f"taxi-{a.job}-{a.api}").getOrCreate()
    (run_rdd if a.api == "rdd" else run_df)(spark, a.job, a.input, a.output, a.partitions)
    spark.stop()


if __name__ == "__main__":
    main()
