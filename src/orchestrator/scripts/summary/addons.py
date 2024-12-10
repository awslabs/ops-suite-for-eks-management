from ..lib.basestep import BaseStep
from ..lib.ekshelper import EKSHelper
from ..lib.inputcluster import InputCluster
from ..lib.wfutils import ExecutionUtility, FileUtility
from .constants import ADDONS_STEP, LOG_FOLDER, S3_FOLDER_NAME


class Addons(BaseStep):
    eks_helper: EKSHelper = None

    def __init__(self):
        super().__init__(
            step_name=ADDONS_STEP, s3_folder=S3_FOLDER_NAME, log_prefix=LOG_FOLDER
        )

    def run(self, input_cluster: InputCluster = None):
        cluster = input_cluster.cluster
        csv_report = self.csv_report_file(cluster=cluster, report_name=ADDONS_STEP)

        try:
            self.logger.info(f"Listing addons for {cluster}")
            addons = self.eks_helper.list_addons(cluster)
            total_addons = len(addons)

            if total_addons == 0:
                self.logger.info(f"{cluster} does not have addons")
                headers = ["Id", "Name", "Version", "Status", "Data"]
                dummy_row = [1, None, None, None, "N/A"]
                # Write back just the headers to the file
                FileUtility.write_csv_headers(csv_report, headers, dummy_row)
            else:
                addon_content = []
                self.logger.info(f"{cluster} has {len(addons)} addons")
                for addon in addons:
                    addon_detail = self.eks_helper.get_addon_details(
                        cluster_name=cluster, addon_name=addon
                    )
                    addon_version = addon_detail.get("addonVersion")
                    status = addon_detail.get("status", None)
                    report_dict = dict(
                        Name=addon, Version=addon_version, Status=status, Data="A"
                    )
                    addon_content.append(report_dict)

                FileUtility.write_csv(csv_report, addon_content)

        except Exception as e:
            self.logger.error(
                f"Fetching addons for {cluster} failed with exception: {e}"
            )
            ExecutionUtility.stop()


if __name__ == "__main__":
    addons_step = Addons()
    addons_step.start(
        name=ADDONS_STEP,
        report_name=ADDONS_STEP,
        for_each_cluster=True,
        filter_input_clusters=True,
        input_clusters_required=False,
        check_cluster_status=False,
    )
