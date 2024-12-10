import json
from datetime import datetime

from cluster import Action, Cluster, ClusterSource, logger
from target import InputTarget, TargetLocation, logger

# Constants
"""
Max characters allowed in a IAM Role name
"""
MAX_ROLE_LENGTH = 64

"""
Min characters allowed in a IAM Role name
"""
MIN_ROLE_LENGTH = 1

current_date = datetime.now().date()


class EventSource(ClusterSource):
    """
    Extract the cluster data from lambda event.
    The child classes must implement the below methods.
    * valid_cluster
    * set_defaults
    """

    def __init__(self, action: Action, input_clusters: [], default_options: dict):
        super().__init__(source="EVENT", default_options=default_options)
        self._action: Action = action
        self._input_clusters: [] = input_clusters

    def get_clusters(
        self,
    ) -> [Cluster]:
        """
        Get the clusters from the event

        Returns:
            []: List of Cluster objects
        """

        mapped_clusters: [Cluster] = []
        logger.info(f"Input_clusters: {self._input_clusters}")
        if len(self._input_clusters) != 0:
            for input_cluster in self._input_clusters:
                cluster: Cluster = self.get_cluster_mappings(input_cluster)

                if cluster.get("Action", None) is None:
                    cluster["Action"] = str(self._action.value)
                mapped_clusters.append(cluster)
        return mapped_clusters

    def get_cluster_mappings(self, input_cluster: dict) -> Cluster:
        """
        Convert input_cluster (dict) into a Cluster typeddict
        Args:
            input_cluster: Input cluster

        Returns:
            Cluster
        """

        input_cluster_str = json.dumps(input_cluster)
        cluster: Cluster = json.loads(input_cluster_str)
        self.set_defaults(cluster)

        valid, message = self.valid_required_fields(cluster)
        if not valid:
            logger.error(message)
            raise Exception(message)

        valid, message = self.valid_cluster(cluster)
        if not valid:
            logger.error(message)
            raise Exception(message)

        logger.info(f"get_cluster_mappings: {cluster}")
        return cluster

    @staticmethod
    def valid_required_fields(cluster: Cluster) -> (bool, str):
        """
        Valid the required fields - Account Id, region and cluster name
        Args:
            cluster: Input cluster object

        Returns:
            tuple: (valid, message)
        """

        account_id = cluster.get("AccountId", None)
        region = cluster.get("Region", None)
        cluster_name = cluster.get("ClusterName", None)
        if account_id is None or region is None or cluster_name is None:
            return (
                False,
                "One of these fields are missing - AccountId, Region, ClusterName",
            )

        return True, "Valid"

    def valid_cluster(self, cluster: Cluster) -> (bool, str):
        """
        Validate the necessary fields

        Args:
            cluster: Input cluster object

        Returns:
            tuple: (valid, message)
        """

        pass

    def set_defaults(self, cluster: Cluster) -> None:
        """
        Set defaults to fields that are not present in the input.

        Args:
            cluster: Input cluster object

        Returns:
            None
        """

        pass


class SummaryEventSource(EventSource):
    """
    Implementation for EventSource class.
    Validates and defaults the fields necessary for summary collection in the input cluster.
    """

    def __init__(self, input_clusters: [], default_options: dict):
        super().__init__(Action.SUMMARY, input_clusters, default_options)

    def valid_cluster(self, cluster: Cluster) -> (bool, str):
        return True, "Valid"


class BackupEventSource(EventSource):
    """
    Implementation for EventSource class.
    Validates and defaults the fields necessary for velero backup creation in the input cluster.
    """

    def __init__(self, input_clusters: [], default_options: dict):
        super().__init__(Action.BACKUP, input_clusters, default_options)

    def valid_cluster(self, cluster: Cluster) -> (bool, str):
        """
        Validate ServiceAccountRoleName field

        Args:
            cluster: Input cluster object

        Returns:
            tuple: (valid, message)
        """

        cluster_name = cluster.get("ClusterName")
        action = cluster.get("Action", None)

        message = "Valid"

        if action is not None and action != str(Action.BACKUP.value):
            message = f"Only BACKUP value is allowed for action field in `Backup` array fpr {cluster_name}"
            return False, message

        role_name = cluster.get("BackupOptions").get("ServiceAccountRoleName")
        if (
            role_name is None
            or len(role_name) > MAX_ROLE_LENGTH
            or len(role_name) < MIN_ROLE_LENGTH
        ):
            message = f"Provided/ defaulted role name {role_name} for {cluster_name}"
            return False, message

        return True, message

    def set_defaults(self, cluster: Cluster) -> None:
        """
        Below defaults will be set.
        * BackupName = {current_date}-{region}-{cluster_name}
        * VeleroNamespace = from default_options dict
        * VeleroPluginVersion = v1.10.1
        * role_prefix = from default_options dict
        * role_name = {role_prefix}-{cluster_name}-Role

        Args:
            cluster: Input cluster object

        Returns:
            None
        """

        cluster_name = cluster.get("ClusterName")
        region = cluster.get("Region")
        role_prefix = self.default_options.get("ServiceAccountRolePrefix")

        logger.info(f"Setting default options for {cluster_name}")

        options = cluster.get("BackupOptions", {})

        backup_name = options.get("BackupName")
        if backup_name is None:
            backup_name = f"{current_date}-{region}-{cluster_name}"

        velero_namespace = options.get("VeleroNamespace")
        if velero_namespace is None:
            velero_namespace = self.default_options.get("VeleroNamespace")

        velero_plugin_version = options.get("VeleroPluginVersion")
        if velero_plugin_version is None:
            velero_plugin_version = self.default_options.get("VeleroPluginVersion")

        service_account = options.get("ServiceAccount")
        if service_account is None:
            service_account = self.default_options.get("ServiceAccount")

        service_account_role = options.get("ServiceAccountRoleName")
        if service_account_role is None:
            service_account_role = f"{role_prefix}-{cluster_name}-Role"

        logger.info(f"BackupName - {backup_name}")
        logger.info(f"VeleroNamespace - {velero_namespace}")
        logger.info(f"ServiceAccount - {service_account}")
        logger.info(f"ServiceAccountRoleName - {service_account_role}")

        backup_options_defaults = dict(
            BackupName=backup_name,
            VeleroNamespace=velero_namespace,
            ServiceAccount=service_account,
            ServiceAccountRoleName=service_account_role,
            VeleroArguments=options.get("VeleroArguments", None),
            VeleroPluginVersion=velero_plugin_version,
        )

        cluster["BackupOptions"] = backup_options_defaults


class RestoreEventSource(EventSource):
    """
    Implementation for EventSource class.
    Validates and defaults the fields necessary for velero restore creation in the input cluster.
    """

    def __init__(self, input_clusters: [], default_options: dict):
        super().__init__(Action.RESTORE, input_clusters, default_options)

    def valid_cluster(self, cluster: Cluster) -> (bool, str):
        """
        Validate BackupName field

        Args:
            cluster: Input cluster object

        Returns:
            tuple: (valid, message)
        """

        cluster_name = cluster.get("ClusterName")
        action = cluster.get("Action", None)

        message = "Valid"

        if action is not None and action != str(Action.RESTORE.value):
            message = f"Only RESTORE value is allowed for action field in `Restore` array for {cluster_name}"
            return False, message

        backup_name = cluster.get("RestoreOptions").get("BackupName", None)
        if backup_name is None:
            message = f"BackupName is required for RESTORE action for {cluster_name}"
            return False, message

        return True, message

    def set_defaults(self, cluster: Cluster) -> None:
        """
        No defaults will be set.

        Args:
            cluster: Input cluster object

        Returns:
            None
        """

        options = cluster.get("RestoreOptions", {})
        cluster["RestoreOptions"] = options


class UpgradeEventSource(EventSource):
    """
    Implementation for EventSource class.
    Validates and defaults the fields necessary for upgrading the cluster.
    """

    def __init__(self, input_clusters: [], default_options: dict):
        super().__init__(Action.UPGRADE, input_clusters, default_options)

    def valid_cluster(self, cluster: Cluster) -> (bool, str):
        """
        Validate ManagedNodeGroups field

        Args:
            cluster: Input cluster object

        Returns:
            tuple: (valid, message)
        """

        cluster_name = cluster.get("ClusterName")
        action = cluster.get("Action", None)

        message = "Valid"

        if action is not None and action != str(Action.UPGRADE.value):
            message = f"Only Upgrade value is allowed for action field in `Upgrade` array for {cluster_name}"
            return False, message

        managed_node_groups = cluster.get("UpgradeOptions").get("ManagedNodeGroups", [])
        if len(managed_node_groups) != 0:
            for node in managed_node_groups:
                name = node.get("Name", None)
                if name is None:
                    message = f"One of these fields are missing in ManagedNodeGroups - Name for {cluster_name}"
                    return False, message

        return True, message

    def set_defaults(self, cluster: Cluster) -> None:
        """
        Below defaults will be set.
        * DesiredEKSVersion = Latest EKS version

        Args:
            cluster: Input cluster object

        Returns:
            None
        """

        options = cluster.get("UpgradeOptions", {})
        options["DesiredEKSVersion"] = options.get(
            "DesiredEKSVersion", self.default_options.get("DesiredEKSVersion")
        )

        cluster["UpgradeOptions"] = options


class EventTargets(TargetLocation):
    """
    Implementation for TargetLocation class.
    Fetch the target details from the lambda event.
    """

    def __init__(self, input_targets: []):
        logger.info("Fetching TargetLocations from Lambda Event")
        self._input_targets = input_targets

    def get_locations(self) -> []:
        """
        Get the target locations from the event

        Returns:
            []: List of target locations
        """

        target_locations = []
        for target in self._input_targets:
            target_locations.append(self.get_target(target))

        return target_locations

    def extract_target_from_input(self, item: dict) -> InputTarget:
        """
        Convert the target item (dict) into an InputTarget

        Args:
            item: target item in the event

        Returns:
            InputTarget
        """

        account_id = item.get("AccountId", None)
        region = item.get("Region", None)
        role = item.get("ExecutionRoleName", None)

        if account_id is None or region is None:
            raise Exception("AccountId and Region are required")

        target = {"Account": account_id, "Region": region, "ExecutionRoleName": role}

        input_target_str = json.dumps(target)
        input_target: InputTarget = json.loads(input_target_str)
        logger.debug(f"Input Target Location: {input_target}")
        return input_target
