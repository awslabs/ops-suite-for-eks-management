from ..lib.baseconfig import FilterClustersConfig
from .constants import FILTER_CLUSTERS_CONFIG, LOG_FOLDER


class ClustersConfig(FilterClustersConfig):

    def __init__(self):
        super().__init__(config_name=FILTER_CLUSTERS_CONFIG, log_prefix=LOG_FOLDER)


if __name__ == "__main__":
    clusters_config = ClustersConfig()
    clusters_config.start()
