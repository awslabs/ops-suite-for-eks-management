import os
from datetime import datetime

from ..lib.basestep import BaseStep
from ..lib.ekshelper import EKSHelper
from ..lib.inputcluster import InputCluster
from ..lib.processhelper import ProcessHelper
from ..lib.wfutils import ExecutionUtility, FileUtility
from .constants import DEFAULT_STEP_NAME, LOG_FOLDER, S3_FOLDER_NAME, VELERO_BACKUP_STEP


class VeleroBackupStep(BaseStep):
    eks_helper: EKSHelper = None

    def __init__(self):
        super().__init__(
            step_name=VELERO_BACKUP_STEP,
            s3_folder=S3_FOLDER_NAME,
            log_prefix=LOG_FOLDER,
        )

        self.eks_helper = EKSHelper(
            region=self.region, calling_module=VELERO_BACKUP_STEP
        )
        self.process_helper = ProcessHelper(calling_module=VELERO_BACKUP_STEP)

    def run(self, input_cluster: InputCluster = None):
        self.logger.info(f"Cluster details provided : {input_cluster}")

        cluster = input_cluster.cluster

        options = input_cluster.backup_options
        velero_namespace = options.velero_namespace
        backup_name = self.get_backup_name(input_cluster)

        json_file = self.json_report_file(
            cluster=cluster, report_name=DEFAULT_STEP_NAME
        )

        existing_report = FileUtility.read_json_file(json_file)

        try:
            failure_status = False

            eks_version = self.eks_helper.get_eks_cluster_details(cluster).get(
                "version"
            )

            self.logger.info(f"Cluster EKS Version: {eks_version}")

            if input_cluster.is_backup():

                if (
                    self.eks_helper.fargate_cluster_check(cluster, velero_namespace)
                    == "FAIL"
                ):

                    message = (
                        f"Fargate profile not present for {velero_namespace} namespace. "
                        f"Velero plugin may not be installed."
                    )

                    self.logger.error(message)

                    existing_report["BackupStatus"] = "Failure"
                    existing_report["BackupName"] = backup_name
                    existing_report["BackupLocation"] = "N/A"
                    existing_report["ClusterVersion"] = eks_version
                    existing_report["Message"] = message

                    failure_status = True

                else:

                    script_file = f"{self.bash_scripts_path()}/create_backup.sh"
                    status_json_file = f"{self.get_reporting_directory(cluster, DEFAULT_STEP_NAME)}/backup_status.json"

                    kube_config_path = self.kube_config_path(cluster)
                    self.logger.info(
                        f"Kube config file:- {kube_config_path} and backup name:- {backup_name}"
                    )

                    additional_args: list[str] = self.get_arguments(
                        options.velero_arguments
                    )
                    self.logger.info(f"Additional args to velero: {additional_args}")

                    command_arguments: list[str] = [
                        kube_config_path,
                        cluster,
                        backup_name,
                        status_json_file,
                        velero_namespace,
                    ]

                    command_arguments.extend(additional_args)

                    resp = self.process_helper.run_shell(
                        script_file=script_file, arguments=command_arguments
                    )
                    self.logger.info(f"Backup shell response for {cluster}: {resp}")
                    if resp == 0:

                        status_json = FileUtility.read_json_file(status_json_file)

                        self.logger.info(
                            f"Backup creation response for {cluster}: {status_json}"
                        )

                        status = status_json.get("phase", "Failure")

                        self.logger.info(
                            f"Backup creation status for {cluster}: {status}"
                        )

                        if status != "Completed":

                            message = (
                                f"Backup creation not completed. "
                                f"Check the logs using kubectl logs deploy/velero -n {velero_namespace}."
                            )

                            self.logger.error(message)

                            existing_report["BackupStatus"] = status
                            existing_report["BackupName"] = backup_name
                            existing_report["BackupLocation"] = "N/A"
                            existing_report["ClusterVersion"] = eks_version
                            existing_report["Message"] = message

                            failure_status = True

                        else:

                            s3_backup_location = self.get_backup_bucket_name()
                            backup_location = (
                                f"{s3_backup_location}/{cluster}/backups/{backup_name}"
                            )

                            message = "Backup creation completed. Check the BackupLocation: {backup_location} "
                            self.logger.info(message)

                            existing_report["BackupStatus"] = status
                            existing_report["BackupName"] = backup_name
                            existing_report["BackupLocation"] = backup_location
                            existing_report["ClusterVersion"] = eks_version
                            existing_report["Message"] = message

                    else:

                        message = "Backup creation script failed"
                        self.logger.error(message)

                        existing_report["BackupStatus"] = "Failed"
                        existing_report["BackupName"] = backup_name
                        existing_report["BackupLocation"] = "N/A"
                        existing_report["ClusterVersion"] = eks_version
                        existing_report["Message"] = message

                        failure_status = True

                    if os.path.isfile(status_json_file):
                        # Remove status json file
                        os.remove(status_json_file)

            else:

                message = f"Backup action is not present in input for {cluster}."
                self.logger.info(message)

                existing_report["BackupStatus"] = "No Action"
                existing_report["BackupName"] = "N/A"
                existing_report["BackupLocation"] = "N/A"
                existing_report["ClusterVersion"] = eks_version
                existing_report["Message"] = message

            FileUtility.write_json(json_file, existing_report)

            if failure_status:
                self.logger.error(f"Velero backup failed for {cluster}. Exiting..")
                ExecutionUtility.stop()

        except Exception as e:
            self.logger.error(f"Error while creating velero backup for {cluster}: {e}")
            ExecutionUtility.stop()

    def get_backup_name(self, input_cluster: InputCluster) -> str:
        cluster = input_cluster.cluster
        options = input_cluster.backup_options
        backup_name = options.backup_name

        if backup_name is None:
            date = datetime.now().date()
            return f"{date}-{self.region}-{cluster}"

        return backup_name.lower()


if __name__ == "__main__":
    velero_backup_step = VeleroBackupStep()
    velero_backup_step.start(
        name=VELERO_BACKUP_STEP,
        report_name=DEFAULT_STEP_NAME,
        for_each_cluster=True,
        filter_input_clusters=True,
        input_clusters_required=True,
        check_cluster_status=False,
    )
