import logging

import yaml

from .processhelper import ProcessHelper
from .wfutils import FileUtility, Progress

# Constants
"""
Addons that are supported for upgrade.
"""
SUPPORTED_ADDONS_FOR_UPDATE: [str] = [
    "vpc-cni",
    "coredns",
    "kube-proxy",
    "aws-ebs-csi-driver",
    "aws-efs-csi-driver",
    "snapshot-controller",
    "adot",
    "aws-guardduty-agent",
    "amazon-cloudwatch-observability",
    "eks-pod-identity-agent",
    "aws-mountpoint-s3-csi-driver",
]

"""
Addons that are upgrades by default if none are provided in the input.
"""
DEFAULT_ADDONS_FOR_UPDATE: [str] = ["vpc-cni", "coredns", "kube-proxy"]

"""
Addons that can only be updated to a minor version at a time.
"""
MINOR_VERSION_UPDATES: [str] = ["vpc-cni", "eks-pod-identity-agent"]

"""
Name of the script file used for updating the addons.
"""
SCRIPT_NAME: str = "update_aws_addons.sh"

ACTIVE_STATUS: str = "ACTIVE"


def get_addon_content(
    name: str,
    version: str,
    message: str,
    status: str = "Update Manually",
    updated_version: str = "N/A",
) -> dict:
    """
    Get the addon content for a given addon name and version.

    Args:
        name: Name of the addon.
        version: Version of the addon prior to the update.
        message: Message, if any, for the addon update.
        status: Status of the addon update.
        updated_version: Updated version of the addon.

    Returns:
        dict: (Name, Version, UpdatedVersion, UpdateStatus, Message)
    """

    return dict(
        Name=name,
        Version=version,
        UpdatedVersion=updated_version,
        UpdateStatus=status,
        Message=message,
    )


class UpdateConfigYamlGenerator:
    """
    Class that is used to generate the addon update configuration file.
    This will be used by the `eksctl` to update the addon.
    """

    def __init__(self, log_name: str):
        self.logger = logging.getLogger(log_name)

    def generate_update_config(
        self,
        region: str,
        cluster: str,
        addon: str,
        version: str,
        service_account_role: str,
    ):
        """
        Generate YAMl config file for addon update.

        Args:
            region: AWS Region
            cluster: EKS Cluster Name
            addon: Addon Name
            version: Addon version to upgrade to.
            service_account_role: Service Account role that needs to be attached to the addon.

        Returns:
            Any: Update Addon YAMl config file
        """

        self.logger.debug(f"Generating update config for addon {addon}")
        addon_update = {
            "apiVersion": "eksctl.io/v1alpha5",
            "kind": "ClusterConfig",
            "metadata": {"name": cluster, "region": region},
            "addons": [
                {"name": addon, "version": version, "resolveConflicts": "preserve"}
            ],
        }

        if service_account_role is not None and service_account_role != "":
            addon_update["addons"][0]["serviceAccountRoleARN"] = service_account_role

        self.logger.debug(f"Generating update config for addon {addon}: {addon_update}")
        return yaml.dump(addon_update, default_flow_style=False)


class Addon:
    """
    Base class to update the addons. A child class can extend this class and implement the following methods:
    * get_update_version
    """

    def __init__(
        self,
        log_name: str,
        region: str,
        cluster: str,
        addon_name: str,
        desired_eks_version: str,
        script_file_path: str,
    ):
        """
        Args:
            log_name: Name of the logger
            region: AWS Region
            cluster: EKS Cluster Name
            addon_name: Addon Name
            desired_eks_version: Desired EKS Version. This will be used to get the update addon version.
            script_file_path: Path to find the bash script files.
        """

        self.logger = logging.getLogger(log_name)
        self.process_helper = ProcessHelper(log_name)

        self.region = region
        self.cluster = cluster
        self.addon_name = addon_name
        self.desired_eks_version = desired_eks_version
        self.script_file_path = script_file_path

        self.script_file = f"{script_file_path}/{SCRIPT_NAME}"

        self.config_generator = UpdateConfigYamlGenerator(log_name)

    def update(
        self, addon_details: dict, input_addons: [str], progress: Progress
    ) -> dict:
        """
        Update the addon.
        * If the addon is not present in the list of input addons, a specific message will be populated
            to inform if the addon is supported or skipped due to not being present in the input.
        * If the addon is not in ACTIVE status during upgrade, it will be skipped.

        Args:
            addon_details: Detailed information about the addon being updated.
            input_addons: List of addons present in the input.
            progress: Progress object to track the number of addons that are being updated or ignored.

        Returns:
            dict: (Name, Version, UpdatedVersion, UpdateStatus, Message)
        """

        addon_version = addon_details.get("addonVersion")

        if self.addon_name not in input_addons:

            if self.addon_name in SUPPORTED_ADDONS_FOR_UPDATE:
                progress.not_requested_increment()
                message = "Not present in the input addons to update"
            else:
                progress.not_supported_increment()
                message = "Not supported. Update manually"

            self.logger.info(f"{self.addon_name}: {message}")
            return get_addon_content(
                name=self.addon_name, version=addon_version, message=message
            )

        self.logger.info(f"Updating {self.addon_name}")
        status = addon_details.get("status", None)

        if status != ACTIVE_STATUS:
            progress.not_active_increment()
            message = "Status is not ACTIVE. Manually update the addon"
            self.logger.info(f"{self.addon_name}: {message}")
            return get_addon_content(
                name=self.addon_name, version=addon_version, message=message
            )

        service_account_role = addon_details.get("serviceAccountRoleArn", "")
        return self.execute_addon_script(addon_version, service_account_role, progress)

    def execute_addon_script(
        self, addon_version: str, service_account_role: str, progress: Progress
    ) -> dict:
        """
        Upgrade the Addon using `update_aws_addons.sh` script file.
        Update will be skipped if the current addon version is the latest supported for the desired EKS version.

        Args:
            addon_version: Addon version to upgrade to
            service_account_role: Service Account Role ARN, if present,
                that will be attached to the addon while upgrading.
            progress: Progress object to track the number of addons that are being updated or ignored.

        Returns:
            dict: (Name, Version, UpdatedVersion, UpdateStatus, Message)
        """

        update_version = self.get_update_version(addon_version=addon_version)

        if addon_version == update_version:
            progress.no_action_increment()
            message = "Running with latest version"
            self.logger.info(f"{self.addon_name}: {message}")

            return get_addon_content(
                name=self.addon_name,
                version=addon_version,
                status="No Action",
                updated_version=update_version,
                message=message,
            )

        config_yaml_content = self.config_generator.generate_update_config(
            region=self.region,
            cluster=self.cluster,
            addon=self.addon_name,
            version=update_version,
            service_account_role=service_account_role,
        )

        self.logger.debug(
            f"Addon YAMl update file for {self.cluster}.{self.addon_name}: {config_yaml_content}"
        )
        yaml_file_path: str = (
            f"{self.script_file_path}/{self.cluster}-{self.addon_name}.yaml"
        )
        FileUtility.write_yaml(yaml_file_path, config_yaml_content)

        command_arguments: list[str] = [
            "-c",
            self.cluster,
            "-r",
            self.region,
            "-a",
            self.addon_name,
            "-f",
            yaml_file_path,
        ]
        resp = self.process_helper.run_shell(
            script_file=self.script_file, arguments=command_arguments
        )

        if resp == 0:
            progress.updated_increment()
            self.logger.info(
                f"Updating {self.cluster}.{self.addon_name} to the desired version {update_version} is success"
            )
            return get_addon_content(
                name=self.addon_name,
                status="Success",
                updated_version=update_version,
                version=addon_version,
                message="Updated",
            )

        else:
            progress.failed_increment()
            self.logger.error(
                f"Update script failed while updating {self.cluster}.{self.addon_name} "
                f"to the desired version {update_version}"
            )
            return get_addon_content(
                name=self.addon_name,
                status="Failure",
                updated_version=update_version,
                version=addon_version,
                message="Update addon script failed",
            )

    def get_update_version(self, addon_version: str) -> str:
        """
        Get the addon version to update to based on the current addon version.
        Args:
            addon_version: Current Addon Version

        Returns:
            str: Addon Version to upgrade to
        """

        pass
