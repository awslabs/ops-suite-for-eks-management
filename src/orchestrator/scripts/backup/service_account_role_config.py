from ..lib.baseconfig import CONFIG_FOLDER, BaseConfig
from ..lib.inputcluster import BackupOptions, InputCluster
from ..lib.processhelper import ProcessHelper
from ..lib.wfutils import ExecutionUtility
from .constants import LOG_FOLDER, SERVICE_ACCOUNT_ROLE_CONFIG, TRUST_RELATIONSHIP_FILE


class ServiceAccountRoleConfig(BaseConfig):

    def __init__(self):
        super().__init__(config_name=SERVICE_ACCOUNT_ROLE_CONFIG, log_prefix=LOG_FOLDER)

        self.process_helper = ProcessHelper(SERVICE_ACCOUNT_ROLE_CONFIG)

    def run(self, input_cluster: InputCluster = None):
        cluster: str = input_cluster.cluster

        if input_cluster.is_restore():
            self.logger.info(
                f"Skipping this step since the action is restore {cluster}"
            )
            return

        self.logger.info(f"Generating role trust relationship for {cluster}")

        options: BackupOptions = input_cluster.backup_options
        file_path = f"{self.working_directory}/{CONFIG_FOLDER}/{cluster}-{TRUST_RELATIONSHIP_FILE}"
        script_file = f"{self.bash_scripts_path()}/service_account_config.sh"

        command_arguments: list[str] = [
            cluster,
            self.region,
            options.velero_namespace,
            options.service_account,
            file_path,
        ]

        resp = self.process_helper.run_shell(
            script_file=script_file, arguments=command_arguments
        )

        if resp == 0:
            self.logger.info(
                f"Created Trust Relationship JSON file used while creating Service Account role "
                f"for {cluster}"
            )
        else:
            self.logger.error(
                f"Creating Trust Relationship JSON file failed for {cluster}"
            )
            ExecutionUtility.stop()


if __name__ == "__main__":
    service_account_role_config = ServiceAccountRoleConfig()
    service_account_role_config.start(
        for_each_cluster=True, filter_input_clusters=True, input_clusters_required=True
    )
