#!/bin/bash

config_path=$1
cluster_name=$2
backup_name=$3
file_path=$4
namespace=$5

backup_exists=$(velero --kubeconfig "$config_path" backup describe "$backup_name" --namespace "$namespace" -o json | jq -r '.phase')

if [[ -z "$backup_exists" ]]; then
  echo "$backup_name not present for $cluster_name"
  echo "Creating backup with name $backup_name for $cluster_name"
  velero --kubeconfig "$config_path" backup create "$backup_name" --namespace "$namespace"  "${@:6}" --wait
elif [[ "$backup_exists" != "Completed" ]]; then
  echo "$backup_name not created successfully for $cluster_name. Deleting it..."
  velero --kubeconfig "$config_path" backup delete "$backup_name" --namespace "$namespace" --confirm
else
  echo "$backup_name already exists for $cluster_name"
fi

status=$(velero --kubeconfig "$config_path" backup describe "$backup_name" --namespace "$namespace"  -o json)
echo "Backup Status: $status"

if [[ -z "$status" ]] ; then
  echo "Could not describe backup status for $backup_name"
  velero --kubeconfig "$config_path" backup describe "$backup_name" --namespace "$namespace"  -o json
  return 1
else
  echo "Creating $file_path file with the status contents"
  echo "$status" > "$file_path"
fi
