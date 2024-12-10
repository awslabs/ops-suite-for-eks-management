from typing import Callable, Optional

from aws_lambda_powertools import Logger

logger = Logger()

# Table Names
METADATA_TABLE_NAME: str = "metadata"
WORKER_NODES_TABLE_NAME: str = "workernodes"
DEPRECATED_APIS_TABLE_NAME: str = "deprecatedapis"
CSR_TABLE_NAME: str = "csr"
PSP_TABLE_NAME: str = "psp"
UNHEALTHY_PODS_TABLE_NAME: str = "unhealthypods"
SINGLETON_TABLE_NAME: str = "singleton"
ADDONS_TABLE_NAME: str = "addons"
BACKUP_AND_RESTORE_TABLE_NAME: str = "backupandrestore"
CLUSTERS_UPGRADE_TABLE_NAME: str = "clusterupgrade"
ADDONS_UPGRADE_TABLE_NAME: str = "addonsupgrade"
NODE_GROUP_UPGRADE_TABLE_NAME: str = "nodegroupupgrade"
POST_UPGRADE_TABLE_NAME: str = "postupgrade"

TABLE_MAPPINGS: dict[str, str] = {
    "metadata": METADATA_TABLE_NAME,
    "deprecatedapis": DEPRECATED_APIS_TABLE_NAME,
    "deprecated": DEPRECATED_APIS_TABLE_NAME,
    "csr": CSR_TABLE_NAME,
    "certificatesigningrequests": CSR_TABLE_NAME,
    "podsecuritypolicies": PSP_TABLE_NAME,
    "psp": PSP_TABLE_NAME,
    "unhealthypods": UNHEALTHY_PODS_TABLE_NAME,
    "singleton": SINGLETON_TABLE_NAME,
    "singletonresources": SINGLETON_TABLE_NAME,
    "addons": ADDONS_TABLE_NAME,
    "addon": ADDONS_TABLE_NAME,
    "backupandrestore": BACKUP_AND_RESTORE_TABLE_NAME,
    "backup": BACKUP_AND_RESTORE_TABLE_NAME,
    "backups": BACKUP_AND_RESTORE_TABLE_NAME,
    "restore": BACKUP_AND_RESTORE_TABLE_NAME,
    "restores": BACKUP_AND_RESTORE_TABLE_NAME,
    "upgrade": CLUSTERS_UPGRADE_TABLE_NAME,
    "clusterupgrade": CLUSTERS_UPGRADE_TABLE_NAME,
    "upgrades": CLUSTERS_UPGRADE_TABLE_NAME,
    "nodegroupupgrade": NODE_GROUP_UPGRADE_TABLE_NAME,
    "nodegroupupgrades": NODE_GROUP_UPGRADE_TABLE_NAME,
    "postupgrade": POST_UPGRADE_TABLE_NAME,
    "addonsupgrade": ADDONS_UPGRADE_TABLE_NAME,
    "addonupgrades": ADDONS_UPGRADE_TABLE_NAME,
    "addonupgrade": ADDONS_UPGRADE_TABLE_NAME,
}


def get_table(key: str) -> Optional[str]:
    try:
        return TABLE_MAPPINGS[key]
    except KeyError as e:
        logger.error(f"Key {key} not found: {e}")
        return None


class AthenaQueries:
    def __init__(
        self,
        database: str,
        account_id: str,
        region: str,
        cluster_name: str,
        information: str,
        latest_date: str,
    ):

        self.database: str = database
        self.account_id: str = account_id
        self.region: str = region
        self.cluster_name: str = cluster_name
        self.information: str = information
        self.latest_date: str = latest_date

    def get_athena_query(self) -> (str, str, str, bool, Callable):
        table_name = get_table(self.information.lower())
        logger.info(f"Fetching additional data from table: {table_name}")

        if table_name is None:
            raise Exception(
                f"Table not found for information type - {self.information}"
            )

        if METADATA_TABLE_NAME == table_name:
            return self.get_metadata_query()

        if DEPRECATED_APIS_TABLE_NAME == table_name:
            return self.get_deprecated_apis_query()

        if CSR_TABLE_NAME == table_name:
            return self.get_csr_query()

        if PSP_TABLE_NAME == table_name:
            return self.get_psp_query()

        if UNHEALTHY_PODS_TABLE_NAME == table_name:
            return self.get_unhealthy_pods_query()

        if SINGLETON_TABLE_NAME == table_name:
            return self.get_singleton_resources_query()

        if ADDONS_TABLE_NAME == table_name:
            return self.get_addons_query()

        if BACKUP_AND_RESTORE_TABLE_NAME == table_name:

            if "restore" in self.information:
                return self.get_restore_query()

            return self.get_backup_query()

        if CLUSTERS_UPGRADE_TABLE_NAME == table_name:
            return self.get_upgrade_query()

        if ADDONS_UPGRADE_TABLE_NAME == table_name:
            return self.get_addon_upgrade_query()

        if NODE_GROUP_UPGRADE_TABLE_NAME == table_name:
            return self.get_nodegroup_upgrade_query()

        if POST_UPGRADE_TABLE_NAME == table_name:
            return self.get_post_upgrade_query()

    @staticmethod
    def common_query() -> str:
        return f"""
            SELECT
                {METADATA_TABLE_NAME}.accountid AS accountId,
                {METADATA_TABLE_NAME}.region,
                {METADATA_TABLE_NAME}.clustername AS clusterName,
                {METADATA_TABLE_NAME}.clusterversion AS clusterVersion,
                {METADATA_TABLE_NAME}.addondetails_coredns_details AS coredns,
                {METADATA_TABLE_NAME}.addondetails_kubeproxy_details AS kubeproxy,
                {METADATA_TABLE_NAME}.addondetails_awsnode_details AS awsnode,
                {METADATA_TABLE_NAME}.totalworkernodes AS totalWorkerNodes
        """

    def join_query(self, table_name: str) -> str:
        return f"""
           FROM {self.database}.{METADATA_TABLE_NAME} {METADATA_TABLE_NAME}
           INNER JOIN {self.database}.{table_name} {table_name}
           ON {METADATA_TABLE_NAME}.accountid = {table_name}.accountid
           AND {METADATA_TABLE_NAME}.region = {table_name}.region
           AND {METADATA_TABLE_NAME}.clustername = {table_name}.clustername
           {self.attach_where_conditions(table_name)}
       """

    def attach_where_conditions(self, table_name: str, query: str = None) -> str:

        if query is None:
            query = ""

        if table_name != METADATA_TABLE_NAME:
            query = self.attach_where_conditions(
                table_name=METADATA_TABLE_NAME, query=query
            )

        query = f"{query} AND {table_name}.date = '{self.latest_date}'"

        if self.account_id is not None:
            query = f"{query} AND {table_name}.accountid = '{self.account_id}'"

        if self.region is not None:
            query = f"{query} AND {table_name}.region = '{self.region}'"

        if self.cluster_name is not None:
            query = f"{query} AND {table_name}.clustername = '{self.cluster_name}'"

        return query

    @staticmethod
    def extract_metadata_data(data) -> dict:
        return {
            "CoreDNS": data[4]["VarCharValue"],
            "KubeProxy": data[5]["VarCharValue"],
            "AWSNode": data[6]["VarCharValue"],
            "TotalWorkerNodes": data[7]["VarCharValue"],
        }

    def get_metadata_query(self) -> (str, str, str, bool, Callable):
        multi_row: bool = False
        query: str = f"""
            {self.common_query()}
            FROM {self.database}.{METADATA_TABLE_NAME} {METADATA_TABLE_NAME}
            WHERE 1 = 1
            {self.attach_where_conditions(METADATA_TABLE_NAME)}
        """

        return (
            "Metadata",
            METADATA_TABLE_NAME,
            query,
            multi_row,
            self.extract_metadata_data,
        )

    def get_deprecated_apis_query(self) -> (str, str, str, bool, Callable):
        multi_row: bool = True
        query: str = f"""
            {self.common_query()},
            {DEPRECATED_APIS_TABLE_NAME}.name AS apiName,
            {DEPRECATED_APIS_TABLE_NAME}.apiversion AS apiVersion,
            {DEPRECATED_APIS_TABLE_NAME}.ruleset AS ruleSet,
            {DEPRECATED_APIS_TABLE_NAME}.replacewith AS apiReplacement,
            {DEPRECATED_APIS_TABLE_NAME}.sinceversion AS deprecatedSince,
            {DEPRECATED_APIS_TABLE_NAME}.stopversion AS removedVersion,
            {DEPRECATED_APIS_TABLE_NAME}.requestsinlast30days AS requestsInLast30Days,
            {DEPRECATED_APIS_TABLE_NAME}.message
            {self.join_query(DEPRECATED_APIS_TABLE_NAME)}
        """

        def extract_data(data) -> dict:
            return {
                "APIName": data[8]["VarCharValue"],
                "APIVersion": data[9]["VarCharValue"],
                "RuleSet": data[10]["VarCharValue"],
                "Replacement": data[11]["VarCharValue"],
                "DeprecatedSince": data[12]["VarCharValue"],
                "RemovedIn": data[13]["VarCharValue"],
                "RequestsInLast30Days": data[14]["VarCharValue"],
                "Message": data[15]["VarCharValue"],
            }

        return (
            "DeprecatedAPIs",
            DEPRECATED_APIS_TABLE_NAME,
            query,
            multi_row,
            extract_data,
        )

    def get_csr_query(self) -> (str, str, str, bool, Callable):
        multi_row: bool = True
        query: str = f"""
            {self.common_query()},
            {CSR_TABLE_NAME}.csrname AS csrName,
            {CSR_TABLE_NAME}.signername AS signerName,
            {CSR_TABLE_NAME}.currentstatus AS currentStatus
            {self.join_query(CSR_TABLE_NAME)}
        """

        def extract_data(data) -> dict:
            return {
                "Name": data[9]["VarCharValue"],
                "SignerName": data[10]["VarCharValue"],
                "CurrentStatus": data[11]["VarCharValue"],
            }

        return (
            "CertificateSigningRequests",
            CSR_TABLE_NAME,
            query,
            multi_row,
            extract_data,
        )

    def get_psp_query(self) -> (str, str, str, bool, Callable):
        multi_row: bool = True
        query: str = f"""
            {self.common_query()},
            {PSP_TABLE_NAME}.name AS policyName,
            {PSP_TABLE_NAME}.fsgroup AS fsGroup,
            {PSP_TABLE_NAME}.runasuser AS runAsUser,
            {PSP_TABLE_NAME}.supplementalgroups AS supplementalGroups
            {self.join_query(PSP_TABLE_NAME)}
        """

        def extract_data(data) -> dict:
            return {
                "PolicyName": data[9]["VarCharValue"],
                "FSGroup": data[10]["VarCharValue"],
                "RunAsUser": data[11]["VarCharValue"],
                "SupplementalGroups": data[12]["VarCharValue"],
            }

        return "PodSecurityPolicies", PSP_TABLE_NAME, query, multi_row, extract_data

    def get_unhealthy_pods_query(self) -> (str, str, str, bool, Callable):
        multi_row: bool = True
        query: str = f"""
            {self.common_query()},
            {UNHEALTHY_PODS_TABLE_NAME}.namespace AS namespace,
            {UNHEALTHY_PODS_TABLE_NAME}.podname AS podName,
            {UNHEALTHY_PODS_TABLE_NAME}.podstatus AS podStatus,
            {UNHEALTHY_PODS_TABLE_NAME}.errorreason AS errorReason
            {self.join_query(UNHEALTHY_PODS_TABLE_NAME)}
        """

        def extract_data(data) -> dict:
            return {
                "Namespace": data[9]["VarCharValue"],
                "Name": data[10]["VarCharValue"],
                "Status": data[11]["VarCharValue"],
                "ErrorReason": data[12]["VarCharValue"],
            }

        return (
            "UnhealthyPods",
            UNHEALTHY_PODS_TABLE_NAME,
            query,
            multi_row,
            extract_data,
        )

    def get_addons_query(self) -> (str, str, str, bool, Callable):
        multi_row: bool = True
        query: str = f"""
            {self.common_query()},
            {ADDONS_TABLE_NAME}.name AS addonName,
            {ADDONS_TABLE_NAME}.version AS addonVersion,
            {ADDONS_TABLE_NAME}.status AS addonStatus,
            {self.join_query(ADDONS_TABLE_NAME)}
        """

        def extract_data(data) -> dict:
            return {
                "Name": data[9]["VarCharValue"],
                "Version": data[10]["VarCharValue"],
                "Status": data[11]["VarCharValue"],
            }

        return "Addons", ADDONS_TABLE_NAME, query, multi_row, extract_data

    def get_singleton_resources_query(self) -> (str, str, str, bool, Callable):
        multi_row: bool = True
        query: str = f"""
            {self.common_query()},
            {SINGLETON_TABLE_NAME}.resource AS resourceType,
            {SINGLETON_TABLE_NAME}.namespace AS namespace
            {self.join_query(SINGLETON_TABLE_NAME)}
        """

        def extract_data(data) -> dict:
            return {
                "ResourceType": data[9]["VarCharValue"],
                "Namespace": data[10]["VarCharValue"],
            }

        return (
            "SingletonResources",
            SINGLETON_TABLE_NAME,
            query,
            multi_row,
            extract_data,
        )

    def get_backup_query(self) -> (str, str, str, bool, Callable):
        multi_row: bool = False
        query: str = f"""
            {self.common_query()},
            {BACKUP_AND_RESTORE_TABLE_NAME}.podstatus AS podStatus,
            {BACKUP_AND_RESTORE_TABLE_NAME}.serviceaccount AS serviceAccount,
            {BACKUP_AND_RESTORE_TABLE_NAME}.serviceaccountstatus AS serviceAccountStatus,
            {BACKUP_AND_RESTORE_TABLE_NAME}.backupstatus AS backupStatus,
            {BACKUP_AND_RESTORE_TABLE_NAME}.backupname as backupName,
            {BACKUP_AND_RESTORE_TABLE_NAME}.backuplocation as backupLocation,
            {self.join_query(BACKUP_AND_RESTORE_TABLE_NAME)}
        """

        def extract_data(data) -> dict:
            return {
                "PodStatus": data[9]["VarCharValue"],
                "ServiceAccount": data[10]["VarCharValue"],
                "ServiceAccountStatus": data[11]["VarCharValue"],
                "BackupStatus": data[12]["VarCharValue"],
                "BackupName": data[13]["VarCharValue"],
                "BackupLocation": data[14]["VarCharValue"],
            }

        return "Backup", BACKUP_AND_RESTORE_TABLE_NAME, query, multi_row, extract_data

    def get_restore_query(self) -> (str, str, str, bool, Callable):
        multi_row: bool = False
        query: str = f"""
            {self.common_query()},
            {BACKUP_AND_RESTORE_TABLE_NAME}.restorestatus as restoreStatus,
            {BACKUP_AND_RESTORE_TABLE_NAME}.backupname as backupName,
            {BACKUP_AND_RESTORE_TABLE_NAME}.restorebackuplocation as restoreBackupLocation
            {self.join_query(BACKUP_AND_RESTORE_TABLE_NAME)}
        """

        def extract_data(data) -> dict:
            return {
                "RestoreStatus": data[9]["VarCharValue"],
                "BackupName": data[10]["VarCharValue"],
                "RestoreBackupLocation": data[11]["VarCharValue"],
            }

        return "Restore", BACKUP_AND_RESTORE_TABLE_NAME, query, multi_row, extract_data

    def get_upgrade_query(self) -> (str, str, str, bool, Callable):
        multi_row: bool = False
        query: str = f"""
            {self.common_query()},
            {CLUSTERS_UPGRADE_TABLE_NAME}.clusterstatus AS clusterStatus,
            {CLUSTERS_UPGRADE_TABLE_NAME}.clusterupdatestatus AS clusterUpdateStatus,
            {CLUSTERS_UPGRADE_TABLE_NAME}.postupdateclusterversion AS updatedClusterVersion,
            {CLUSTERS_UPGRADE_TABLE_NAME}.totalnodegroups AS totalNodegroups,
            {CLUSTERS_UPGRADE_TABLE_NAME}.nodegroupsupgraded AS nodegroupsUpgraded,
            {CLUSTERS_UPGRADE_TABLE_NAME}.nodegroupsfailed AS nodegroupsFailed,
            {CLUSTERS_UPGRADE_TABLE_NAME}.nodegroupsrunningdesired AS nodegroupsRunningDesiredVersion,
            {CLUSTERS_UPGRADE_TABLE_NAME}.totaladdons AS totalAddons,
            {CLUSTERS_UPGRADE_TABLE_NAME}.addonsupgraded AS addonsUpgraded,
            {CLUSTERS_UPGRADE_TABLE_NAME}.addonsfailed as addonsFailed,
            {CLUSTERS_UPGRADE_TABLE_NAME}.addonsnotactive AS addonsNotActive,
            {CLUSTERS_UPGRADE_TABLE_NAME}.addonsnotsupported AS addonsNotSupported,
            {CLUSTERS_UPGRADE_TABLE_NAME}.addonsnotininput AS addonsNotInInput,
            {CLUSTERS_UPGRADE_TABLE_NAME}.addonsrunninglatest AS addonsRunningDesiredVersion,
            {CLUSTERS_UPGRADE_TABLE_NAME}.message
            {self.join_query(CLUSTERS_UPGRADE_TABLE_NAME)}
        """

        def extract_data(data) -> dict:
            return {
                "ClusterStatus": data[9]["VarCharValue"],
                "ClusterUpdateStatus": data[10]["VarCharValue"],
                "UpdatedClusterVersion": data[11]["VarCharValue"],
                "TotalNodegroups": data[12]["VarCharValue"],
                "NodegroupsUpgraded": data[13]["VarCharValue"],
                "NodegroupsFailed": data[14]["VarCharValue"],
                "NodegroupsRunningDesiredVersion": data[15]["VarCharValue"],
                "TotalAddons": data[16]["VarCharValue"],
                "AddonsUpgraded": data[17]["VarCharValue"],
                "AddonsFailed": data[18]["VarCharValue"],
                "AddonsNotActive": data[19]["VarCharValue"],
                "AddonsNotSupported": data[20]["VarCharValue"],
                "AddonsNotInInput": data[21]["VarCharValue"],
                "AddonsRunningDesiredVersion": data[22]["VarCharValue"],
                "UpgradeMessage": data[23]["VarCharValue"],
            }

        return "Upgrade", CLUSTERS_UPGRADE_TABLE_NAME, query, multi_row, extract_data

    def get_addon_upgrade_query(self) -> (str, str, str, bool, Callable):
        multi_row: bool = True
        query: str = f"""
            {self.common_query()},
            {ADDONS_UPGRADE_TABLE_NAME}.name AS addonName,
            {ADDONS_UPGRADE_TABLE_NAME}.version AS priorVersion,
            {ADDONS_UPGRADE_TABLE_NAME}.updatedversion AS updatedVersion,
            {ADDONS_UPGRADE_TABLE_NAME}.updatestatus AS updateStatus,
            {ADDONS_UPGRADE_TABLE_NAME}.message AS message,
            {self.join_query(ADDONS_UPGRADE_TABLE_NAME)}
        """

        def extract_data(data) -> dict:
            return {
                "AddonName": data[9]["VarCharValue"],
                "PriorVersion": data[10]["VarCharValue"],
                "UpdatedVersion": data[11]["VarCharValue"],
                "UpdateStatus": data[12]["VarCharValue"],
                "AddonUpgradeMessage": data[13]["VarCharValue"],
            }

        return (
            "AddonsUpgrades",
            ADDONS_UPGRADE_TABLE_NAME,
            query,
            multi_row,
            extract_data,
        )

    def get_nodegroup_upgrade_query(self) -> (str, str, str, bool, Callable):
        multi_row: bool = True
        query: str = f"""
            {self.common_query()},
            {NODE_GROUP_UPGRADE_TABLE_NAME}.name AS nodegroupName,
            {NODE_GROUP_UPGRADE_TABLE_NAME}.desiredversion AS desiredVersion,
            {NODE_GROUP_UPGRADE_TABLE_NAME}.updatestatus AS updateStatus,
            {NODE_GROUP_UPGRADE_TABLE_NAME}.message AS message,
            {self.join_query(NODE_GROUP_UPGRADE_TABLE_NAME)}
        """

        def extract_data(data) -> dict:
            return {
                "NodegroupName": data[9]["VarCharValue"],
                "DesiredVersion": data[10]["VarCharValue"],
                "UpdateStatus": data[11]["VarCharValue"],
                "AddonUpgradeMessage": data[12]["VarCharValue"],
            }

        return (
            "NodegroupsUpgrades",
            NODE_GROUP_UPGRADE_TABLE_NAME,
            query,
            multi_row,
            extract_data,
        )

    def get_post_upgrade_query(self) -> (str, str, str, bool, Callable):
        multi_row: bool = True
        query: str = f"""
             {self.common_query()},
             {POST_UPGRADE_TABLE_NAME}.currentclusterversion AS currentClusterVersion,
             {POST_UPGRADE_TABLE_NAME}.type AS resourceType,
             {POST_UPGRADE_TABLE_NAME}.name AS resourceName,
             {POST_UPGRADE_TABLE_NAME}.currentversion AS currentVersion,
             {POST_UPGRADE_TABLE_NAME}.status AS status,
             {POST_UPGRADE_TABLE_NAME}.message,
             {self.join_query(POST_UPGRADE_TABLE_NAME)}
         """

        def extract_data(data) -> dict:
            return {
                "CurrentClusterVersion": data[9]["VarCharValue"],
                "ResourceType": data[10]["VarCharValue"],
                "ResourceName": data[11]["VarCharValue"],
                "CurrentResourceVersion": data[12]["VarCharValue"],
                "ResourceStatus": data[13]["VarCharValue"],
                "ResourceMessage": data[14]["VarCharValue"],
            }

        return "PostUpgrade", POST_UPGRADE_TABLE_NAME, query, multi_row, extract_data
