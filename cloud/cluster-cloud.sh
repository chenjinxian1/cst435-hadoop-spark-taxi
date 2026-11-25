#!/usr/bin/env bash
# Cloud counterpart of scripts/cluster.sh. Runs ON the master VM.
#   cloud/cluster-cloud.sh up <N>      fresh cluster: master + worker1..N (N = 1..2)
#   cloud/cluster-cloud.sh load <TIER> / status   (same as scripts/cluster.sh)
#   cloud/cluster-cloud.sh down
# Each VM is one node. Containers use the host network, so the node names in the
# Hadoop configuration (master, worker1, ...) are the VM host names, resolved by
# Azure's internal DNS. No CPU/memory caps: the whole 2-vCPU / 8 GB VM is the node,
# and YARN advertises the same 2 vcores / 3584 MB as in the local cluster.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE=cst435/hadoop-spark:latest
WORKERS=(worker1 worker2)
SSH=(ssh -n -o StrictHostKeyChecking=accept-new -o BatchMode=yes)
M=(docker exec master)

wait_for() {
  local what="$1"; shift
  for _ in $(seq 1 90); do
    if "$@" >/dev/null 2>&1; then echo "  ok: $what"; return 0; fi
    sleep 2
  done
  echo "timeout waiting for $what" >&2; exit 1
}
live_datanodes()   { "${M[@]}" hdfs dfsadmin -report 2>/dev/null | sed -n 's/^Live datanodes (\([0-9]*\)).*/\1/p'; }
running_nms()      { "${M[@]}" yarn node -list 2>/dev/null | grep -c RUNNING || true; }
has_datanodes()    { [ "$(live_datanodes)" = "$1" ]; }
has_nodemanagers() { [ "$(running_nms)" = "$1" ]; }

stop_all() {
  docker rm -f master >/dev/null 2>&1 || true
  for w in "${WORKERS[@]}"; do "${SSH[@]}" "$w" "docker rm -f worker >/dev/null 2>&1 || true"; done
}

case "${1:-}" in
  up)
    N="${2:?usage: cluster-cloud.sh up N}"
    stop_all
    mkdir -p "$ROOT/results"
    docker run -d --name master --network host -e TZ=Asia/Kuala_Lumpur \
      -v "$ROOT/code:/opt/job:ro" -v "$ROOT/scripts:/opt/scripts:ro" \
      -v "$ROOT/data/csv:/data/csv:ro" -v "$ROOT/results:/results" \
      "$IMAGE" master >/dev/null
    for w in "${WORKERS[@]:0:$N}"; do
      "${SSH[@]}" "$w" "docker run -d --name worker --network host -e TZ=Asia/Kuala_Lumpur $IMAGE worker >/dev/null"
    done
    wait_for "HDFS out of safe mode" "${M[@]}" hdfs dfsadmin -safemode wait
    wait_for "$N live DataNodes"     has_datanodes "$N"
    wait_for "$N YARN NodeManagers"  has_nodemanagers "$N"
    "${M[@]}" bash -c 'hdfs dfs -mkdir -p /spark-jars /spark-logs /input /out &&
                       hdfs dfs -put -f $SPARK_HOME/jars/*.jar /spark-jars/'
    echo "cloud cluster up: master + $N worker VM(s)"
    ;;
  load|status)
    exec "$ROOT/scripts/cluster.sh" "$@" ;;
  down)
    stop_all ;;
  *)
    sed -n '2,5p' "$0"; exit 1 ;;
esac
