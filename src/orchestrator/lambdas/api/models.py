from typing import Optional

from aws_lambda_powertools.utilities.parser import BaseModel, Field


class RequestCluster(BaseModel):
    AccountId: str = Field(alias="AccountId", default=None)
    Region: str = Field(alias="Region", default=None)
    ClusterName: str = Field(alias="ClusterName", default=None)


class RestoreOptionsRequest(BaseModel):
    BackupName: str = Field(alias="BackupName", default=None)


class RestoreCluster(RequestCluster):
    RestoreOptions: RestoreOptionsRequest = Field(alias="RestoreOptions", default={})


class RestoreClusterRequest(BaseModel):
    Restore: list[RestoreCluster] = Field(alias="Restore", default=[])


class RestoreRequest(BaseModel):
    Clusters: RestoreClusterRequest = Field(alias="Clusters", default={})


class BackupOptionsRequest(BaseModel):
    BackupName: Optional[str] = Field(alias="BackupName", default=None)
    VeleroNamespace: Optional[str] = Field(alias="VeleroNamespace", default=None)
    ServiceAccount: Optional[str] = Field(alias="ServiceAccount", default=None)
    ServiceAccountRoleName: Optional[str] = Field(
        alias="ServiceAccountRoleName", default=None
    )


class BackupCluster(RequestCluster):
    BackupOptions: Optional[BackupOptionsRequest] = Field(
        alias="BackupOptions", default={}
    )


class BackupClusterRequest(BaseModel):
    Backup: list[BackupCluster] = Field(alias="Backup", default=[])


class BackupRequest(BaseModel):
    Clusters: BackupClusterRequest = Field(alias="Clusters", default={})


class UpgradeOptionsRequest(BaseModel):
    DesiredEKSVersion: Optional[str] = Field(alias="DesiredEKSVersion")


class UpgradeCluster(RequestCluster):
    UpgradeOptions: Optional[UpgradeOptionsRequest] = Field(
        alias="UpgradeOptions", default={}
    )


class UpgradeClusterRequest(BaseModel):
    Upgrade: list[UpgradeCluster] = Field(alias="Upgrade", default=[])


class UpgradeRequest(BaseModel):
    Clusters: UpgradeClusterRequest = Field(alias="Clusters", default={})


class SummaryClusterRequest(BaseModel):
    Summary: Optional[list[RequestCluster]] = Field(
        alias="Summary",
        default=[],
    )


class SummaryRequest(BaseModel):
    Clusters: Optional[SummaryClusterRequest] = Field(alias="Clusters", default={})


class Tenant(BaseModel):
    AccountId: str = Field(alias="AccountId", default=None)
    Region: str = Field(alias="Region", default=None)
    ExecutionRoleName: str = Field(alias="ExecutionRoleName", default=None)


class TenantRequest(BaseModel):
    Tenants: list[Tenant] = Field(alias="Tenants", default=[])
