class ManagedNodeGroup:
    """
    Model class for EKS managed node groups
    """

    _name: str = None
    _launch_template_version: str = None

    def __init__(self, input_node_group: dict):
        self.name = input_node_group.get("Name", None)
        self.launch_template_version = input_node_group.get(
            "LaunchTemplateVersion", None
        )

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, name: str):
        self._name = name

    @property
    def launch_template_version(self) -> str:
        return self._launch_template_version

    @launch_template_version.setter
    def launch_template_version(self, launch_template_version: str):
        self._launch_template_version = launch_template_version

    def __str__(self):
        return f"{self.name}"

    def __repr__(self):
        class_name = type(self).__name__
        return f"{class_name}(name={self.name!r}, launch_template_version={self.launch_template_version!r})"


class UpgradeOptions:
    """ "
    Model class for upgrade options.
    """

    _desired_eks_version: str = None
    _amazon_eks_addons_to_update: [str] = []
    _common_launch_template_version: str = None
    _managed_node_groups: [ManagedNodeGroup] = []

    def __init__(self, upgrade_options: dict):
        self.desired_eks_version = upgrade_options.get("DesiredEKSVersion")
        self.addons_to_update = upgrade_options.get("AddonsToUpdate", [])
        self.common_launch_template_version = upgrade_options.get(
            "CommonLaunchTemplateVersion", None
        )
        self.managed_node_groups = upgrade_options.get("ManagedNodeGroups", [])

    @property
    def desired_eks_version(self) -> str:
        return self._desired_eks_version

    @desired_eks_version.setter
    def desired_eks_version(self, desired_eks_version: str):
        self._desired_eks_version = desired_eks_version

    @property
    def addons_to_update(self) -> [str]:
        return self._amazon_eks_addons_to_update

    @addons_to_update.setter
    def addons_to_update(self, addons_to_update: [str]):
        self._amazon_eks_addons_to_update = addons_to_update

    @property
    def common_launch_template_version(self) -> str:
        return self._common_launch_template_version

    @common_launch_template_version.setter
    def common_launch_template_version(self, version: str):
        self._common_launch_template_version = version

    @property
    def managed_node_groups(self) -> [ManagedNodeGroup]:
        return self._managed_node_groups

    @managed_node_groups.setter
    def managed_node_groups(self, managed_node_groups: [dict]):
        if len(managed_node_groups) == 0:
            self._managed_node_groups = []
        else:
            for node in managed_node_groups:
                managed_node_group = ManagedNodeGroup(node)
                self._managed_node_groups.append(managed_node_group)

    def __repr__(self):
        class_name = type(self).__name__
        return (
            f"{class_name}(desired_eks_version={self.desired_eks_version!r}, "
            f"addons_to_update={self.addons_to_update!r},"
            f"common_launch_template_version={self.common_launch_template_version!r},"
            f"managed_node_groups={self._managed_node_groups!r})"
        )


class BackupOptions:
    """ "
    Model class for backup options.
    """

    _backup_name: str = None
    _velero_namespace: str = None
    _service_account: str = None
    _service_account_role_name: str = None
    _velero_plugin_version: str = None
    _velero_arguments: dict = {}

    def __init__(self, backup_options: dict):
        self.backup_name = backup_options.get("BackupName")
        self.velero_namespace = backup_options.get("VeleroNamespace")
        self.service_account = backup_options.get("ServiceAccount")
        self.service_account_role_name = backup_options.get("ServiceAccountRoleName")
        self.velero_plugin_version = backup_options.get("VeleroPluginVersion")
        self.velero_arguments = backup_options.get("VeleroArguments", {})

    @property
    def backup_name(self) -> str:
        return self._backup_name

    @backup_name.setter
    def backup_name(self, backup_name: str):
        self._backup_name = backup_name

    @property
    def velero_namespace(self) -> str:
        return self._velero_namespace

    @velero_namespace.setter
    def velero_namespace(self, velero_namespace: str):
        self._velero_namespace = velero_namespace

    @property
    def service_account(self) -> str:
        return self._service_account

    @service_account.setter
    def service_account(self, service_account: str):
        self._service_account = service_account

    @property
    def service_account_role_name(self) -> str:
        return self._service_account_role_name

    @service_account_role_name.setter
    def service_account_role_name(self, service_account_role_name: str):
        self._service_account_role_name = service_account_role_name

    @property
    def velero_plugin_version(self):
        return self._velero_plugin_version

    @velero_plugin_version.setter
    def velero_plugin_version(self, velero_plugin_version: str):
        self._velero_plugin_version = velero_plugin_version

    @property
    def velero_arguments(self) -> dict:
        return self._velero_arguments

    @velero_arguments.setter
    def velero_arguments(self, velero_arguments: dict):
        self._velero_arguments = velero_arguments

    def __repr__(self):
        class_name = type(self).__name__
        return (
            f"{class_name}(backup_name={self.backup_name!r},"
            f"velero_namespace={self.velero_namespace!r}, "
            f"service_account={self.service_account!r},"
            f"service_account_role_name={self.service_account_role_name!r},"
            f"velero_arguments={self.velero_arguments!r})"
        )


class RestoreOptions:
    """ "
    Model class for backup options.
    """

    _backup_name: str = None
    _velero_arguments: dict = {}

    def __init__(self, backup_options: dict):
        self.backup_name = backup_options.get("BackupName")
        self.velero_arguments = backup_options.get("VeleroArguments", {})

    @property
    def backup_name(self) -> str:
        return self._backup_name

    @backup_name.setter
    def backup_name(self, backup_name: str):
        self._backup_name = backup_name

    @property
    def velero_arguments(self) -> dict:
        return self._velero_arguments

    @velero_arguments.setter
    def velero_arguments(self, velero_arguments: dict):
        self._velero_arguments = velero_arguments

    def __repr__(self):
        class_name = type(self).__name__
        return (
            f"{class_name}(backup_name={self.backup_name!r}, "
            f"velero_arguments={self.velero_arguments!r})"
        )


class InputCluster:
    """ "
    Model class for input cluster.
    """

    _account_id: str = None
    _region: str = None
    _cluster: str = None
    _action: str = None
    _upgrade_options: UpgradeOptions = None
    _backup_options: BackupOptions = None
    _restore_options: RestoreOptions = None

    def __init__(self, input_cluster: dict):
        self.account = input_cluster.get("AccountId", None)
        self.region = input_cluster.get("Region", None)
        self.cluster = input_cluster.get("ClusterName", None)
        self.action = input_cluster.get("Action", None)
        self.backup_options = input_cluster.get("BackupOptions", {})
        self.restore_options = input_cluster.get("RestoreOptions", {})
        self.upgrade_options = input_cluster.get("UpgradeOptions", {})

    @property
    def account(self) -> str:
        return self._account_id

    @account.setter
    def account(self, account_id: str):
        self._account_id = account_id

    @property
    def region(self) -> str:
        return self._region

    @region.setter
    def region(self, region: str):
        self._region = region

    @property
    def cluster(self) -> str:
        return self._cluster

    @cluster.setter
    def cluster(self, cluster: str):
        self._cluster = cluster

    @property
    def action(self) -> str:
        return self._action

    @action.setter
    def action(self, action: str):
        self._action = action

    def is_backup(self) -> bool:
        return self.action == "BACKUP"

    def is_restore(self) -> bool:
        return self.action == "RESTORE"

    @property
    def upgrade_options(self) -> UpgradeOptions:
        return self._upgrade_options

    @upgrade_options.setter
    def upgrade_options(self, upgrade_options: {}):
        self._upgrade_options = UpgradeOptions(upgrade_options)

    @property
    def backup_options(self) -> BackupOptions:
        return self._backup_options

    @backup_options.setter
    def backup_options(self, backup_options: {}):
        self._backup_options = BackupOptions(backup_options)

    @property
    def restore_options(self) -> RestoreOptions:
        return self._restore_options

    @restore_options.setter
    def restore_options(self, restore_options: {}):
        self._restore_options = RestoreOptions(restore_options)

    def cluster_equals(self, match_cluster: str) -> bool:
        return match_cluster == self.cluster

    def match_cluster(
        self, current_account: str, current_region: str, match_cluster: str
    ) -> bool:
        return (
            current_account == self.account
            and current_region == self.region
            and match_cluster == self.cluster
        )

    def __str__(self):
        return f"{self.account}:{self.region}:{self.cluster}"

    def __repr__(self):
        class_name = type(self).__name__
        return (
            f"{class_name}(account={self.account!r}, region={self.region!r}, cluster={self.cluster!r}, "
            f"action={self.action!r}, "
            f"upgrade_options={self.upgrade_options!r}, backup_options={self.backup_options!r}, "
            f"restore_options={self.restore_options!r})"
        )
