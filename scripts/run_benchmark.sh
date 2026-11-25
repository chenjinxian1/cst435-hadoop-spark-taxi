#!/usr/bin/env bash
# Run an experiment plan (from the host with Git Bash, or on the cloud master VM).
#   scripts/run_benchmark.sh experiments/local.plan
#   CLUSTER_SH=cloud/cluster-cloud.sh ENV_LABEL=azure scripts/run_benchmark.sh experiments/cloud.plan
#
# Plan file: one block per line ("#" starts a comment)
#   <workers> <tier> <framework[,framework...]> <reps>
# Blocks run in file order; the cluster is rebuilt whenever <workers> changes.
# Every run appends one row to results/benchmark.csv (MapReduce runs also to
# results/counters.csv). Runs already recorded as "ok" are skipped, so an
# interrupted sweep is resumed by re-running the same command.
set -uo pipefail
export MSYS_NO_PATHCONV=1
ROOT="$(cd "$(dirname "$0")/.." && (pwd -W 2>/dev/null || pwd))"  # Windows path under Git Bash

PLAN="${1:?usage: run_benchmark.sh <plan file>}"
JOBS="${JOBS:-demand routes fare}"
ENV_LABEL="${ENV_LABEL:-local-docker}"
CLUSTER_SH="${CLUSTER_SH:-$ROOT/scripts/cluster.sh}"
OUT="$ROOT/results/benchmark.csv"
COUNTERS="$ROOT/results/counters.csv"

mkdir -p "$ROOT/results/logs"
[ -f "$OUT" ] || echo "timestamp,env,framework,job,tier,nodes,rep,seconds,status" > "$OUT"
[ -f "$COUNTERS" ] || echo "env,framework,job,tier,nodes,rep,map_tasks,map_output_records,combine_output_records,reduce_shuffle_bytes" > "$COUNTERS"

already_done() { grep -q "^[^,]*,$ENV_LABEL,$1,$2,$3,$4,$5,[^,]*,ok$" "$OUT"; }
counter() { sed -n "s/^[[:space:]]*$1=\([0-9]*\).*/\1/p" "$2" | head -1; }

run_one() {  # run_one <fw> <job> <tier> <nodes> <rep>
  local fw=$1 job=$2 tier=$3 n=$4 rep=$5 line secs status log
  if already_done "$fw" "$job" "$tier" "$n" "$rep"; then
    printf '  %-14s %-7s %-3s n=%s rep=%s  (already done)\n' "$fw" "$job" "$tier" "$n" "$rep"; return
  fi
  line=$(docker exec master /opt/scripts/run_job.sh "$fw" "$job" "$tier" "$n" | grep '^SECONDS')
  if [ -n "$line" ]; then secs="${line#SECONDS }"; status=ok; else secs=""; status=failed; fi
  echo "$(date -Iseconds),$ENV_LABEL,$fw,$job,$tier,$n,$rep,$secs,$status" >> "$OUT"
  printf '  %-14s %-7s %-3s n=%s rep=%s  %8ss  %s\n' "$fw" "$job" "$tier" "$n" "$rep" "$secs" "$status"
  log="$ROOT/results/logs/$fw-$job-$tier-n$n.log"
  if [ "$status" = ok ] && [ "${fw#mr}" != "$fw" ] && [ -f "$log" ]; then
    echo "$ENV_LABEL,$fw,$job,$tier,$n,$rep,$(counter 'Launched map tasks' "$log"),$(counter 'Map output records' "$log"),$(counter 'Combine output records' "$log"),$(counter 'Reduce shuffle bytes' "$log")" >> "$COUNTERS"
  fi
}

block_done() {  # block_done <n> <tier> <fws> <reps>: every run of the block already ok?
  local job fw nn rep
  for job in $JOBS; do for fw in ${3//,/ }; do
    nn="$1"; [ "$fw" = serial ] && nn=1
    for rep in $(seq 1 "$4"); do already_done "$fw" "$job" "$2" "$nn" "$rep" || return 1; done
  done; done
}

current=""
while read -r n tier fws reps _ <&3; do
  case "${n:-#}" in \#*) continue ;; esac
  if block_done "$n" "$tier" "$fws" "$reps"; then echo "--- skip n=$n tier $tier (all runs done)"; continue; fi
  if [ "$n" != "$current" ]; then
    echo "=== $(date '+%F %T')  cluster with $n worker(s) ==="
    if ! "$CLUSTER_SH" up "$n"; then echo "cluster start failed for n=$n" >&2; current=""; continue; fi
    current="$n"
  fi
  echo "--- tier $tier: $fws x $reps"
  "$CLUSTER_SH" load "$tier" || { echo "load failed for $tier" >&2; continue; }
  for job in $JOBS; do
    for fw in ${fws//,/ }; do
      nn="$n"; [ "$fw" = serial ] && nn=1      # serial baseline is one process
      for rep in $(seq 1 "$reps"); do run_one "$fw" "$job" "$tier" "$nn" "$rep"; done
    done
  done
done 3< "$PLAN"
echo "=== $(date '+%F %T')  plan finished; results in $OUT"
