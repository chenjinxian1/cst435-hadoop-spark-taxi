#!/usr/bin/env bash
# Page-cache experiment: tests whether the input of a job stays in the workers'
# memory, to explain the poor two-worker result on tier L (report, Section VII).
#   scripts/cache_experiment.sh                      N = 1 2 3 4, mr + spark_df, routes, tier L
#   NODES="2 3" REPS=2 FWS=mr scripts/cache_experiment.sh
#
# For every cluster size the cluster is rebuilt and the tier loaded into HDFS.
# Then, REPS times for every engine, two runs back to back:
#   cold  the page cache of the Docker VM is dropped first, so all data come from disk
#   warm  the same job again, with whatever the first run left in memory
# For every run and worker we record the cgroup counters before and after the run
# (bytes read from disk, refaulted page-cache pages, CPU time used and time throttled
# by the 2-CPU cap) and sample anonymous memory
# and page cache every second (scripts/cgroup_probe.sh).
#
# Output: results/cache/cache_runs.csv (one row per run, summed over workers)
#         results/cache/samples/<fw>-<job>-<tier>-n<N>-r<rep>-<mode>.txt
#         (lines: worker epoch anon_bytes cache_bytes)
set -uo pipefail
export MSYS_NO_PATHCONV=1
ROOT="$(cd "$(dirname "$0")/.." && (pwd -W 2>/dev/null || pwd))"  # Windows path under Git Bash

NODES="${NODES:-1 2 3 4}"
REPS="${REPS:-3}"
FWS="${FWS:-mr spark_df}"
JOB="${JOB:-routes}"
TIER="${TIER:-L}"
OUT="$ROOT/results/cache"
CSV="$OUT/cache_runs.csv"
PROBE=(sh /opt/scripts/cgroup_probe.sh)
SAMPLE=/tmp/cache-sample.txt

mkdir -p "$OUT/samples"
[ -f "$CSV" ] || echo "timestamp,framework,job,tier,nodes,rep,mode,seconds,disk_read_mib,refault_mib,cache_peak_mib,anon_peak_mib,hdfs_mib_per_worker,cpu_pct_per_worker,cpu_throttled_s" > "$CSV"

pair_done() {  # pair_done <fw> <nodes> <rep>: cold + warm runs already recorded?
  grep -q ",$1,$JOB,$TIER,$2,$3,warm,[0-9]" "$CSV"
}
block_done() {  # every pair for this cluster size recorded?
  local rep fw
  for rep in $(seq 1 "$REPS"); do for fw in $FWS; do pair_done "$fw" "$1" "$rep" || return 1; done; done
}

drop_caches() {  # drops the page cache of the whole Docker VM (clean pages only; no data is lost)
  docker run --rm --privileged --user root --entrypoint sh cst435/hadoop-spark:latest \
    -c 'sync && echo 3 > /proc/sys/vm/drop_caches' || echo "WARNING: could not drop caches" >&2
}

run_measured() {  # run_measured <fw> <nodes> <rep> <mode> <hdfs list>
  local fw=$1 n=$2 rep=$3 mode=$4 hdfs=$5 w line secs rb rf cpu thr rb_sum=0 rf_sum=0 thr_sum=0 util=""
  local samples="$OUT/samples/$fw-$JOB-$TIER-n$n-r$rep-$mode.txt"
  declare -A rb0 rf0 cpu0 thr0 dcpu
  for w in "${workers[@]}"; do
    read -r rb0[$w] rf0[$w] cpu0[$w] thr0[$w] < <(docker exec "$w" "${PROBE[@]}" counters)
    docker exec -d "$w" "${PROBE[@]}" sample "$SAMPLE"
  done

  line=$(docker exec -e RESULTS_DIR=/results/cache master /opt/scripts/run_job.sh "$fw" "$JOB" "$TIER" "$n" | grep '^SECONDS')
  secs="${line#SECONDS }"

  : > "$samples"
  for w in "${workers[@]}"; do
    docker exec "$w" touch "$SAMPLE.stop"
    read -r rb rf cpu thr < <(docker exec "$w" "${PROBE[@]}" counters)
    rb_sum=$((rb_sum + rb - rb0[$w]))
    rf_sum=$((rf_sum + rf - rf0[$w]))
    thr_sum=$((thr_sum + thr - thr0[$w]))
    dcpu[$w]=$((cpu - cpu0[$w]))
    docker exec "$w" cat "$SAMPLE" | awk -v w="$w" '{ print w, $0 }' >> "$samples"
  done
  # CPU utilisation of each worker in % of its 2-CPU cap over the job's wall-clock time
  for w in "${workers[@]}"; do
    util+="$(awk -v c="${dcpu[$w]}" -v s="${secs:-0}" 'BEGIN { printf "%.0f", (s > 0 ? c / 1e6 / (2 * s) * 100 : 0) }');"
  done
  util="${util%;}"
  # peaks: largest per-worker value seen during the run
  read -r anon_pk cache_pk < <(awk '$3 > a { a = $3 } $4 > c { c = $4 } END { printf "%.0f %.0f\n", a / 2^20, c / 2^20 }' "$samples")
  echo "$(date -Iseconds),$fw,$JOB,$TIER,$n,$rep,$mode,${secs:-},$((rb_sum / 1048576)),$((rf_sum * 4096 / 1048576)),$cache_pk,$anon_pk,$hdfs,$util,$((thr_sum / 1000000))" >> "$CSV"
  printf '  %-9s n=%s rep=%s %-4s %7ss  disk read %5s MiB  refault %5s MiB  cache peak %5s MiB  anon peak %5s MiB  CPU %% %-12s throttled %ss\n' \
    "$fw" "$n" "$rep" "$mode" "${secs:-FAILED}" "$((rb_sum / 1048576))" "$((rf_sum * 4096 / 1048576))" "$cache_pk" "$anon_pk" "$util" "$((thr_sum / 1000000))"
}

for n in $NODES; do
  if block_done "$n"; then echo "--- skip n=$n (all runs recorded)"; continue; fi
  echo "=== $(date '+%F %T')  cluster with $n worker(s), tier $TIER ==="
  "$ROOT/scripts/cluster.sh" up "$n" || { echo "cluster start failed" >&2; exit 1; }
  "$ROOT/scripts/cluster.sh" load "$TIER" || { echo "load failed" >&2; exit 1; }
  workers=(); for i in $(seq 1 "$n"); do workers+=("worker$i"); done
  hdfs=$(for w in "${workers[@]}"; do docker exec "$w" "${PROBE[@]}" hdfs; done | paste -sd';' -)
  echo "  HDFS data per worker (MiB): $hdfs"
  for rep in $(seq 1 "$REPS"); do
    for fw in $FWS; do
      if pair_done "$fw" "$n" "$rep"; then echo "  $fw n=$n rep=$rep (already recorded)"; continue; fi
      for mode in cold warm; do
        [ "$mode" = cold ] && drop_caches
        run_measured "$fw" "$n" "$rep" "$mode" "$hdfs"
      done
    done
  done
done
echo "=== $(date '+%F %T')  cache experiment finished; results in $CSV"
