#!/bin/bash

config_path=$1
namespace=$2
s3_bucket=$3
region=$4
service_account=$5
cluster_name=$6
velero_plugin_version=$7

# Use --prefix option to create backups under a separate folder for each cluster
velero install \
    --kubeconfig "$config_path" \
    --provider aws \
    --namespace "$namespace" \
    --plugins velero/velero-plugin-for-aws:"$velero_plugin_version" \
    --bucket "$s3_bucket" \
    --backup-location-config region="$region" \
    --snapshot-location-config region="$region" \
    --service-account-name "$service_account" \
    --prefix "$cluster_name" \
    --wait \
    --no-secret
