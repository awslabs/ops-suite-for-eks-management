from ..lib.basestep import BaseStep
from ..lib.inputcluster import InputCluster
from ..lib.processhelper import ProcessHelper
from ..lib.wfutils import ExecutionUtility
from .constants import LOG_FOLDER, S3_FOLDER_NAME, TOOLS_UPDATE_STEP


class UpdateToolsStep(BaseStep):

    def __init__(self):
        super().__init__(
            step_name=TOOLS_UPDATE_STEP, s3_folder=S3_FOLDER_NAME, log_prefix=LOG_FOLDER
        )
        self.process_helper = ProcessHelper(TOOLS_UPDATE_STEP)

    def run(self, input_cluster: InputCluster = None):
        try:

            if self.update_tools == "UPDATE":
                self.logger.info("Updating tools")

                script_file = f"{self.bash_scripts_path()}/update_tools.sh"

                resp = self.process_helper.run_shell(script_file, [])

                if resp == 0:
                    self.logger.info(f"Updated kubectl, eksctl")

                else:
                    self.logger.error(f"Failed update kubectl, eksctl")
                    ExecutionUtility.stop()

            else:
                self.logger.info(
                    "Not updating tools. "
                    "To stay update date with Kubernetes versions please consider updating."
                )

        except Exception as e:
            self.logger.error(f"Updating kubectl, eksctl failed: {e}")
            ExecutionUtility.stop()


if __name__ == "__main__":
    tools_update_step = UpdateToolsStep()
    tools_update_step.start(
        name=TOOLS_UPDATE_STEP,
        for_each_cluster=False,
        filter_input_clusters=False,
        input_clusters_required=False,
        check_cluster_status=False,
    )
