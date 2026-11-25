#!/usr/bin/env bash
# Runs INSIDE the master container: one timed execution of one job.
#   run_job.sh <framework> <job> <tier> <nodes>
#   framework: serial | mr | mr_nocombiner | spark_rdd | spark_df
# Prints "SECONDS <wall-clock seconds>" on success and saves the merged
# job output to $RESULTS_DIR/outputs/<framework>-<job>-<tier>.tsv for checking
# (RESULTS_DIR defaults to /results; other experiments pass their own directory).
set -euo pipefail
FW="$1"; JOB="$2"; TIER="$3"; NODES="$4"
R="${RESULTS_DIR:-/results}"

IN="/input/$TIER"
OUT="/out/$FW-$JOB-$TIER"
SAVE="$R/outputs/$FW-$JOB-$TIER.tsv"
PARTS=$((NODES * 2))                      # reducers / shuffle partitions = total cores
STREAMING_JAR=$(ls "$HADOOP_HOME"/share/hadoop/tools/lib/hadoop-streaming-*.jar)
mkdir -p "$R/outputs" "$R/logs"
LOG="$R/logs/$FW-$JOB-$TIER-n$NODES.log"

if [ "$FW" = serial ]; then
  # Copy input to the container's local disk first (not timed) so the
  # baseline is not slowed down by the Windows bind mount.
  LOCAL=/tmp/serial-input/$TIER
  for d in /tmp/serial-input/*; do [ "$d" != "$LOCAL" ] && rm -rf "$d"; done  # keep one tier only
  if [ ! -d "$LOCAL" ]; then
    mkdir -p "$LOCAL"
    while read -r f; do [ -n "$f" ] && cp "/data/csv/$f" "$LOCAL/"; done < "/data/csv/$TIER.list"
  fi
else
  hdfs dfs -rm -r -f -skipTrash "$OUT" >/dev/null 2>&1 || true
fi

start=$(date +%s.%N)
case "$FW" in
  serial)
    python3 /opt/job/local_baseline.py --job "$JOB" --output "$SAVE" "$LOCAL"/*.csv >"$LOG" 2>&1 ;;
  mr|mr_nocombiner)
    COMBINER=(); [ "$FW" = mr ] && COMBINER=(-combiner "python3 reducer.py")
    hadoop jar "$STREAMING_JAR" \
      -D mapreduce.job.name="$FW-$JOB-$TIER-n$NODES" \
      -D mapreduce.job.reduces="$PARTS" \
      -files /opt/job/mapper.py,/opt/job/reducer.py \
      -mapper "python3 mapper.py $JOB" "${COMBINER[@]}" -reducer "python3 reducer.py" \
      -input "$IN" -output "$OUT" >"$LOG" 2>&1 ;;
  spark_rdd|spark_df)
    spark-submit --num-executors "$NODES" --name "$FW-$JOB-$TIER-n$NODES" \
      --py-files /opt/job/mapper.py /opt/job/spark_job.py \
      --job "$JOB" --api "${FW#spark_}" --partitions "$PARTS" \
      --input "hdfs://$IN" --output "hdfs://$OUT" >"$LOG" 2>&1 ;;
  *) echo "unknown framework $FW" >&2; exit 2 ;;
esac
end=$(date +%s.%N)

if [ "$FW" != serial ]; then
  hdfs dfs -getmerge "$OUT" "$SAVE" 2>/dev/null
  rm -f "$(dirname "$SAVE")/.$(basename "$SAVE").crc"   # local checksum file from getmerge
fi
echo "SECONDS $(echo "$end - $start" | awk '{printf "%.2f", $1 - $3}')"
