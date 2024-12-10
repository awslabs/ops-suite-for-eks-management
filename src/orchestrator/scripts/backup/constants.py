SOLUTION_NAME: str = "backup"
S3_FOLDER_NAME: str = f"reports"
LOG_FOLDER: str = f"{SOLUTION_NAME}"

SERVICE_ACCOUNT_ROLE_BINDING_FILE: str = "service-account-role-binding"
SERVICE_ACCOUNT_FILE_NAME = "service-account"
TRUST_RELATIONSHIP_FILE: str = "trust-relationship.json"

# Config Names
CLUSTERS_CONFIG: str = "clusters"
REGION_CONFIG: str = "region"
FILTER_CLUSTERS_CONFIG: str = "filterClusters"
REPORTS_CONFIG: str = "reportsCleanup"
ROLE_BINDING_CONFIG: str = "clusterRoleBindingYaml"
SERVICE_ACCOUNT_CONFIG: str = "serviceAccountYaml"
SERVICE_ACCOUNT_ROLE_CONFIG: str = "serviceAccountTrustPolicy"
KUBE_CONFIG: str = "checkKubeConfigFile"

# Steps
DEFAULT_STEP_NAME: str = "backupAndRestore"
SERVICE_ACCOUNT_STEP: str = "serviceAccount"
VELERO_PLUGIN_STEP: str = "veleroPlugin"
VELERO_BACKUP_STEP: str = "veleroBackup"
VELERO_RESTORE_STEP: str = "veleroRestore"
