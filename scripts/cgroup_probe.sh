#!/bin/sh
# Runs INSIDE a worker container; reads the container's own cgroup v2 counters.
#   cgroup_probe.sh counters       -> "<bytes read from disk> <refaulted file pages>
#                                      <CPU time used, us> <time throttled by the CPU cap, us>"
#   cgroup_probe.sh sample <file>  -> append "<epoch> <anon bytes> <page-cache bytes>"
#                                     every second until <file>.stop exists
#   cgroup_probe.sh hdfs           -> MiB of HDFS block data stored on this worker
# A "refault" is a page-cache page that was evicted and then read again, i.e.
# data that did not fit in the memory left over by the JVMs.
CG=/sys/fs/cgroup
case "$1" in
  counters)
    rb=$(awk '{ for (i = 2; i <= NF; i++) if ($i ~ /^rbytes=/) { sub("rbytes=", "", $i); s += $i } }
              END { printf "%.0f\n", s }' "$CG/io.stat")
    rf=$(awk '$1 == "workingset_refault_file" { print $2 }' "$CG/memory.stat")
    cpu=$(awk '$1 == "usage_usec" { print $2 }' "$CG/cpu.stat")
    thr=$(awk '$1 == "throttled_usec" { print $2 }' "$CG/cpu.stat")
    echo "$rb ${rf:-0} ${cpu:-0} ${thr:-0}" ;;
  sample)
    rm -f "$2" "$2.stop"
    while [ ! -f "$2.stop" ]; do
      awk -v t="$(date +%s.%N)" '$1 == "anon" { a = $2 } $1 == "file" { f = $2 } END { print t, a, f }' \
        "$CG/memory.stat" >> "$2"
      sleep 1
    done ;;
  hdfs)
    du -sm /hdfs/dn | cut -f1 ;;
  *)
    sed -n '2,8p' "$0"; exit 1 ;;
esac
