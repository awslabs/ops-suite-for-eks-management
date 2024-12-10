SOLUTION_NAME: str = "update"
S3_FOLDER_NAME: str = f"reports"
LOG_FOLDER: str = f"{SOLUTION_NAME}"

# Config Names
CLUSTERS_CONFIG: str = "clusters"
REGION_CONFIG: str = "region"
FILTER_CLUSTERS_CONFIG: str = "filterClusters"
REPORTS_CONFIG: str = "reportsCleanup"
KUBE_CONFIG: str = "checkKubeConfigFile"

# Steps
DEFAULT_STEP_NAME: str = "clustersUpgrade"
CONTROL_PLANE_UPGRADE_STEP: str = "controlPlaneUpgrade"
RESTART_FARGATE_PROFILES_STEP: str = "restartFargateProfiles"
NODE_GROUPS_UPGRADE_STEP: str = "nodegroupsUpgrade"
ADDONS_UPGRADE_STEP: str = "addonsUpgrade"
POST_UPGRADE_STEP: str = "postUpgrade"
TOOLS_UPDATE_STEP: str = "toolsUpdate"
