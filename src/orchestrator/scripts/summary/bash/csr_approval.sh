#!/bin/bash -e

kube_config_path=$1
csr_name=$2

echo "Approving the certificate signing requests"

response=$(kubectl --kubeconfig="$kube_config_path" certificate approve "$csr_name")
error_code=${?}

if [[ $error_code -ne 0 ]]; then
  echo "ERROR: CSR approval failed. $response"
  exit 1
fi

echo "CSRs approved for $csr_name"
