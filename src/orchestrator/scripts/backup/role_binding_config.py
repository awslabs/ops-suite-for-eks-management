import yaml

from ..lib.baseconfig import BaseConfig
from ..lib.inputcluster import BackupOptions, InputCluster
from .constants import (
    LOG_FOLDER,
    ROLE_BINDING_CONFIG,
    SERVICE_ACCOUNT_ROLE_BINDING_FILE,
)


class RoleBindingConfig(BaseConfig):

    def __init__(self):
        super().__init__(config_name=ROLE_BINDING_CONFIG, log_prefix=LOG_FOLDER)

    def run(self, input_cluster: InputCluster = None):
        cluster: str = input_cluster.cluster

        if input_cluster.is_restore():
            self.logger.info(
                f"Skipping this step since the action is restore {cluster}"
            )
            return

        self.logger.info(f"Creating YAML for role binding for {cluster}")

        options: BackupOptions = input_cluster.backup_options
        self.logger.info(f"BackupOptions {options}")

        yaml_content = self.generate_role_binding_yaml(input_cluster)
        self.logger.info(f"YAMl File: {yaml_content}")

        file_name = f"{SERVICE_ACCOUNT_ROLE_BINDING_FILE}-{cluster}"
        self.write_config_yaml(yaml_content, file_name)

    @staticmethod
    def generate_role_binding_yaml(input_cluster: InputCluster):
        options: BackupOptions = input_cluster.backup_options
        role_binding_yaml = {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "ClusterRoleBinding",
            "metadata": {"name": options.service_account},
            "roleRef": {
                "apiGroup": "rbac.authorization.k8s.io",
                "kind": "ClusterRole",
                "name": "cluster-admin",
            },
            "subjects": [
                {
                    "kind": "ServiceAccount",
                    "name": options.service_account,
                    "namespace": options.velero_namespace,
                }
            ],
        }

        return yaml.dump(role_binding_yaml, default_flow_style=False)


if __name__ == "__main__":
    role_binding_config = RoleBindingConfig()
    role_binding_config.start(
        for_each_cluster=True, filter_input_clusters=True, input_clusters_required=True
    )
