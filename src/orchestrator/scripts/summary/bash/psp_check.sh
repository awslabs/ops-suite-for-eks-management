#!/bin/bash -e

# © 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
home_path=$1
cluster_name=$2
report_file=$3

today=$(date +%F)
echo "Starting checking for Pod Security policies in $cluster_name on $today"

config_path="$home_path/config/$cluster_name"
echo "Config path $config_path"

#<name>|<fsGroup><runAsUser><supplementalGroups>;
psp_path='{range .items[*]}{@.metadata.name}{"|"}{@.spec.fsGroup.rule}{"|"}{@.spec.runAsUser.rule}{"|"}{@.spec.supplementalGroups.rule}{";"}{end}'
psp_details=$(kubectl --kubeconfig="$config_path" get psp -o jsonpath="$psp_path") || echo "No PSP details present"

if [[ $psp_details -ne 0 ]]; then
  psp_details="{}"
fi

echo "PSP Details: $psp_details";

cat <<EOF > "$report_file"
"$psp_details"
EOF
