#!/usr/bin/env bash
# Host-side cluster control (run from Git Bash or WSL, Docker Desktop running).
#   scripts/cluster.sh up <N>      fresh cluster with master + N workers (N = 1..4)
#   scripts/cluster.sh load <TIER> copy data tier (S/M/L/XL) into HDFS /input/<TIER>
#   scripts/cluster.sh status      HDFS + YARN node report
#   scripts/cluster.sh down        stop and remove all containers
set -euo pipefail
export MSYS_NO_PATHCONV=1                 # stop Git Bash rewriting /opt/... paths
ROOT="$(cd "$(dirname "$0")/.." && (pwd -W 2>/dev/null || pwd))"  # Windows path under Git Bash
DC=(docker compose -f "$ROOT/cluster/docker-compose.yml")
M=(docker exec master)

wait_for() {  # wait_for <description> <command...>
  local what="$1"; shift
  for _ in $(seq 1 90); do
    if "$@" >/dev/null 2>&1; then echo "  ok: $what"; return 0; fi
    sleep 2
  done
  echo "timeout waiting for $what" >&2; exit 1
}

live_datanodes() { "${M[@]}" hdfs dfsadmin -report 2>/dev/null | sed -n 's/^Live datanodes (\([0-9]*\)).*/\1/p'; }
running_nms()    { "${M[@]}" yarn node -list 2>/dev/null | grep -c RUNNING || true; }
has_datanodes()    { [ "$(live_datanodes)" = "$1" ]; }
has_nodemanagers() { [ "$(running_nms)" = "$1" ]; }

case "${1:-}" in
  up)
    N="${2:?usage: cluster.sh up N}"
    workers=(); for i in $(seq 1 "$N"); do workers+=("worker$i"); done
    "${DC[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
    # Build only when the image is missing (run `docker compose build` after changing the Dockerfile).
    docker image inspect cst435/hadoop-spark:latest >/dev/null 2>&1 || "${DC[@]}" build master
    "${DC[@]}" up -d master "${workers[@]}"
    wait_for "HDFS out of safe mode" "${M[@]}" hdfs dfsadmin -safemode wait
    wait_for "$N live DataNodes"     has_datanodes "$N"
    wait_for "$N YARN NodeManagers"  has_nodemanagers "$N"
    "${M[@]}" bash -c 'hdfs dfs -mkdir -p /spark-jars /spark-logs /input /out &&
                       hdfs dfs -put -f $SPARK_HOME/jars/*.jar /spark-jars/'
    echo "cluster up: master + $N worker(s)"
    ;;
  load)
    T="${2:?usage: cluster.sh load TIER}"
    # Keep only one tier in HDFS at a time (tiers are nested; saves disk).
    "${M[@]}" bash -c "for d in \$(hdfs dfs -ls -C /input 2>/dev/null); do
        [ \"\$d\" != /input/$T ] && hdfs dfs -rm -r -f -skipTrash \"\$d\" >/dev/null; done
      hdfs dfs -test -d /input/$T && exit 0
      hdfs dfs -mkdir -p /input/$T
      while read -r f; do [ -n \"\$f\" ] && hdfs dfs -put /data/csv/\$f /input/$T/; done < /data/csv/$T.list"
    "${M[@]}" hdfs dfs -du -s -h "/input/$T"
    ;;
  status)
    "${M[@]}" hdfs dfsadmin -report | grep -E '^(Live datanodes|Name:|DFS Used:)' || true
    "${M[@]}" yarn node -list
    ;;
  down)
    "${DC[@]}" down -v --remove-orphans
    ;;
  *)
    sed -n '2,6p' "$0"; exit 1 ;;
esac
