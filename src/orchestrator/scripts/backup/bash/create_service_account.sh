#!/bin/bash

working_dir=$1
cluster_name=$2
service_account_name=$3
velero_namespace=$4
role_arn=$5

config_path="$working_dir/config/$cluster_name"

echo 'Creating role binding for the service account'
role_binding_file="service-account-role-binding-$cluster_name.yaml"
kubectl --kubeconfig "$config_path" apply -f "$working_dir"/config/"$role_binding_file"

error_code=${?}
if [ $error_code -ne 0 ]; then
  echo "$service_account_name not created"
  exit 1
else
  echo "$service_account_name service account created"
fi

echo 'Creating service account'
service_account_file="service-account-$cluster_name.yaml"
kubectl --kubeconfig "$config_path" apply -f "$working_dir"/config/"$service_account_file"

error_code=${?}
if [ $error_code -ne 0 ]; then
  echo "$service_account_name not bound to cluster $cluster_name. Deleting service account"
  kubectl --kubeconfig "$config_path" delete serviceaccount -n "$velero_namespace" "$service_account_name"
  echo "$service_account_name service account deleted"
  exit 1
else
  echo "$service_account_name bound to cluster $cluster_name"
fi

echo 'Annotating your service account'
kubectl --kubeconfig "$config_path" annotate serviceaccount -n "$velero_namespace" "$service_account_name" eks.amazonaws.com/role-arn="$role_arn"

error_code=${?}
if [ $error_code -ne 0 ]; then
  echo "$service_account_name not annotated. Deleting service account"
  kubectl --kubeconfig "$config_path" delete serviceaccount -n "$velero_namespace" "$service_account_name"
  echo "$service_account_name service account deleted"
  exit 1
else
  echo "$service_account_name annotated"
fi
