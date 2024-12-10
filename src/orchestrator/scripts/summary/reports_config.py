from ..lib.baseconfig import BaseReportConfig
from .constants import LOG_FOLDER, REPORTS_CONFIG


class CleanupReportsConfig(BaseReportConfig):

    def __init__(self):
        super().__init__(config_name=REPORTS_CONFIG, log_prefix=LOG_FOLDER)


if __name__ == "__main__":
    reports_config = CleanupReportsConfig()
    reports_config.start(
        for_each_cluster=True, filter_input_clusters=True, input_clusters_required=False
    )
