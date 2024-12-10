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
    '--addon')                  set -- "$@" '-a'   ;;
    '--file')                   set -- "$@" '-f'   ;;
    *)                          set -- "$@" "$arg" ;;
  esac
done

function usage() {
  echo "Setup Bastion host with required tools."
  echo " -c, --cluster                Required. Name of the EKS Cluster"
  echo " -r, --region                 Required. AWS Region"
  echo " -a, --addon                  Required. Name of the Addon to update"
  echo " -f, --file                   Required. Addon update config file"
  echo ""
}

while getopts "c:r:a:f:h" option; do
  case "${option}" in
    c) cluster_name="${OPTARG}" ;;
    r) region="${OPTARG}" ;;
    a) addon_name="${OPTARG}" ;;
    f) file_name="${OPTARG}" ;;
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

if [[ -z "$cluster_name" ]] || [[ -z "$region" ]] || [[ -z "$addon_name" ]] || [[ -z "$file_name" ]] ;
then
  echo "cluster, region, addon and file options are mandatory"
  usage
  exit 1
fi

oidc_id=$(aws eks describe-cluster --name "$cluster_name" --query "cluster.identity.oidc.issuer" --output text | cut -d '/' -f 5)
echo "OIDC Id for $cluster_name is $oidc_id"

provider=$(aws iam list-open-id-connect-providers | grep "$oidc_id" | cut -d "/" -f4)

if [[ -z "$provider" ]] ; then
  echo "OIDC Id $oidc_id not associated with $cluster_name. Associating.."

  resp=$(eksctl utils associate-iam-oidc-provider --cluster "$cluster_name" --region "$region" --approve)
  error_code=${?}
  if [[ $error_code -ne 0 ]]; then
    echo "ERROR: Failed to associate OIDC provider for $cluster_name. $resp"
    exit 1
  fi
fi

provider=$(aws iam list-open-id-connect-providers | grep "$oidc_id" | cut -d "/" -f4)
error_code=${?}
if [[ $error_code -ne 0 ]]; then
  echo "Not able to associate OIDC Provider in IAM: $provider"
  exit 1
fi

echo "Updating $addon_name for $cluster_name"
response=$(eksctl update addon -f "$file_name")

error_code=${?}
if [[ $error_code -ne 0 ]]; then
  echo "ERROR: Failed to update $addon_name addon for $cluster_name. $response"
  exit 1
fi
