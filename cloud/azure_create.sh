#!/usr/bin/env bash
# Create the Azure cluster: 1 master + 2 workers (2 vCPU / 8 GB each) in one VNet.
#   cloud/azure_create.sh            create everything
#   cloud/azure_create.sh delete     delete the whole resource group (stops all charges)
#
# Constraints of the Azure for Students subscription used here (checked 2026-11-24):
#   - allowed regions: japaneast, malaysiawest, indiasouthcentral, koreacentral, indonesiacentral
#   - at most 6 vCPUs per region and 4 per VM family -> 3 VMs of 2 vCPUs
#   - koreacentral is the allowed region that offers Dv4 sizes to this subscription
# Workers use identical sizes; the master is the same generation (Dv4) in another
# family because the 4-vCPU family quota is used up by the two workers.
set -euo pipefail
AZ="${AZ:-az}"
RG="${RG:-cst435-rg}"
LOC="${LOC:-koreacentral}"
KEY="${KEY:-$HOME/.ssh/cst435_azure}"
HERE="$(cd "$(dirname "$0")" && (pwd -W 2>/dev/null || pwd))"

if [ "${1:-}" = delete ]; then
  "$AZ" group delete -n "$RG" --yes
  echo "deleted resource group $RG"; exit 0
fi

MYIP="$(curl -fsS https://api.ipify.org)"
echo "SSH will be allowed only from $MYIP"

"$AZ" group create -n "$RG" -l "$LOC" -o none
"$AZ" network vnet create -g "$RG" -n cst435-vnet --address-prefix 10.10.0.0/16 \
     --subnet-name nodes --subnet-prefix 10.10.1.0/24 -o none
"$AZ" network nsg create -g "$RG" -n cst435-nsg -o none
# Default NSG rules already allow all traffic inside the VNet (HDFS, YARN, Spark ports).
"$AZ" network nsg rule create -g "$RG" --nsg-name cst435-nsg -n ssh-from-admin --priority 100 \
     --source-address-prefixes "$MYIP/32" --destination-port-ranges 22 --protocol Tcp --access Allow -o none

create_vm() {  # create_vm <name> <size> <os disk GB>
  "$AZ" vm create -g "$RG" -n "$1" --size "$2" --image Ubuntu2204 \
     --admin-username azureuser --ssh-key-values "$KEY.pub" \
     --vnet-name cst435-vnet --subnet nodes --nsg cst435-nsg \
     --public-ip-sku Standard --os-disk-size-gb "$3" --storage-sku StandardSSD_LRS \
     --custom-data "$HERE/cloud-init.yaml" --no-wait -o none
}
create_vm master  Standard_D2_v4  64
create_vm worker1 Standard_D2s_v4 32
create_vm worker2 Standard_D2s_v4 32
for vm in master worker1 worker2; do "$AZ" vm wait -g "$RG" -n "$vm" --created -o none; done

"$AZ" vm list -d -g "$RG" --query "[].{name:name, size:hardwareProfile.vmSize, public:publicIps, private:privateIps}" -o table
