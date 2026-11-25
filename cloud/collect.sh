#!/usr/bin/env bash
# Wait for the cloud plan to finish, copy results to results/azure/, then
# deallocate the VMs (compute billing stops; disks/IPs remain until `azure_create.sh delete`).
#   cloud/collect.sh            wait + collect + deallocate
#   cloud/collect.sh --now      collect immediately (no wait, no deallocate)
set -uo pipefail
AZ="${AZ:-az}"
RG="${RG:-cst435-rg}"
KEY="${KEY:-$HOME/.ssh/cst435_azure}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IP="$("$AZ" vm show -d -g "$RG" -n master --query publicIps -o tsv | tr -d '\r')"
SSH=(ssh -i "$KEY" -o ConnectTimeout=30 -o ServerAliveInterval=30 "azureuser@$IP")

collect() {
  mkdir -p "$ROOT/results/azure"
  "${SSH[@]}" "tar czf - -C cst435/results ." < /dev/null | tar xzf - -C "$ROOT/results/azure"
  echo "copied cloud results to results/azure/ ($(($(wc -l < "$ROOT/results/azure/benchmark.csv") - 1)) runs)"
}

if [ "${1:-}" = --now ]; then collect; exit 0; fi

while true; do
  state="$("${SSH[@]}" 'if grep -q "plan finished" cst435/results/cloud-run.log; then echo done;
            elif pgrep -f "^bash scripts/run_benchmark" >/dev/null; then echo running; else echo died; fi' < /dev/null 2>/dev/null)"
  case "$state" in
    done) break ;;
    died) echo "cloud benchmark stopped without finishing" >&2; collect; exit 1 ;;
  esac
  sleep 300
done
collect
for vm in master worker1 worker2; do "$AZ" vm deallocate -g "$RG" -n "$vm" --no-wait -o none; done
echo "cloud plan finished; VMs deallocating"
