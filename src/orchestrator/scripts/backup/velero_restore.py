import os

from ..lib.basestep import BaseStep
from ..lib.ekshelper import EKSHelper, ExecutionUtility
from ..lib.inputcluster import InputCluster
from ..lib.processhelper import ProcessHelper
from ..lib.wfutils import FileUtility
from .constants import (
    DEFAULT_STEP_NAME,
    LOG_FOLDER,
    S3_FOLDER_NAME,
    VELERO_RESTORE_STEP,
)


class VeleroRestoreStep(BaseStep):
    eks_helper: EKSHelper = None

    def __init__(self):
        super().__init__(
            step_name=VELERO_RESTORE_STEP,
            s3_folder=S3_FOLDER_NAME,
            log_prefix=LOG_FOLDER,
        )

        self.eks_helper = EKSHelper(
            region=self.region, calling_module=VELERO_RESTORE_STEP
        )
        self.process_helper = ProcessHelper(calling_module=VELERO_RESTORE_STEP)

    def run(self, input_cluster: InputCluster = None):
        self.logger.info(f"Cluster details provided : {input_cluster}")

        cluster = input_cluster.cluster
        options = input_cluster.restore_options
        backup_name = options.backup_name

        json_file = self.json_report_file(
            cluster=cluster, report_name=DEFAULT_STEP_NAME
        )
        existing_report = FileUtility.read_json_file(json_file)

        try:

            failure_status = False

            if input_cluster.is_restore():

                # Velero needs backup names in lower cases
                backup_name = backup_name.lower()

                script_file = f"{self.bash_scripts_path()}/create_restore.sh"
                status_json_file = f"{self.get_reporting_directory(cluster, DEFAULT_STEP_NAME)}/restore_status.json"

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
                ]

                command_arguments.extend(additional_args)

                resp = self.process_helper.run_shell(
                    script_file=script_file, arguments=command_arguments
                )

                if resp == 0:

                    self.logger.info("resp is 0")

                    status_json = FileUtility.read_json_file(status_json_file)
                    self.logger.info(
                        f"Restore creation response for {cluster}: {status_json}"
                    )

                    status_obj = status_json.get("status", {})
                    status = status_obj.get("phase", "Failure")

                    self.logger.info(f"Restore creation status for {cluster}: {status}")

                    s3_backup_location = self.get_backup_bucket_name()
                    existing_report["BackupName"] = backup_name
                    existing_report["RestoreStatus"] = status
                    existing_report["RestoreBackupLocation"] = (
                        f"{s3_backup_location}/{cluster}/backups/{backup_name}"
                    )

                    if status == "Failure":
                        failure_status = True
                        existing_report["Message"] = "Restore creation failed"
                    else:
                        existing_report["Message"] = (
                            f"Cluster restored using {backup_name}"
                        )

                else:

                    message = f"Restore creation script failed for {cluster}"
                    self.logger.error(message)

                    failure_status = True

                    existing_report["RestoreStatus"] = "Failed"
                    existing_report["Message"] = message
                    existing_report["BackupName"] = backup_name
                    existing_report["RestoreBackupLocation"] = "N/A"

                if os.path.isfile(status_json_file):
                    # Remove status json file
                    os.remove(status_json_file)

            else:
                self.logger.info(f"No action required for {cluster}")
                existing_report["RestoreStatus"] = "No Action"
                existing_report["Message"] = "Restore action not present in input."
                existing_report["RestoreBackupLocation"] = "N/A"

            FileUtility.write_json(json_file, existing_report)

            if failure_status:
                self.logger.error(f"Velero restore failed for {cluster}. Exiting..")
                ExecutionUtility.stop()

        except Exception as e:
            self.logger.error(
                f"Error while restoring from velero backup for {cluster}: {e}"
            )
            ExecutionUtility.stop()


if __name__ == "__main__":
    velero_restore_step = VeleroRestoreStep()
    velero_restore_step.start(
        name=VELERO_RESTORE_STEP,
        report_name=DEFAULT_STEP_NAME,
        for_each_cluster=True,
        filter_input_clusters=True,
        input_clusters_required=True,
        check_cluster_status=False,
    )
