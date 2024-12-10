#!/bin/bash -e

# © 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
working_dir=$1
cluster_name=$2
report_file=$3

today=$(date +%F)
echo "Starting collecting metadata for for $cluster_name on $today"

config_path="$working_dir/config/$cluster_name"

kubectl_version="$(kubectl version -o json --client | jq -rj '.clientVersion|.major,".",.minor')";
echo "kubectl client version: $kubectl_version";

control_plane_version="$(kubectl --kubeconfig="$config_path" version -o json | jq -rj '.serverVersion|.major,".",.minor')";
echo "Control Plane Version: $control_plane_version";

echo "EKS Add-On Details:";
#<name>|<version>;
addon_path='{.metadata.name}{"|"}{.spec.template.spec.containers[0].image}'

coredns=$(kubectl --kubeconfig="$config_path" get deployment -n kube-system coredns -o jsonpath="$addon_path")
echo "$coredns"

kube_proxy=$(kubectl --kubeconfig="$config_path" get daemonset -n kube-system kube-proxy -o jsonpath="$addon_path")
echo "$kube_proxy"

aws_node=$(kubectl --kubeconfig="$config_path" get daemonset -n kube-system aws-node -o jsonpath="$addon_path")
echo "$aws_node"

worker_nodes=$(kubectl --kubeconfig="$config_path" get nodes --no-headers | wc -l);
echo "Total number of worker nodes: $worker_nodes";

#<name>|<version>;
node_version_path='{range .items[*]}{@.metadata.name}{"|"}{@.status.nodeInfo.kubeletVersion}{";"}{end}'
worker_node_version=$(kubectl --kubeconfig="$config_path" get nodes -o jsonpath="$node_version_path");
printf "Version details of each worker node: \n$worker_node_version\n";

cat <<EOF > "$report_file"
{
  "KubectlVersion":"$kubectl_version",
  "ClusterVersion":"$control_plane_version",
  "AddonDetails":{
    "CoreDns":"$coredns",
    "KubeProxy":"$kube_proxy",
    "AWSNode":"$aws_node"
  },
  "TotalWorkerNodes":$(($worker_nodes + 0)),
  "WorkerNodes": "$worker_node_version"
}
EOF
