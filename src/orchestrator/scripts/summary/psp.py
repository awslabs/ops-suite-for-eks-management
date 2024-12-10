import os

from ..lib.basestep import BaseStep
from ..lib.inputcluster import InputCluster
from ..lib.processhelper import ProcessHelper
from ..lib.wfutils import ExecutionUtility, FileUtility
from .constants import LOG_FOLDER, PSP_STEP, S3_FOLDER_NAME


class PSPStep(BaseStep):

    def __init__(self):
        super().__init__(
            step_name=PSP_STEP, s3_folder=S3_FOLDER_NAME, log_prefix=LOG_FOLDER
        )
        self.process_helper = ProcessHelper(calling_module=PSP_STEP)

    def run(self, input_cluster: InputCluster = None):
        cluster = input_cluster.cluster

        # Invoke psp_check script
        script_file = f"{self.bash_scripts_path()}/psp_check.sh"
        json_report = self.json_report_file(cluster=cluster, report_name=PSP_STEP)
        csv_report = self.csv_report_file(cluster=cluster, report_name=PSP_STEP)

        command_arguments: list[str] = [self.working_directory, cluster, json_report]

        resp = self.process_helper.run_shell(
            script_file=script_file, arguments=command_arguments
        )

        if resp == 0:
            # Format the json file
            file_content = FileUtility.read_json_file(json_report)
            formatted_dict = self.format_json_file(cluster, str(file_content))

            if formatted_dict is not None:
                # Attach Data key
                for d in formatted_dict:
                    d["Data"] = "A"
                # Write back the contents to the file
                FileUtility.write_csv(csv_report, formatted_dict)
            else:
                headers = [
                    "Id",
                    "Name",
                    "FsGroup",
                    "RunAsUser",
                    "SupplementalGroups",
                    "Data",
                ]
                dummy_row = [1, None, None, None, None, "N/A"]
                FileUtility.write_csv_headers(csv_report, headers, dummy_row)

            # Remove the previous json file
            os.remove(json_report)

        else:
            self.logger.error(f"Invoking {script_file} failed for {cluster}.")
            ExecutionUtility.stop()

    def format_json_file(self, cluster: str, content_str: str):
        if len(content_str) != 0:
            psp_array = content_str.split(";")

            if len(psp_array) == 0:
                self.logger.info(f"No Pod Security Policies present for {cluster}")
                return None

            psp_details = []

            for element in psp_array:
                if len(element) != 0:
                    record = element.split("|")
                    psp = dict(
                        Name=record[0],
                        FsGroup=record[1],
                        RunAsUser=record[2],
                        SupplementalGroups=record[3],
                    )

                    psp_details.append(psp)

            return psp_details

        self.logger.info(f"No content present in the PSP report for {cluster}")
        return None


if __name__ == "__main__":
    psp_step = PSPStep()
    psp_step.start(
        name=PSP_STEP,
        report_name=PSP_STEP,
        for_each_cluster=True,
        filter_input_clusters=True,
        input_clusters_required=False,
        check_cluster_status=False,
    )
