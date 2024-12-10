SOLUTION_NAME: str = "summary"
S3_FOLDER_NAME: str = f"reports"
LOG_FOLDER: str = f"{SOLUTION_NAME}"

# Config Names
CLUSTERS_CONFIG: str = "clusters"
REGION_CONFIG: str = "region"
FILTER_CLUSTERS_CONFIG: str = "filterClusters"
REPORTS_CONFIG: str = "reportsCleanup"
KUBE_CONFIG: str = "checkKubeConfigFile"

# Steps
DEFAULT_STEP_NAME: str = "summary"
METADATA_STEP: str = "metadata"
WORKER_NODE_METADATA_STEP: str = "workerNodes"
DEPRECATED_APIS_STEP: str = "deprecatedAPIs"
CSR_STEP: str = "csr"
PSP_STEP: str = "psp"
UNHEALTHY_PODS_STEP: str = "unhealthyPods"
SINGLETON_STEP: str = "singleton"
ADDONS_STEP: str = "addons"

# CSR
CSR_AUTO_APPROVE: bool = False

# Singleton
RESTRICTED_NAMESPACES: [] = ["kube-system"]
IGNORE_LIVENESS_READINESS_DEPLOYMENTS: [] = []
DAEMONSET_NAME: str = "ebs-csi-node"
NEED_LIVENESS_AND_READINESS_PROBE: bool = False
NEED_NODE_AFFINITIES: bool = False
NEED_DAEMONSET_NODE: bool = False
