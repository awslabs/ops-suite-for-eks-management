#!/bin/bash

config_path=$1
cluster_name=$2
backup_name=$3
file_path=$4


backup_exists=$(velero --kubeconfig "$config_path" backup describe "$backup_name" -o json | jq -r '.phase')

if [[ -z "$backup_exists" ]]; then
  echo "$backup_name not present for $cluster_name"
  exit 1
elif [[ "$backup_exists" != "Completed" ]]; then
  echo "$backup_name not created successfully for $cluster_name."
  exit 1
else
  echo "$backup_name for $cluster_name found."
fi

echo "Creating restore $backup_name from backup $backup_name for $cluster_name"
velero --kubeconfig "$config_path" restore create "$backup_name" --from-backup "$backup_name" "${@:5}" --wait

status=$(velero --kubeconfig "$config_path" restore get "$backup_name" -o json)
echo "Restore Status: $status"

if [[ -z "$status" ]] ; then
  echo "Could not describe restore status for $backup_name"
  velero --kubeconfig "$config_path" restore get "$backup_name" -o json
  return 1
else
  echo "Creating $file_path file with the status contents"
  echo "$status" > "$file_path"
fi
