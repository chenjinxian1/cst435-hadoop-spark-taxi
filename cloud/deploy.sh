#!/usr/bin/env bash
# From the laptop: copy the project to the master VM, build the image there,
# ship it to the workers over the private network, and prepare the data on the master.
#   cloud/deploy.sh                 (after cloud/azure_create.sh)
set -euo pipefail
AZ="${AZ:-az}"
RG="${RG:-cst435-rg}"
KEY="${KEY:-$HOME/.ssh/cst435_azure}"
TIERS="${TIERS:-S M L}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IP="$("$AZ" vm show -d -g "$RG" -n master --query publicIps -o tsv | tr -d '\r')"
SSH=(ssh -i "$KEY" -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 "azureuser@$IP")
echo "master public IP: $IP"

echo "== waiting for cloud-init (Docker install) on all VMs"
"${SSH[@]}" "cloud-init status --wait >/dev/null; docker version --format 'master docker {{.Server.Version}}'"

echo "== copying project"
tar czf - -C "$ROOT" cluster code scripts experiments cloud | "${SSH[@]}" "mkdir -p cst435 && tar xzf - -C cst435"
# Dedicated key (only used for these VMs) so the master can reach the workers.
"${SSH[@]}" "cat > .ssh/id_ed25519 && chmod 600 .ssh/id_ed25519" < "$KEY"
for w in worker1 worker2; do
  "${SSH[@]}" "ssh -o StrictHostKeyChecking=accept-new $w 'cloud-init status --wait >/dev/null; docker version --format \"$w docker {{.Server.Version}}\"'"
done

# On Azure Ubuntu a VM resolves its OWN host name to an IPv6 link-local address,
# which Hadoop clients cannot use. Pin all node names to their private IPv4s.
"$AZ" vm list -d -g "$RG" --query "[].[privateIps, name]" -o tsv | tr -d '\r' \
  | sed 's/$/  # cst435/' | "${SSH[@]}" "cat > /tmp/cst435-hosts; cat /tmp/cst435-hosts"
for h in master worker1 worker2; do
  "${SSH[@]}" "scp -q -o StrictHostKeyChecking=accept-new /tmp/cst435-hosts $h:/tmp/cst435-hosts &&
    ssh $h 'sudo sed -i \"/# cst435/d\" /etc/hosts && cat /tmp/cst435-hosts | sudo tee -a /etc/hosts >/dev/null && echo \$(hostname): \$(getent hosts master)'"
done

echo "== building image on master"
"${SSH[@]}" "cd cst435/cluster && sed -i 's/\r\$//' entrypoint.sh ../scripts/*.sh ../cloud/*.sh && docker build -q -t cst435/hadoop-spark:latest ."
for w in worker1 worker2; do
  echo "== loading image on $w"
  "${SSH[@]}" "docker save cst435/hadoop-spark:latest | ssh $w docker load -q"
done

echo "== preparing data on master: $TIERS"
"${SSH[@]}" "cd cst435 && docker run --rm -u \$(id -u):\$(id -g) -e HOME=/tmp -v \$PWD:/w -w /w python:3.12-slim \
   sh -c 'pip install -q --user pandas pyarrow && python scripts/prepare_data.py --tiers $TIERS'"
echo "deploy done. ssh: ssh -i $KEY azureuser@$IP"
