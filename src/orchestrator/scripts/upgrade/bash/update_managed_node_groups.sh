#!/bin/bash

#######################################
# Function usage explanation
#######################################
for arg in "$@"; do
  shift
  case "$arg" in
    '--help')                   set -- "$@" '-h'   ;;
    '--cluster')                set -- "$@" '-c'   ;;
    '--region')                 set -- "$@" '-r'   ;;
    '--node-group')             set -- "$@" '-g'   ;;
    '--desired-eks-version')    set -- "$@" '-e'   ;;
    *)                          set -- "$@" "$arg" ;;
  esac
done

function usage() {
  echo "Setup Bastion host with required tools."
  echo " -c, --cluster                Required. Name of the EKS Cluster"
  echo " -r, --region                 Required. AWS Region"
  echo " -g, --node-group             Required. Name of the node group"
  echo " -e, --desired-eks-version    Required. Desired EKS Kubernetes version"
  echo ""
}

while getopts "c:r:g:e:h" option; do
  case "${option}" in
    c) cluster_name="${OPTARG}" ;;
    r) region="${OPTARG}" ;;
    g) node_group_name="${OPTARG}" ;;
    e) desired_eks_version="${OPTARG}" ;;
    h)
      usage
      return 0
      ;;
    \?)
      echo "Invalid parameter"
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$cluster_name" ]] || [[ -z "$node_group_name" ]] || [[ -z "$desired_eks_version" ]] || [[ -z "$region" ]];
then
  echo "cluster, region, node-group and desired-eks-version options are mandatory"
  usage
  exit 1
fi

echo "Upgrading managed node group $node_group_name for cluster $cluster_name to EKS version $desired_eks_version"

response=$(eksctl upgrade nodegroup \
  --name="$node_group_name" \
  --cluster="$cluster_name" \
  --region="$region" \
  --kubernetes-version="$desired_eks_version"
)

error_code=${?}
if [[ $error_code -ne 0 ]]; then
  echo "ERROR: Failed to update the $node_group_name for $cluster_name. $response"
  exit 1
fi
