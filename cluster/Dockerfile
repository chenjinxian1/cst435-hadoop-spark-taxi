# One image for every node: Hadoop (HDFS + YARN + MapReduce) and Spark on YARN.
# Role (master / worker) is chosen at run time by entrypoint.sh.
FROM eclipse-temurin:11-jdk-jammy

ARG HADOOP_VERSION=3.4.1
ARG SPARK_VERSION=3.5.5
ARG APACHE_MIRROR=https://archive.apache.org/dist

# All daemons run as an unprivileged user (Hadoop 3 refuses root daemons by default).
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      python3 python3-pip curl procps netcat-openbsd \
 && rm -rf /var/lib/apt/lists/* \
 && ln -sf /usr/bin/python3 /usr/bin/python \
 && useradd -m -s /bin/bash hadoop

# chown happens in the same layer as the extraction: a separate "chown -R"
# layer would store a second copy of every file and double the image size.
RUN curl -fsSL ${APACHE_MIRROR}/hadoop/common/hadoop-${HADOOP_VERSION}/hadoop-${HADOOP_VERSION}.tar.gz \
      | tar -xz -C /opt \
 && mv /opt/hadoop-${HADOOP_VERSION} /opt/hadoop \
 && rm -rf /opt/hadoop/share/doc \
 && mkdir -p /opt/hadoop/logs /hdfs/nn /hdfs/dn \
 && chown -R hadoop:hadoop /opt/hadoop /hdfs

RUN curl -fsSL ${APACHE_MIRROR}/spark/spark-${SPARK_VERSION}/spark-${SPARK_VERSION}-bin-hadoop3.tgz \
      | tar -xz -C /opt \
 && mv /opt/spark-${SPARK_VERSION}-bin-hadoop3 /opt/spark \
 && chown -R hadoop:hadoop /opt/spark

ENV HADOOP_HOME=/opt/hadoop \
    HADOOP_CONF_DIR=/opt/hadoop/etc/hadoop \
    SPARK_HOME=/opt/spark \
    PYSPARK_PYTHON=python3 \
    PATH=/opt/hadoop/bin:/opt/hadoop/sbin:/opt/spark/bin:$PATH

COPY --chown=hadoop:hadoop config/*.xml ${HADOOP_CONF_DIR}/
COPY --chown=hadoop:hadoop config/spark-defaults.conf ${SPARK_HOME}/conf/
COPY entrypoint.sh /entrypoint.sh

RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh \
 && echo "export JAVA_HOME=${JAVA_HOME}" >> ${HADOOP_CONF_DIR}/hadoop-env.sh

USER hadoop
WORKDIR /home/hadoop
ENTRYPOINT ["/entrypoint.sh"]
