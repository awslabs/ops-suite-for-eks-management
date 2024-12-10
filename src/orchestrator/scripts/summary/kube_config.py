from ..lib.baseconfig import BaseKubeConfig
from .constants import KUBE_CONFIG, LOG_FOLDER


class KubeConfig(BaseKubeConfig):
    def __init__(self):
        super().__init__(config_name=KUBE_CONFIG, log_prefix=LOG_FOLDER)


if __name__ == "__main__":
    kube_config = KubeConfig()
    kube_config.start(
        for_each_cluster=True, filter_input_clusters=True, input_clusters_required=False
    )
