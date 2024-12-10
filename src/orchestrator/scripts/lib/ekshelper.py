import logging
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

from .wfutils import ExecutionUtility

# Constants
"""
Statuses to used to filter the EKS Cluster insights.
"""
DEFAULT_INSIGHT_STATUSES: [] = ["PASSING", "WARNING", "ERROR", "UNKNOWN"]

"""
Minimum Kubernetes minor version.
"""
MIN_KUBERNETES_MINOR_VERSION: str = "0.01"


class EKSHelper:
    """
    Wrapper class for EKS boto3 client
    """

    eks_client = None

    def __init__(self, region: str, calling_module: str):
        log_name = f"{calling_module}.EKSHelper"
        self._logger = logging.getLogger(log_name)

        self.eks_client = boto3.client("eks", region_name=region)

    def list_clusters(self) -> []:
        """
        Get all the clusters available in the account and region.

        Returns:
            []: List of clusters available in the Account region.
        """

        cluster_list = []
        request = {"maxResults": 100, "include": ["all"]}

        while True:
            try:
                response = self.eks_client.list_clusters(**request)
                cluster_list.extend(response.get("clusters"))

                next_token = response.get("nextToken")
                if next_token is None:
                    break
                else:
                    request.update(nextToken=next_token)
            except ClientError as e:
                self._logger.error(f"Error while listing EKS clusters: {e}")
                ExecutionUtility.stop()

        return cluster_list

    def get_eks_cluster_details(self, cluster_name: str) -> dict:
        """
        Get the EKS version and status.

        Args:
            cluster_name: Name of the EKS Cluster

        Returns:
            dict: EKS Cluster details
        """

        try:
            response = self.eks_client.describe_cluster(
                name=cluster_name,
            )
            return dict(
                version=response["cluster"]["version"],
                status=response["cluster"]["status"],
            )
        except ClientError as e:
            self._logger.error(
                f"Error while fetching EKS version using describe_cluster API {cluster_name}: {e}"
            )
            ExecutionUtility.stop()

    def can_describe_cluster(self, cluster_name) -> bool:
        """
        Checks weather the IAM role has access to the cluster or not.

        Args:
            cluster_name: Name of the EKS cluster to be described

        Returns:
            bool: True or False depending on the access.
        """

        try:
            self.eks_client.describe_cluster(name=cluster_name)
            return True
        except ClientError as e:
            self._logger.error(f"Exception while describing {cluster_name}: {e}")
            return False

    def list_node_groups(self, cluster_name: str) -> []:
        """
        Get all the node groups in the cluster

        Args:
            cluster_name: Name of the EKS Cluster

        Returns:
            []: List of node groups associated with the cluster
        """

        node_groups = []
        request = {"clusterName": cluster_name, "maxResults": 50}
        while True:
            try:
                response = self.eks_client.list_nodegroups(**request)
                node_groups.extend(response.get("nodegroups"))
                next_token = response.get("nextToken")

                if next_token is None:
                    break
                else:
                    request.update(nextToken=next_token)

            except ClientError as e:
                self._logger.error(
                    f"Error while listing node groups for {cluster_name}: {e}"
                )
                ExecutionUtility.stop()

        return node_groups

    def get_node_group_details(self, cluster_name: str, node_group_name: str) -> dict:
        """
        Get the node group details.

        Args:
            cluster_name: Name of the EKS Cluster
            node_group_name: Name of the Node group

        Returns:
            dict: Node group details

        """

        request = {"clusterName": cluster_name, "nodegroupName": node_group_name}
        try:
            response = self.eks_client.describe_nodegroup(**request)
            return response.get("nodegroup")

        except ClientError as e:
            self._logger.error(
                f"Error while fetching node group details for {cluster_name}.{node_group_name}: {e}"
            )
            ExecutionUtility.stop()

    def list_addons(self, cluster_name: str) -> []:
        """
        Get all the addons attached to the cluster.

        Args:
            cluster_name: name of the EKS Cluster

        Returns:
            []: List of addons
        """

        addons = []
        request = {"clusterName": cluster_name, "maxResults": 50}
        while True:
            try:
                response = self.eks_client.list_addons(**request)
                addons.extend(response.get("addons"))
                next_token = response.get("nextToken")

                if next_token is None:
                    break
                else:
                    request.update(nextToken=next_token)

            except ClientError as e:
                self._logger.error(
                    f"Error while listing addons for {cluster_name}: {e}"
                )
                ExecutionUtility.stop()

        return addons

    def get_addon_details(self, cluster_name: str, addon_name: str) -> dict:
        """

        Args:
            cluster_name: Name of the EKS Cluster
            addon_name: Name of the Addon

        Returns:
            dict: Addon details
        """

        request = {"clusterName": cluster_name, "addonName": addon_name}

        try:
            response = self.eks_client.describe_addon(**request)
            return response.get("addon")
        except ClientError as e:
            self._logger.error(
                f"Error while describing addon {addon_name} for {cluster_name}: {e}"
            )
            ExecutionUtility.stop()

    def get_addon_versions(self, addon_name: str, kubernetes_version: str) -> []:
        """
        Get all the available versions of an addon for the given kubernetes version.

        Args:
            addon_name:
            kubernetes_version:

        Returns:
            []: Available addon version for the addon for the given kubernetes version.
        """

        all_versions: [] = []

        request = {"kubernetesVersion": kubernetes_version, "addonName": addon_name}

        while True:
            try:
                response = self.eks_client.describe_addon_versions(**request)
                all_versions.extend(response.get("addons"))

                next_token = response.get("nextToken")

                if next_token is None:
                    break
                else:
                    request.update(nextToken=next_token)

            except ClientError as e:
                self._logger.error(
                    f"Error while describing addon {addon_name} versions for kubernetes {kubernetes_version}: {e}"
                )
                ExecutionUtility.stop()

        return self.extract_details_from_addon_versions(
            all_versions, kubernetes_version
        )

    def extract_details_from_addon_versions(
        self, addon_versions: [], kubernetes_version: str
    ) -> []:
        """
        Extract the addon versions by filtering based on the given kubernetes version.
        The filtered addon versions will only have dict(addonVersion, defaultVersion)

        Args:
            addon_versions: List of addon versions
            kubernetes_version: Kubernetes version for which addons need to be extracted

        Returns:
            []: List of addon versions with the needed details filtered by the given kubernetes version
        """

        try:
            required_details: [] = []
            for addon in addon_versions:
                addon_versions = addon.get("addonVersions")
                for version in addon_versions:
                    compatibilities = version.get("compatibilities")
                    addon_version = version.get("addonVersion")
                    for compatibility in compatibilities:
                        cluster_version = compatibility.get("clusterVersion")
                        default_version = compatibility.get("defaultVersion")
                        if kubernetes_version == cluster_version:
                            required_version = dict(
                                addonVersion=addon_version,
                                defaultVersion=default_version,
                            )
                            required_details.append(required_version)

            return required_details
        except ClientError as e:
            self._logger.error(
                f"Error while extracting addon details from {addon_versions}: {e}"
            )
            ExecutionUtility.stop()

    @staticmethod
    def get_default_addon_version(addon_versions: []) -> str:
        """
        Get the default addon version from the given list of versions.

        Args:
            addon_versions: List of addons versions

        Returns:
            str: Default addon version
        """

        for version in addon_versions:
            if version.get("defaultVersion"):
                return version.get("addonVersion")

    def get_next_minor_addon_version(
        self, addon_version: str, addon_versions: [], need_default_version: bool = True
    ) -> str:
        """
        Get the next minor version compared to the current addon version.
        Note: Some addons can only be updated by one minor version.

        Args:
            addon_version: Current addon version
            addon_versions: List of addon versions available for the given kubernetes version
            need_default_version: Whether the version needs to be a default one.

        Returns:
            str: Next minor addon version

        """

        minor_addon_version = self.extract_minor_version(addon_version)
        next_minor_version = minor_addon_version + 1
        all_minor_versions = [
            i
            for i in addon_versions
            if next_minor_version == self.extract_minor_version(i.get("addonVersion"))
        ]

        self._logger.info(
            f"Available Minor Versions {len(all_minor_versions)}: {all_minor_versions}"
        )

        if len(all_minor_versions) == 0:
            self._logger.info(
                f"{addon_version} supports the desired EKS version. No need to update."
            )
            return addon_version

        default_version = self.get_default_addon_version(
            addon_versions=all_minor_versions
        )

        if (
            need_default_version
            and default_version is not None
            and next_minor_version == self.extract_minor_version(default_version)
        ):
            self._logger.info(
                f"Next minor version update which is a default version found: {default_version} "
            )
            return default_version

        sorted_versions_list = sorted(
            all_minor_versions, key=lambda i: i["addonVersion"]
        )
        self._logger.info(f"Next minor version update found: {sorted_versions_list[0]}")
        return sorted_versions_list[0].get("addonVersion")

    def extract_minor_version(self, addon_version: str) -> int:
        """
        Extract the minor version number from the addon version.
        Example: If the version is v1.1.0-eksbuild.1, then return 1
        Args:
            addon_version: EKS addon version

        Returns:
            int: Minor version number
        """

        try:
            version_array = addon_version.split(".")
            return int(version_array[1])
        except ClientError as e:
            self._logger.error(
                f"Error while extracting minor version number from {addon_version}: {e}"
            )
            ExecutionUtility.stop()

    def list_insights(
        self, cluster_name: str, kubernetes_version: str, filter_statuses=None
    ) -> []:
        """
        Get all the cluster insights related to UPGRADE_READINESS filtered by the kubernetes version
        and statuses.

        Args:
            cluster_name: Name of the EKS cluster
            kubernetes_version: Desired kubernetes version
            filter_statuses: List of statuses used for filtering.

        Returns:
            []: List of insights
        """

        if filter_statuses is None:
            filter_statuses = DEFAULT_INSIGHT_STATUSES

        self._logger.info(
            f"Listing Insights for {cluster_name} and version {kubernetes_version}"
        )
        versions: [] = self.previous_kubernetes_versions(
            cluster_name, kubernetes_version
        )
        self._logger.info(f"Filtering for {versions} kubernetes versions")

        insights = []
        request = {
            "clusterName": cluster_name,
            "filter": {
                "categories": ["UPGRADE_READINESS"],
                "kubernetesVersions": versions,
                "statuses": filter_statuses,
            },
            "maxResults": 100,
        }
        while True:
            try:
                response = self.eks_client.list_insights(**request)
                insights.extend(response.get("insights"))
                next_token = response.get("nextToken")

                if next_token is None:
                    break
                else:
                    request.update(nextToken=next_token)

            except ClientError as e:
                self._logger.error(
                    f"Error while listing insights for {cluster_name}: {e}"
                )
                ExecutionUtility.stop()

        return insights

    def describe_insight(self, cluster_name: str, insight_id: str) -> dict:
        """
        Get the insight details for the given cluster and insight ID.

        Args:
            cluster_name: Name of the EKS cluster
            insight_id: Insight ID

        Returns:
            dict: Insight details
        """

        self._logger.info(
            f"Describing Insights for {cluster_name} for insight id {insight_id}"
        )
        request = {"clusterName": cluster_name, "id": insight_id}

        try:
            response = self.eks_client.describe_insight(**request)
            return response.get("insight")
        except Exception as e:
            self._logger.error(
                f"Error while describing insights for {cluster_name} and id {insight_id}: {e}"
            )
            ExecutionUtility.stop()

    def previous_kubernetes_versions(
        self, cluster_name: str, desired_version: str
    ) -> []:
        """
        Get the older kubernetes versions for the given kubernetes version.

        Args:
            cluster_name: Name of the EKS cluster. Used only for logging purpose.
            desired_version: Desired kubernetes version for which previous version be will fetched.

        Returns:
            []: List of older kubernetes versions
        """

        versions: [] = []
        eks_details = self.get_eks_cluster_details(cluster_name)
        eks_version = eks_details.get("version")

        current: Decimal = Decimal(eks_version)
        desired: Decimal = Decimal(desired_version)

        self._logger.info(f"current: {current}; desired: {desired}")

        if current == Decimal:
            versions.append(desired_version)
        else:
            while current < desired:
                desired = desired - Decimal(MIN_KUBERNETES_MINOR_VERSION)
                versions.append(str(desired))

        return versions

    def list_fargate_profiles(self, cluster_name: str) -> []:
        """
        Get all the fargate profiles for the given cluster.

        Args:
            cluster_name: Name of the EKS cluster.

        Returns:
            []: List of fargate profiles

        """

        fargate_profiles = []
        request = {"clusterName": cluster_name, "maxResults": 50}
        while True:
            try:
                response = self.eks_client.list_fargate_profiles(**request)
                fargate_profiles.extend(response.get("fargateProfileNames"))
                next_token = response.get("nextToken")

                if next_token is None:
                    break
                else:
                    request.update(nextToken=next_token)

            except ClientError as e:
                self._logger.error(
                    f"Error while listing fargate profiles for {cluster_name}: {e}"
                )
                ExecutionUtility.stop()

        return fargate_profiles

    def is_fargate_cluster(self, cluster_name: str) -> bool:
        """
        Check weather the given cluster only has fargate profiles.

        Args:
            cluster_name: Name of the EKS cluster.

        Returns:
            bool: True if cluster only has fargate profiles, False otherwise.
        """

        node_groups = self.list_node_groups(cluster_name)
        fargate_profiles = self.list_fargate_profiles(cluster_name)

        return len(node_groups) == 0 and len(fargate_profiles) > 0

    def check_namespace_selector(
        self, cluster_name: str, fargate_profile_name: str, velero_namespace: str
    ) -> bool:
        """
        Check whether the fargate profile has the given namespace.

        Args:
            cluster_name: Name of the EKS cluster
            fargate_profile_name: Name of the fargate profile
            velero_namespace: Velero namespace

        Returns:
            bool: True if velero namespace is present in the fargate profile, False otherwise.

        """

        namespace_selector_present = False

        try:

            response = self.eks_client.describe_fargate_profile(
                clusterName=cluster_name, fargateProfileName=fargate_profile_name
            )

            profile = response.get("fargateProfile")
            status = profile.get("status")

            if status == "ACTIVE":
                selectors = profile.get("selectors")
                for selector in selectors:
                    namespace = selector.get("namespace")
                    if velero_namespace == namespace:
                        namespace_selector_present = True
                        break

            return namespace_selector_present

        except ClientError as e:
            self._logger.error(
                f"Error while describing fargate profile for {cluster_name}: {e}"
            )
            ExecutionUtility.stop()

    def check_namespace_selector_all_profiles(
        self, cluster_name: str, namespace: str
    ) -> bool:
        """
        Check weather the given namespace is present in any of the fargate profiles.

        Args:
            cluster_name: Name of the EKS cluster.
            namespace: Velero Namespace

        Returns:
            bool: True if the namespace is present in any of the fargate profiles, False otherwise.

        """

        namespace_selector_present = False

        fargate_profiles = self.list_fargate_profiles(cluster_name)

        for profile in fargate_profiles:
            namespace_selector_present = self.check_namespace_selector(
                cluster_name, profile, namespace
            )

            if namespace_selector_present:
                break

        return namespace_selector_present

    def fargate_cluster_check(self, cluster_name: str, namespace: str) -> str:
        """
        Check weather the velero plugin can be installed on the clusters.

        Args:
            cluster_name: Name of the EKS Cluster.
            namespace: Velero Namespace

        Returns:
            str: FAIL if the cluster only has fargate profiles and none of them have the namespace. PASS otherwise.

        """

        if self.is_fargate_cluster(cluster_name):
            self._logger.info(f"{cluster_name} only has fargate profiles")
            if not self.check_namespace_selector_all_profiles(cluster_name, namespace):
                self._logger.warning(
                    f"{namespace} namespace is not present in any of the fargate profile selectors"
                )
                return "FAIL"

        return "PASS"
