from ..lib.basestep import BaseStep
from ..lib.ekshelper import EKSHelper
from ..lib.inputcluster import InputCluster
from ..lib.processhelper import ProcessHelper
from ..lib.wfutils import ExecutionUtility, FileUtility
from .constants import (
    DEFAULT_STEP_NAME,
    LOG_FOLDER,
    RESTART_FARGATE_PROFILES_STEP,
    S3_FOLDER_NAME,
)


class RestartFargateProfilesStep(BaseStep):
    eks_helper: EKSHelper = None

    def __init__(self):
        super().__init__(
            step_name=RESTART_FARGATE_PROFILES_STEP,
            s3_folder=S3_FOLDER_NAME,
            log_prefix=LOG_FOLDER,
        )
        self.eks_helper = EKSHelper(
            region=self.region, calling_module=RESTART_FARGATE_PROFILES_STEP
        )
        self.process_helper = ProcessHelper(
            calling_module=RESTART_FARGATE_PROFILES_STEP
        )

    def run(self, input_cluster: InputCluster = None):
        cluster = input_cluster.cluster
        json_file = self.base_report(cluster=cluster, name=DEFAULT_STEP_NAME)
        existing_report = FileUtility.read_json_file(json_file)

        try:

            fargate_profiles = self.eks_helper.list_fargate_profiles(cluster)
            total_fargate_profiles = len(fargate_profiles)

            self.logger.info(
                f"Number of fargate profiles present in cluster: {cluster} is {total_fargate_profiles}"
            )

            restarted_profiles = 0

            if total_fargate_profiles > 0:

                for profile in fargate_profiles:
                    # get namespaces for each profile
                    # for namespacein in fargate_namespaces:
                    # kubectl rollout restart deployment <profile> - n <namespace>
                    pass

            else:
                self.logger.info(f"No fargate profiles present in cluster: {cluster}")

            existing_report["TotalFargateProfiles"] = total_fargate_profiles
            existing_report["Message"] = (
                f"{existing_report['Message']} "
                f"Restarted Fargate profiles: {restarted_profiles}. "
            )

        except Exception as e:
            self.logger.error(
                f"Restarting fargate profiles for {cluster} failed with exception: {e}"
            )
            ExecutionUtility.stop()


if __name__ == "__main__":
    restart_fargate_step = RestartFargateProfilesStep()
    restart_fargate_step.start(
        name=RESTART_FARGATE_PROFILES_STEP,
        report_name=DEFAULT_STEP_NAME,
        for_each_cluster=True,
        filter_input_clusters=True,
        input_clusters_required=True,
        check_cluster_status=True,
    )
