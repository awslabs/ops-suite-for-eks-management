import yaml

from ..lib.baseconfig import BaseConfig
from ..lib.inputcluster import BackupOptions, InputCluster
from .constants import LOG_FOLDER, SERVICE_ACCOUNT_CONFIG, SERVICE_ACCOUNT_FILE_NAME


class ServiceAccountConfig(BaseConfig):

    def __init__(self):
        super().__init__(config_name=SERVICE_ACCOUNT_CONFIG, log_prefix=LOG_FOLDER)

    def run(self, input_cluster: InputCluster = None):
        cluster: str = input_cluster.cluster

        if input_cluster.is_restore():
            self.logger.info(
                f"Skipping this step since the action is restore {cluster}"
            )
            return

        self.logger.info("Creating YAML for service account")

        yaml_content = self.generate_service_account_yaml(input_cluster)
        self.logger.info(f"YAMl File: {yaml_content}")

        file_name = f"{SERVICE_ACCOUNT_FILE_NAME}-{cluster}"
        self.write_config_yaml(yaml_content, file_name)

    @staticmethod
    def generate_service_account_yaml(input_cluster: InputCluster):
        options: BackupOptions = input_cluster.backup_options
        service_account_yaml = {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {
                "name": options.service_account,
                "namespace": options.velero_namespace,
            },
        }

        return yaml.dump(service_account_yaml, default_flow_style=False)


if __name__ == "__main__":
    service_account_config = ServiceAccountConfig()
    service_account_config.start(
        for_each_cluster=True, filter_input_clusters=True, input_clusters_required=True
    )
