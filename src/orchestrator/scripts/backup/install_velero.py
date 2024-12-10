from kubernetes import client

from ..lib.basestep import BaseStep
from ..lib.ekshelper import EKSHelper
from ..lib.inputcluster import InputCluster
from ..lib.processhelper import ProcessHelper
from ..lib.wfutils import ExecutionUtility, FileUtility
from .constants import DEFAULT_STEP_NAME, LOG_FOLDER, S3_FOLDER_NAME, VELERO_PLUGIN_STEP


class VeleroPluginInstallStep(BaseStep):
    eks_helper: EKSHelper = None

    def __init__(self):
        super().__init__(
            step_name=VELERO_PLUGIN_STEP,
            s3_folder=S3_FOLDER_NAME,
            log_prefix=LOG_FOLDER,
        )

        self.eks_helper = EKSHelper(
            region=self.region, calling_module=VELERO_PLUGIN_STEP
        )
        self.process_helper = ProcessHelper(calling_module=VELERO_PLUGIN_STEP)

    def run(self, input_cluster: InputCluster = None):
        cluster = input_cluster.cluster
        options = input_cluster.backup_options

        json_file = self.json_report_file(
            cluster=cluster, report_name=DEFAULT_STEP_NAME
        )

        existing_report = FileUtility.read_json_file(json_file)
        velero_namespace = options.velero_namespace
        velero_plugin_version = options.velero_plugin_version

        try:
            if input_cluster.is_restore():
                message = f"Backup action is not present in input for {cluster}."
                self.logger.info(message)

                existing_report["PodStatus"] = "No Action"
                existing_report["Message"] = message

                FileUtility.write_json(json_file, existing_report)

            else:
                failure_status = False

                if (
                    self.eks_helper.fargate_cluster_check(cluster, velero_namespace)
                    == "FAIL"
                ):
                    message = (
                        f"Fargate profile not present for {velero_namespace} namespace."
                    )

                    self.logger.error(message)

                    existing_report["PodStatus"] = "Failure"
                    existing_report["Message"] = message

                    failure_status = True

                else:

                    core_api = self.kube_core_api_client(cluster)
                    existing_pod_list = core_api.list_namespaced_pod(
                        velero_namespace
                    ).items

                    if len(existing_pod_list) == 0:
                        self.logger.info(
                            f"velero pod does not exist in {cluster}. Installing plugin..."
                        )

                        s3_bucket_name = self.get_backup_bucket_name()
                        self.logger.info(f"BackupLocationStorage is {s3_bucket_name}")

                        script_file = (
                            f"{self.bash_scripts_path()}/install_velero_plugin.sh"
                        )
                        kube_config_path = self.kube_config_path(cluster)

                        command_arguments: list[str] = [
                            kube_config_path,
                            velero_namespace,
                            s3_bucket_name,
                            self.region,
                            options.service_account,
                            cluster.lower(),
                            velero_plugin_version,
                        ]

                        resp = self.process_helper.run_shell(
                            script_file=script_file, arguments=command_arguments
                        )

                        if resp == 0:
                            self.logger.info(
                                f"velero plugin installed in {velero_namespace} namespace for cluster {cluster}"
                            )
                            existing_report["PodStatus"] = self.get_velero_pod_status(
                                velero_namespace, core_api
                            )
                            existing_report["Message"] = (
                                "Velero Plugin installation completed"
                            )

                        else:
                            self.logger.info(
                                f"velero plugin installation in {velero_namespace} namespace for cluster {cluster}"
                                f" failed"
                            )
                            existing_report["PodStatus"] = "Failure"
                            existing_report["Message"] = (
                                "Velero Plugin installation failed."
                            )
                            failure_status = True
                    else:
                        existing_report["PodStatus"] = self.get_velero_pod_status(
                            velero_namespace, core_api
                        )
                        existing_report["Message"] = "Velero Plugin already installed"

                FileUtility.write_json(json_file, existing_report)

                if failure_status:
                    self.logger.error(
                        f"Velero plugin installation failed for {cluster}. Exiting.."
                    )
                    ExecutionUtility.stop()

        except Exception as e:
            self.logger.error(f"Error while installing velero plugin on {cluster}: {e}")
            ExecutionUtility.stop()

    def get_velero_pod_status(self, velero_namespace: str, core_api: client.CoreV1Api):
        latest_pod_list = core_api.list_namespaced_pod(velero_namespace).items
        for pod in latest_pod_list:
            pod_name = pod.metadata.name
            pod_status = pod.status.phase
            self.logger.info(
                f"{pod_name} in {velero_namespace} is in {pod_status} state"
            )
            return pod_status


if __name__ == "__main__":
    velero_install_step = VeleroPluginInstallStep()
    velero_install_step.start(
        name=VELERO_PLUGIN_STEP,
        report_name=DEFAULT_STEP_NAME,
        for_each_cluster=True,
        filter_input_clusters=True,
        input_clusters_required=True,
        check_cluster_status=False,
    )
