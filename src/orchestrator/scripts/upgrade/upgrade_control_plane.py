from ..lib.basestep import BaseStep
from ..lib.ekshelper import MIN_KUBERNETES_MINOR_VERSION, EKSHelper
from ..lib.inputcluster import InputCluster
from ..lib.processhelper import ProcessHelper
from ..lib.wfutils import ExecutionUtility, FileUtility
from .constants import (
    CONTROL_PLANE_UPGRADE_STEP,
    DEFAULT_STEP_NAME,
    LOG_FOLDER,
    S3_FOLDER_NAME,
)


class ControlPlaneUpdateStep(BaseStep):
    eks_helper: EKSHelper = None

    def __init__(self):
        super().__init__(
            step_name=CONTROL_PLANE_UPGRADE_STEP,
            s3_folder=S3_FOLDER_NAME,
            log_prefix=LOG_FOLDER,
        )
        self.eks_helper = EKSHelper(
            region=self.region, calling_module=CONTROL_PLANE_UPGRADE_STEP
        )
        self.process_helper = ProcessHelper(calling_module=CONTROL_PLANE_UPGRADE_STEP)

    def run(self, input_cluster: InputCluster = None):

        cluster = input_cluster.cluster
        options = input_cluster.upgrade_options

        json_file = self.base_report(cluster=cluster, name=DEFAULT_STEP_NAME)
        existing_report = FileUtility.read_json_file(json_file)

        eks_details = self.eks_helper.get_eks_cluster_details(cluster)
        eks_version = eks_details.get("version")

        try:

            script_file = f"{self.bash_scripts_path()}/upgrade_version.sh"
            kube_config_path = self.kube_config_path(cluster)

            desired_version = options.desired_eks_version

            failure_status = False

            if eks_version == desired_version:

                self.logger.info(
                    f"{cluster} already running the desired version {desired_version}"
                )
                existing_report["ClusterUpdateStatus"] = "No Action"
                existing_report["Message"] = (
                    f"Cluster already running {desired_version}"
                )

            elif not self.is_version_upgradable(eks_version, desired_version):

                self.logger.info(f"{cluster} cannot be upgraded to {desired_version}")
                existing_report["ClusterUpdateStatus"] = "Not supported"
                existing_report["Message"] = (
                    f"Upgrading more than one version at a time is not supported."
                )

                # Exiting from the execution
                failure_status = True

            else:

                self.logger.info(
                    f"Updating {cluster} with version {eks_version} to the desired version {desired_version}"
                )

                command_arguments: list[str] = [
                    "-p",
                    kube_config_path,
                    "-c",
                    cluster,
                    "-r",
                    self.region,
                    "-v",
                    eks_version,
                    "-e",
                    desired_version,
                ]

                resp = self.process_helper.run_shell(
                    script_file=script_file, arguments=command_arguments
                )

                if resp == 0:
                    self.logger.info(
                        f"Updating {cluster} to the desired version {desired_version} is success"
                    )
                    existing_report["ClusterUpdateStatus"] = "Success"
                    existing_report["Message"] = (
                        f"Cluster upgraded to {desired_version}"
                    )

                else:
                    failure_status = True
                    self.logger.error(
                        f"Update script failed while updating {cluster} to the desired version {desired_version}"
                    )

                    existing_report["ClusterUpdateStatus"] = "Failure"
                    existing_report["Message"] = f"Update script failed for {cluster}"

            FileUtility.write_json(json_file, existing_report)

            if failure_status:
                self.logger.error(f"Update failed for {cluster}. Exiting..")
                ExecutionUtility.stop()

        except Exception as e:
            self.logger.error(f"Updating {cluster} failed with exception: {e}")
            ExecutionUtility.stop()

    def is_version_upgradable(self, current_version: str, desired_version: str) -> bool:
        current_version_double = float(current_version)
        desired_version_double = float(desired_version)

        upgradable_version = current_version_double + float(
            MIN_KUBERNETES_MINOR_VERSION
        )

        self.logger.info(
            f"Current version is {current_version}. "
            f"Upgradable version is  {upgradable_version}. "
            f"Desired version is {desired_version}"
        )

        return upgradable_version == desired_version_double


if __name__ == "__main__":
    control_plane_update_step = ControlPlaneUpdateStep()
    control_plane_update_step.start(
        name=CONTROL_PLANE_UPGRADE_STEP,
        report_name=DEFAULT_STEP_NAME,
        for_each_cluster=True,
        filter_input_clusters=True,
        input_clusters_required=True,
        check_cluster_status=True,
    )
