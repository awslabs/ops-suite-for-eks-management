from ..lib.basestep import BaseStep
from ..lib.ekshelper import EKSHelper
from ..lib.inputcluster import InputCluster
from ..lib.nodegroup import NodeGroup, get_node_group_content
from ..lib.processhelper import ProcessHelper
from ..lib.wfutils import ExecutionUtility, FileUtility, Progress
from .constants import (
    DEFAULT_STEP_NAME,
    LOG_FOLDER,
    NODE_GROUPS_UPGRADE_STEP,
    S3_FOLDER_NAME,
)


class ManagedNodeGroup(NodeGroup):

    def __init__(
        self,
        region: str,
        cluster: str,
        node_name: str,
        desired_eks_version: str,
        script_file: str,
    ):

        super().__init__("Managed", region, cluster, node_name, desired_eks_version)

        self.process_helper = ProcessHelper(calling_module=NODE_GROUPS_UPGRADE_STEP)

        self.script_file = script_file

    def update_node(self, progress: Progress) -> dict:

        self.logger.info(f"Updating {self.node_name} in {self.cluster}")

        command_arguments: list[str] = [
            "-c",
            self.cluster,
            "-r",
            self.region,
            "-e",
            self.desired_eks_version,
            "-g",
            self.node_name,
        ]

        resp = self.process_helper.run_shell(
            script_file=self.script_file, arguments=command_arguments
        )

        if resp == 0:
            progress.updated_increment()
            self.logger.info(
                f"Updating {self.cluster}.{self.node_name} to the desired version "
                f"{self.desired_eks_version} is success"
            )
            return get_node_group_content(
                name=self.node_name,
                status="Success",
                desired_version=self.desired_eks_version,
                message="Updated",
            )

        else:
            progress.failed_increment()
            self.logger.error(
                f"Update script failed while updating {self.cluster}.{self.node_name} "
                f"to the desired version {self.desired_eks_version}"
            )
            return get_node_group_content(
                name=self.node_name,
                status="Failure",
                desired_version=self.desired_eks_version,
                message="Update nodegroup script failed",
            )


class NodesUpgradeStep(BaseStep):
    eks_helper: EKSHelper = None

    def __init__(self):
        super().__init__(
            step_name=NODE_GROUPS_UPGRADE_STEP,
            s3_folder=S3_FOLDER_NAME,
            log_prefix=LOG_FOLDER,
        )
        self.eks_helper = EKSHelper(
            region=self.region, calling_module=NODE_GROUPS_UPGRADE_STEP
        )

    def run(self, input_cluster: InputCluster = None):

        cluster = input_cluster.cluster
        options = input_cluster.upgrade_options
        desired_eks_version = options.desired_eks_version

        addon_csv_file = self.csv_report_file(
            cluster=cluster, report_name=NODE_GROUPS_UPGRADE_STEP
        )

        try:

            node_groups = self.eks_helper.list_node_groups(cluster)
            progress: Progress = Progress()

            total_node_groups = len(node_groups)

            if total_node_groups == 0:
                self.logger.info(f"{cluster} does not have any managed node groups")
                self.populate_existing_report(
                    cluster=cluster,
                    total_node_groups=total_node_groups,
                    message="No managed node groups found. ",
                    progress=progress,
                )

                headers = ["Id", "Name", "DesiredVersion", "UpdateStatus", "Message"]
                dummy_row = [1, None, None, None, "No NodeGroups present"]
                FileUtility.write_csv_headers(addon_csv_file, headers, dummy_row)

            else:
                node_group_report = []

                script_file = (
                    f"{self.bash_scripts_path()}/update_managed_node_groups.sh"
                )

                for node in node_groups:
                    node_details = self.eks_helper.get_node_group_details(
                        cluster_name=cluster, node_group_name=node
                    )
                    node_group = ManagedNodeGroup(
                        region=self.region,
                        cluster=cluster,
                        node_name=node,
                        desired_eks_version=desired_eks_version,
                        script_file=script_file,
                    )
                    response = node_group.update(node_details, progress)
                    node_group_report.append(response)

                FileUtility.write_csv(addon_csv_file, node_group_report)

                self.populate_existing_report(
                    cluster=cluster,
                    total_node_groups=total_node_groups,
                    message=f"Node groups updated:- {progress.updated}; "
                    f"Check nodegroupsupdate table for more details.",
                    progress=progress,
                )

        except Exception as e:
            self.logger.error(
                f"Updating managed node groups for {cluster} failed with exception: {e}"
            )
            ExecutionUtility.stop()

        finally:
            self.logger.info(f"Uploading node group reports for {cluster}")
            self.upload_reports(cluster=cluster, report_name=NODE_GROUPS_UPGRADE_STEP)

    def populate_existing_report(
        self, cluster: str, total_node_groups: int, progress: Progress, message: str
    ) -> None:

        json_file = self.base_report(cluster=cluster, name=DEFAULT_STEP_NAME)
        existing_report = FileUtility.read_json_file(json_file)

        existing_report["TotalNodeGroups"] = total_node_groups
        existing_report["NodeGroupsUpdated"] = progress.updated
        existing_report["NodeGroupsFailed"] = progress.failed
        existing_report["NodeGroupsRunningDesired"] = progress.no_action
        existing_report["NodeGroupsNotActive"] = progress.not_active
        existing_report["Message"] = f"{existing_report['Message']} " f"{message} "

        FileUtility.write_json(json_file, existing_report)


if __name__ == "__main__":
    nodes_upgrade_step = NodesUpgradeStep()
    nodes_upgrade_step.start(
        name=NODE_GROUPS_UPGRADE_STEP,
        report_name=DEFAULT_STEP_NAME,
        for_each_cluster=True,
        filter_input_clusters=True,
        input_clusters_required=True,
        check_cluster_status=True,
    )
