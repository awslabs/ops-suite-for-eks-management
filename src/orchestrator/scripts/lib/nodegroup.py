import logging

from .wfutils import Progress

# Constants
ACTIVE_STATUS: str = "ACTIVE"


def get_node_group_content(
    name: str,
    message: str,
    status: str = "Update Manually",
    desired_version: str = "N/A",
) -> dict:
    """
    Get the node group content for a given node group name and version.

    Args:
        name: Name of the Node Group
        message: Message
        status: Status of the Node Group
        desired_version: Desired version to upgrade to

    Returns:
        dict: (Name, DesiredVersion, UpdateStatus, Message)
    """

    return dict(
        Name=name, DesiredVersion=desired_version, UpdateStatus=status, Message=message
    )


class NodeGroup:
    """
    Base class to update the node groups. A child class can extend this class and implement the following methods:
    *update_node
    """

    def __init__(
        self,
        node_type: str,
        region: str,
        cluster: str,
        node_name: str,
        desired_eks_version: str,
    ):
        log_name = f"{node_type}.NodeGroup"
        self.logger = logging.getLogger(log_name)

        self.region = region
        self.cluster = cluster
        self.node_name = node_name
        self.desired_eks_version = desired_eks_version

    def update(self, node_details: dict, progress: Progress) -> dict:
        """
        Update the node group.
        * If the node group is not in ACTIVE status during upgrade, it will be skipped.
        * If the node group is already running the desired EKS version, it will be skipped.

        Args:
            node_details: Detailed information about the node group being updated.
            progress: Progress object to track the number of node groups that are being updated or ignored.

        Returns:
            dict: (Name, DesiredVersion, UpdateStatus, Message)
        """

        current_version = node_details.get("version")
        status = node_details.get("status")

        if status != ACTIVE_STATUS:
            progress.not_active_increment()
            self.logger.info(
                f"{self.node_name} in {self.cluster} is in {status}. Cannot be updated.."
            )

            return get_node_group_content(
                name=self.node_name,
                desired_version=self.desired_eks_version,
                message="NodeGroup status is not ACTIVE",
            )

        if self.desired_eks_version == current_version:
            progress.no_action_increment()
            self.logger.info(
                f"{self.node_name} in {self.cluster} already running {self.desired_eks_version}"
            )
            return get_node_group_content(
                name=self.node_name,
                status="No Action",
                desired_version=self.desired_eks_version,
                message="Already running desired version",
            )

        return self.update_node(progress)

    def update_node(self, progress: Progress) -> dict:
        """
        Core logic to update the node. This needs to be implemented in the child class.

        Args:
            progress: Progress object to track the number of node groups that are being updated or ignored.

        Returns:
            dict: (Name, DesiredVersion, UpdateStatus, Message)
        """

        pass
