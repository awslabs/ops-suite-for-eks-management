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
    '--config-path')            set -- "$@" '-p'   ;;
    '--cluster-version')        set -- "$@" '-v'   ;;
    '--desired-eks-version')    set -- "$@" '-e'   ;;
    *)                          set -- "$@" "$arg" ;;
  esac
done

function usage() {
  echo "Setup Bastion host with required tools."
  echo " -c, --cluster                Required. Name of the EKS Cluster"
  echo " -r, --region                 Required. AWS Region"
  echo " -p, --config-path            Required. Path of the kubernetes config file for the cluster"
  echo " -v, --cluster-version        Required. EKS Kubernetes version of the cluster"
  echo " -e, --desired-eks-version    Required. Desired EKS Kubernetes version"
  echo ""
}

while getopts "c:r:p:v:e:h" option; do
  case "${option}" in
    c) cluster_name="${OPTARG}" ;;
    r) region="${OPTARG}" ;;
    p) config_path="${OPTARG}" ;;
    v) cluster_version="${OPTARG}" ;;
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

if [[ -z "$cluster_name" ]] || [[ -z "$config_path" ]] || [[ -z "$desired_eks_version" ]] || [[ -z "$cluster_version" ]] || [[ -z "$region" ]];
then
  echo "cluster, region, config-path, cluster-version and desired-eks-version options are mandatory"
  usage
  exit 1
fi

# Constants
PSP_SUPPORTED_LAST_VERSION=124

if [[ "${cluster_version//.}" -le  PSP_SUPPORTED_LAST_VERSION ]]; then
  echo "$cluster_version is less than or equal to the EKS version 1.24"
  echo "Checking of default Pod Security policies are present."

  psp=$(kubectl --kubeconfig "$config_path" get psp eks.privileged)

  error_code=${?}

  if [[ $error_code -ne 0 ]]; then
    echo "ERROR: Fetching PSPs failed. $psp"
    echo "Refer https://docs.aws.amazon.com/eks/latest/userguide/pod-security-policy.html#default-psp"
    exit 1
  fi
fi

echo "Updating $cluster_name with $cluster_version to desired eks version $desired_eks_version"
response=$(eksctl upgrade cluster --name "$cluster_name" --version "$desired_eks_version" --region "$region" --approve)
error_code=${?}

if [[ $error_code -ne 0 ]]; then
  echo "ERROR: Failed to update the EKS Kubernetes version for $cluster_name. $response"
  exit 1
fi
