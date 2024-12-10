#!/bin/bash

cluster_name=$1
region=$2
namespace=$3
service_account=$4
file_path=$5

account_id=$(aws sts get-caller-identity --query "Account" --output text)

oidc_id=$(aws eks describe-cluster --name "$cluster_name" --query "cluster.identity.oidc.issuer" --output text | cut -d '/' -f 5)

echo "OIDC Id for $cluster_name is $oidc_id"

provider=$(aws iam list-open-id-connect-providers | grep "$oidc_id" | cut -d "/" -f4)

if [[ -z "$provider" ]] ; then
  echo "OIDC Id $oidc_id not associated with $cluster_name. Associating.."
  resp=$(eksctl utils associate-iam-oidc-provider --region "$region" --cluster "$cluster_name" --approve)
  error_code=${?}
  if [[ $error_code -ne 0 ]]; then
    echo "ERROR: Failed to associate OIDC provider for $cluster_name: $resp"
    exit 1
  fi
fi

provider=$(aws iam list-open-id-connect-providers | grep "$oidc_id" | cut -d "/" -f4)
error_code=${?}
if [[ $error_code -ne 0 ]]; then
  echo "Not able to associate OIDC Provider in IAM: $provider"
  exit 1
fi

oidc_provider=$(aws eks describe-cluster --name "$cluster_name" --region "$region" --query "cluster.identity.oidc.issuer" --output text | sed -e "s/^https:\/\///")

cat >"$file_path" <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::$account_id:oidc-provider/$oidc_provider"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "$oidc_provider:aud": "sts.amazonaws.com",
          "$oidc_provider:sub": "system:serviceaccount:$namespace:$service_account"
        }
      }
    }
  ]
}
EOF
