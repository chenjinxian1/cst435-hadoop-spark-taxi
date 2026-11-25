#!/usr/bin/env bash
# Start the Hadoop/YARN daemons for this node's role, then keep the container alive.
#   master : NameNode + ResourceManager + MapReduce JobHistory server
#   worker : DataNode + NodeManager
set -euo pipefail
ROLE="${1:-worker}"

case "$ROLE" in
  master)
    if [ ! -d /hdfs/nn/current ]; then
      echo "[entrypoint] formatting HDFS NameNode"
      hdfs namenode -format -force -nonInteractive cluster435
    fi
    hdfs --daemon start namenode
    yarn --daemon start resourcemanager
    mapred --daemon start historyserver
    ;;
  worker)
    # Wait for the master before registering.
    until nc -z master 9000; do echo "[entrypoint] waiting for master"; sleep 2; done
    hdfs --daemon start datanode
    yarn --daemon start nodemanager
    ;;
  *)
    exec "$@"
    ;;
esac

echo "[entrypoint] $ROLE daemons started on $(hostname)"
exec tail -F /opt/hadoop/logs/*.log
