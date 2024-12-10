from ..lib.basestep import BaseStep
from ..lib.ekshelper import EKSHelper
from ..lib.inputcluster import InputCluster
from ..lib.wfutils import ExecutionUtility, FileUtility
from .constants import DEFAULT_STEP_NAME, LOG_FOLDER, POST_UPGRADE_STEP, S3_FOLDER_NAME


def get_csv_content(
    current_eks_version: str,
    resource_type: str,
    name: str,
    current_version: str,
    status: str,
    message: str,
) -> dict:
    return dict(
        CurrentClusterVersion=current_eks_version,
        Type=resource_type,
        Name=name,
        CurrentVersion=current_version,
        Status=status,
        Message=message,
    )


class PostUpdateStep(BaseStep):
    eks_helper: EKSHelper = None

    def __init__(self):
        super().__init__(
            step_name=POST_UPGRADE_STEP, s3_folder=S3_FOLDER_NAME, log_prefix=LOG_FOLDER
        )
        self.eks_helper = EKSHelper(
            region=self.region, calling_module=POST_UPGRADE_STEP
        )

    def run(self, input_cluster: InputCluster = None):

        cluster = input_cluster.cluster
        options = input_cluster.upgrade_options

        desired_eks_version = options.desired_eks_version
        json_file = self.base_report(cluster=cluster, name=DEFAULT_STEP_NAME)
        post_update_csv_file = self.csv_report_file(
            cluster=cluster, report_name=POST_UPGRADE_STEP
        )

        existing_report = FileUtility.read_json_file(json_file)
        try:

            eks_details = self.eks_helper.get_eks_cluster_details(cluster)
            current_eks_version = eks_details.get("version")
            existing_report["PostUpgradeClusterVersion"] = current_eks_version

            post_update_report = []

            node_group_content = self.get_node_group_details(
                current_eks_version, cluster, desired_eks_version
            )
            post_update_report.extend(node_group_content)

            addon_content = self.get_addon_details(
                current_eks_version, cluster, desired_eks_version
            )
            post_update_report.extend(addon_content)

            FileUtility.write_csv(post_update_csv_file, post_update_report)

            FileUtility.write_json(json_file, existing_report)

        except Exception as e:
            self.logger.error(
                f"Generating post update reports for {cluster} failed with exception: {e}"
            )
            ExecutionUtility.stop()

        finally:
            self.logger.info(f"Uploading post-update reports for {cluster}")
            self.upload_reports(cluster=cluster, report_name=POST_UPGRADE_STEP)

    def get_node_group_details(
        self, cluster_version: str, cluster: str, desired_eks_version: str
    ) -> []:
        self.logger.info(f"Fetching node groups for {cluster}")
        node_groups = self.eks_helper.list_node_groups(cluster)

        if len(node_groups) == 0:
            return [
                get_csv_content(
                    current_eks_version=cluster_version,
                    resource_type="NodeGroup",
                    name="N/A",
                    current_version="N/A",
                    status="N/A",
                    message="No NodeGroups present",
                )
            ]

        node_group_content = []
        for node in node_groups:
            node_detail = self.eks_helper.get_node_group_details(
                cluster_name=cluster, node_group_name=node
            )
            current_version = node_detail.get("version")
            if current_version == desired_eks_version:
                message = "Desired EKS Version running"
            else:
                message = "NodeGroup is not on the desired EKS version"

            content = get_csv_content(
                current_eks_version=cluster_version,
                resource_type="NodeGroup",
                name=node,
                current_version=current_version,
                status=node_detail.get("status"),
                message=message,
            )
            node_group_content.append(content)

        return node_group_content

    def get_addon_details(
        self, cluster_version: str, cluster: str, desired_eks_version: str
    ) -> []:
        self.logger.info(f"Fetching addons for {cluster}")
        addons = self.eks_helper.list_addons(cluster_name=cluster)

        if len(addons) == 0:
            return [
                get_csv_content(
                    current_eks_version=cluster_version,
                    resource_type="Addon",
                    name="N/A",
                    current_version="N/A",
                    status="N/A",
                    message="No Addons present",
                )
            ]

        addon_content = []

        for addon in addons:

            addon_details = self.eks_helper.get_addon_details(
                cluster_name=cluster, addon_name=addon
            )
            current_version = addon_details.get("addonVersion")
            version_list = self.eks_helper.get_addon_versions(
                addon_name=addon, kubernetes_version=desired_eks_version
            )
            default_version = self.eks_helper.get_default_addon_version(version_list)

            if current_version == default_version:
                message = "Default Version is being used"
            else:
                message = f"Addon is not on the default version for Kubernetes version {desired_eks_version}"

            content = get_csv_content(
                current_eks_version=cluster_version,
                resource_type="Addon",
                name=addon,
                current_version=current_version,
                status=addon_details.get("status"),
                message=message,
            )
            addon_content.append(content)

        return addon_content


if __name__ == "__main__":
    post_update_step = PostUpdateStep()
    post_update_step.start(
        name=POST_UPGRADE_STEP,
        report_name=DEFAULT_STEP_NAME,
        for_each_cluster=True,
        filter_input_clusters=True,
        input_clusters_required=True,
        check_cluster_status=True,
    )
