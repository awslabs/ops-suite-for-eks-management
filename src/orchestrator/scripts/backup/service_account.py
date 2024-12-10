from kubernetes import client

from ..lib.basestep import BaseStep
from ..lib.iamhelper import IAMHelper
from ..lib.inputcluster import BackupOptions, InputCluster
from ..lib.processhelper import ProcessHelper
from ..lib.wfutils import ExecutionUtility, FileUtility
from .constants import (
    DEFAULT_STEP_NAME,
    LOG_FOLDER,
    S3_FOLDER_NAME,
    SERVICE_ACCOUNT_STEP,
)


class ServiceAccountStep(BaseStep):
    iam_helper: IAMHelper = None

    def __init__(self):
        super().__init__(
            step_name=SERVICE_ACCOUNT_STEP,
            s3_folder=S3_FOLDER_NAME,
            log_prefix=LOG_FOLDER,
        )

        self.iam_helper = IAMHelper(calling_module=SERVICE_ACCOUNT_STEP)
        self.process_helper = ProcessHelper(calling_module=SERVICE_ACCOUNT_STEP)

    def run(self, input_cluster: InputCluster = None):
        cluster = input_cluster.cluster
        service_account = input_cluster.backup_options.service_account
        json_file = self.json_report_file(
            cluster=cluster, report_name=DEFAULT_STEP_NAME
        )

        try:
            if input_cluster.is_restore():
                message = f"Backup action is not present in input for {cluster}."
                self.logger.info(message)
                report = dict(
                    ServiceAccount=service_account,
                    ServiceAccountStatus="No Action",
                    Message=message,
                )

                FileUtility.write_json(json_file, report)

            else:
                self.logger.info(f"Action is backup for {cluster}")

                options = input_cluster.backup_options

                core_api = self.kube_core_api_client(cluster)

                self.check_and_create_namespace(cluster, options, core_api)

                service_accounts = core_api.list_namespaced_service_account(
                    options.velero_namespace
                )

                if len(service_accounts.items) == 0:
                    self.logger.info(
                        f"No service accounts present for {cluster}. Creating one for velero.."
                    )
                    self.create_service_account(cluster, options, json_file)

                else:
                    service_account_present = False
                    accounts = service_accounts.items
                    for account in accounts:
                        if account.metadata.name == options.service_account:
                            service_account_present = True
                            break

                    if not service_account_present:
                        self.logger.info(
                            f"Velero service account not present for {cluster}. Creating.."
                        )
                        self.create_service_account(cluster, options, json_file)

                    else:
                        self.logger.info(
                            f"Velero service account already present for {cluster}."
                        )
                        report = dict(
                            ServiceAccount=service_account,
                            ServiceAccountStatus="Already present",
                            Message="Service Account already created",
                        )

                        FileUtility.write_json(json_file, report)

        except Exception as e:
            self.logger.error(
                f"Error while creating service account for {cluster}: {e}"
            )
            ExecutionUtility.stop()

    def check_and_create_namespace(
        self, cluster: str, options: BackupOptions, core_api: client.CoreV1Api
    ):
        namespaces = core_api.list_namespace()

        velero_namespace_present = False
        for namespace in namespaces.items:
            if options.velero_namespace == namespace.metadata.name:
                velero_namespace_present = True
                break

        if velero_namespace_present:
            self.logger.info(
                f"{options.velero_namespace} namespace already present in {cluster}"
            )
        else:
            self.logger.info(
                f"{options.velero_namespace} namespace not present in {cluster}. Creating..."
            )
            body = client.V1Namespace(
                metadata=client.V1ObjectMeta(name=options.velero_namespace)
            )
            core_api.create_namespace(body)
            self.logger.info(
                f"{options.velero_namespace} namespace created in {cluster}."
            )

    def create_service_account(
        self, cluster: str, options: BackupOptions, json_file: str
    ):
        role_name = options.service_account_role_name
        service_account = options.service_account

        trust_policy_file = (
            f"{self.working_directory}/config/{cluster}-trust-relationship.json"
        )

        self.iam_helper.create_role(role_name, trust_policy_file)
        self.iam_helper.put_role_policy(role_name, self.get_backup_bucket_name())

        role_arn = f"arn:aws:iam::{self.account_id}:role/{role_name}"

        script_file = f"{self.bash_scripts_path()}/create_service_account.sh"

        command_arguments: list[str] = [
            self.working_directory,
            cluster,
            service_account,
            options.velero_namespace,
            role_arn,
        ]

        resp = self.process_helper.run_shell(
            script_file=script_file, arguments=command_arguments
        )

        failure_status = False
        if resp == 0:
            self.logger.info(
                f"Service Account resource created by the script for {cluster}"
            )
            content = dict(
                ServiceAccount=service_account,
                ServiceAccountStatus="Created",
                Message="Service Account created",
            )

        else:
            self.logger.error(
                f"Service Account resource creation script failed for {cluster}"
            )
            content = dict(
                ServiceAccount=service_account,
                ServiceAccountStatus="Failed",
                Message="Service Account creation failed",
            )
            failure_status = True

        FileUtility.write_json(json_file, content)

        if failure_status:
            self.logger.error(
                f"Service Account creation failed for {cluster}. Exiting.."
            )
            ExecutionUtility.stop()


if __name__ == "__main__":
    service_account_step = ServiceAccountStep()
    service_account_step.start(
        name=SERVICE_ACCOUNT_STEP,
        report_name=DEFAULT_STEP_NAME,
        for_each_cluster=True,
        filter_input_clusters=True,
        input_clusters_required=True,
        check_cluster_status=False,
    )
