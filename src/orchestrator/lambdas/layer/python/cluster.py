from enum import Enum
from typing import List, TypedDict

from aws_lambda_powertools import Logger

logger = Logger()


class Action(Enum):
    SUMMARY = "SUMMARY"
    BACKUP = "BACKUP"
    RESTORE = "RESTORE"
    UPGRADE = "UPGRADE"


class ManagedNodeGroup(TypedDict):
    Name: str
    LaunchTemplateVersion: str


class UpgradeOptions(TypedDict):
    DesiredEKSVersion: str
    AddonsToUpdate: List[str]
    CommonLaunchTemplateVersion: str
    ManagedNodeGroups: List[ManagedNodeGroup]


class BackupOptions(TypedDict):
    BackupName: str
    VeleroNamespace: str
    VeleroPluginVersion: str
    ServiceAccount: str
    ServiceAccountRoleName: str
    VeleroArguments: dict


class RestoreOptions(TypedDict):
    BackupName: str
    VeleroArguments: dict


class Cluster(TypedDict):
    AccountId: str
    Region: str
    ClusterName: str
    Action: str
    Source: str
    UpgradeOptions: UpgradeOptions
    BackupOptions: BackupOptions
    RestoreOptions: RestoreOptions


class ClusterSource:
    _source: str = None

    def __init__(self, source: str, default_options: dict):
        self._source = source
        self._default_options = default_options

    @property
    def source(self) -> str:
        return self._source

    @property
    def default_options(self):
        return self._default_options

    def get_clusters(self) -> [Cluster]:
        pass


class DefaultSource(ClusterSource):

    def __init__(self):
        super().__init__("DEFAULT", default_options={})

    def get_clusters(self) -> [Cluster]:
        return []
