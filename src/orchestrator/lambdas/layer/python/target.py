from typing import TypedDict

from aws_lambda_powertools import Logger
from cluster import Cluster

logger = Logger()

# Constants
DEFAULT_TARGET_SSM_EXECUTION_ROLE = "EKSManagement-SSMAutomationExecutionRole"
DEFAULT_TARGET_LOCATION_MAX_CONCURRENCY = "10"
DEFAULT_TARGET_LOCATION_MAX_ERRORS = "1"


class InputTarget(TypedDict):
    Account: str
    Region: str
    ExecutionRoleName: str


class Target(TypedDict):
    Accounts: list
    Regions: list
    ExecutionRoleName: str


class Tenant(TypedDict):
    AccountId: str
    Region: str
    ExecutionRoleName: str
    ClusterName: str
    ClusterArn: str


class TargetLocation:
    """
    Class to get the target location.
    Child classes must implement
    * get_locations
    * extract_target_from_input
    """

    def get_locations(self) -> []:
        """
        Get the target locations.

        Returns:
            []: List of target locations
        """

        pass

    def get_locations_using_clusters(self, eks_clusters: [Cluster]) -> []:
        """
        Get the target locations from the input clusters.

        Returns:
            []: List of target locations
            eks_clusters: Array of input EKS clusters
        """

        pass

    def extract_target_from_input(self, item: dict) -> InputTarget:
        """
        Convert item to InputTarget

        Args:
            item: Item to convert to InputTarget

        Returns:
            InputTarget
        """

        pass

    def get_target(self, item: dict) -> dict:
        """
        Get the target location from the items.

        Args:
            item: Item to convert to InputTarget

        Returns:
            dict: Target details
        """

        input_target = self.extract_target_from_input(item)

        role = input_target.get("ExecutionRoleName", None)

        if role is None:
            role = DEFAULT_TARGET_SSM_EXECUTION_ROLE

        return {
            "Accounts": [input_target.get("Account")],
            "Regions": [input_target.get("Region")],
            "ExecutionRoleName": role,
            "TargetLocationMaxConcurrency": DEFAULT_TARGET_LOCATION_MAX_ERRORS,
            "TargetLocationMaxErrors": DEFAULT_TARGET_LOCATION_MAX_CONCURRENCY,
        }
