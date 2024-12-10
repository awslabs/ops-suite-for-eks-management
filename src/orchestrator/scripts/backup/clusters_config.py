from ..lib.baseconfig import BaseClustersConfig
from .constants import CLUSTERS_CONFIG, LOG_FOLDER


class ClustersConfig(BaseClustersConfig):

    def __init__(self):
        super().__init__(config_name=CLUSTERS_CONFIG, log_prefix=LOG_FOLDER)


if __name__ == "__main__":
    clusters_config = ClustersConfig()
    clusters_config.start(for_each_cluster=False)
