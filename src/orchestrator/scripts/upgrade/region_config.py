from ..lib.baseconfig import BaseRegionConfig
from .constants import LOG_FOLDER, REGION_CONFIG


class RegionConfig(BaseRegionConfig):
    def __init__(self):
        super().__init__(
            config_name=REGION_CONFIG, need_region=False, log_prefix=LOG_FOLDER
        )


if __name__ == "__main__":
    region_config = RegionConfig()
    region_config.start(for_each_cluster=False)
