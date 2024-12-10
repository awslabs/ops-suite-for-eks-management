from ..lib.addon import DEFAULT_ADDONS_FOR_UPDATE, MINOR_VERSION_UPDATES, Addon
from ..lib.basestep import BaseStep
from ..lib.ekshelper import EKSHelper
from ..lib.inputcluster import InputCluster
from ..lib.wfutils import ExecutionUtility, FileUtility, Progress
from .constants import (
    ADDONS_UPGRADE_STEP,
    DEFAULT_STEP_NAME,
    LOG_FOLDER,
    S3_FOLDER_NAME,
)


class DefaultVersionAddonUpdate(Addon):

    def __init__(
        self,
        log_name: str,
        eks_helper: EKSHelper,
        region: str,
        cluster: str,
        addon_name: str,
        desired_eks_version: str,
        script_file_path: str,
    ):
        log_name = f"{log_name}.DefaultVersionAddon"
        super().__init__(
            log_name, region, cluster, addon_name, desired_eks_version, script_file_path
        )

        self.eks_helper = eks_helper

    def get_update_version(self, addon_version: str) -> str:
        all_versions: [] = self.eks_helper.get_addon_versions(
            addon_name=self.addon_name, kubernetes_version=self.desired_eks_version
        )

        update_version = self.eks_helper.get_default_addon_version(all_versions)
        self.logger.info(
            f"{self.addon_name} will be updated to {update_version} from {addon_version}"
        )
        return update_version


class MinorVersionAddonUpdate(Addon):

    def __init__(
        self,
        log_name: str,
        eks_helper: EKSHelper,
        region: str,
        cluster: str,
        addon_name: str,
        desired_eks_version: str,
        script_file_path: str,
    ):
        log_name = f"{log_name}.MinorVersionAddon"
        super().__init__(
            log_name, region, cluster, addon_name, desired_eks_version, script_file_path
        )

        self.eks_helper = eks_helper

    def get_update_version(self, addon_version: str) -> str:
        self.logger.info(
            f"Fetching next minor update version for {self.addon_name} running {addon_version}"
        )
        all_versions: [] = self.eks_helper.get_addon_versions(
            addon_name=self.addon_name, kubernetes_version=self.desired_eks_version
        )
        update_version = self.eks_helper.get_next_minor_addon_version(
            addon_version=addon_version, addon_versions=all_versions
        )
        self.logger.info(
            f"{self.addon_name} will be updated to {update_version} from {addon_version}"
        )
        return update_version


class AddonsUpgradeStep(BaseStep):
    eks_helper: EKSHelper = None

    def __init__(self):
        super().__init__(
            step_name=ADDONS_UPGRADE_STEP,
            s3_folder=S3_FOLDER_NAME,
            log_prefix=LOG_FOLDER,
        )
        self.eks_helper = EKSHelper(
            region=self.region, calling_module=ADDONS_UPGRADE_STEP
        )

    def run(self, input_cluster: InputCluster = None):

        cluster = input_cluster.cluster
        options = input_cluster.upgrade_options
        desired_eks_version = options.desired_eks_version

        addon_csv_file = self.csv_report_file(
            cluster=cluster, report_name=ADDONS_UPGRADE_STEP
        )

        try:

            self.logger.info(f"Listing addons for {cluster}")
            addons = self.eks_helper.list_addons(cluster)
            total_addons = len(addons)
            script_file_path = f"{self.bash_scripts_path()}"

            progress: Progress = Progress()

            if total_addons == 0:
                self.logger.info(f"{cluster} does not have addons to update")
                self.populate_existing_report(
                    cluster=cluster,
                    total_addons=total_addons,
                    message=f"Addons not present",
                    progress=progress,
                )

                headers = [
                    "Id",
                    "Name",
                    "Version",
                    "UpdatedVersion",
                    "UpdateStatus",
                    "Message",
                ]
                dummy_row = [1, None, None, None, None, "No Addons present"]
                FileUtility.write_csv_headers(addon_csv_file, headers, dummy_row)

            else:

                addons_to_update = options.addons_to_update
                if addons_to_update is None or len(addons_to_update) == 0:
                    self.logger.info(
                        f"{cluster} does not have addons to update in the input. "
                        f"Defaulting them to {DEFAULT_ADDONS_FOR_UPDATE}"
                    )
                    addons_to_update = DEFAULT_ADDONS_FOR_UPDATE

                addon_report = []

                for addon in addons:
                    addon_detail = self.eks_helper.get_addon_details(
                        cluster_name=cluster, addon_name=addon
                    )

                    if addon in MINOR_VERSION_UPDATES:
                        addon_updater = MinorVersionAddonUpdate(
                            log_name=ADDONS_UPGRADE_STEP,
                            eks_helper=self.eks_helper,
                            region=self.region,
                            cluster=cluster,
                            addon_name=addon,
                            desired_eks_version=desired_eks_version,
                            script_file_path=script_file_path,
                        )
                    else:
                        addon_updater = DefaultVersionAddonUpdate(
                            log_name=ADDONS_UPGRADE_STEP,
                            eks_helper=self.eks_helper,
                            region=self.region,
                            cluster=cluster,
                            addon_name=addon,
                            desired_eks_version=desired_eks_version,
                            script_file_path=script_file_path,
                        )

                    response = addon_updater.update(
                        addon_detail, addons_to_update, progress
                    )
                    addon_report.append(response)

                FileUtility.write_csv(addon_csv_file, addon_report)

                self.populate_existing_report(
                    cluster=cluster,
                    total_addons=total_addons,
                    message=f"Addons updated:- {progress.updated}; "
                    f"Check addonsupdate table",
                    progress=progress,
                )

        except Exception as e:
            self.logger.error(
                f"Updating addons for {cluster} failed with exception: {e}"
            )
            ExecutionUtility.stop()

        finally:
            self.logger.info(f"Uploading addon reports for {cluster}")
            self.upload_reports(cluster=cluster, report_name=ADDONS_UPGRADE_STEP)

    def populate_existing_report(
        self, cluster: str, total_addons: int, progress: Progress, message: str
    ) -> None:

        json_file = self.base_report(cluster=cluster, name=DEFAULT_STEP_NAME)
        existing_report = FileUtility.read_json_file(json_file)

        existing_report["TotalAddons"] = total_addons
        existing_report["AddonsUpgraded"] = progress.updated
        existing_report["AddonsFailed"] = progress.failed
        existing_report["AddonsNotActive"] = progress.not_active
        existing_report["AddonsNotSupported"] = progress.not_supported
        existing_report["AddonsNotInInput"] = progress.not_requested
        existing_report["AddonsRunningLatest"] = progress.no_action
        existing_report["Message"] = f"{existing_report['Message']} " f"{message} "

        FileUtility.write_json(json_file, existing_report)


if __name__ == "__main__":
    addons_upgrade_step = AddonsUpgradeStep()
    addons_upgrade_step.start(
        name=ADDONS_UPGRADE_STEP,
        report_name=DEFAULT_STEP_NAME,
        for_each_cluster=True,
        filter_input_clusters=True,
        input_clusters_required=True,
        check_cluster_status=True,
    )
