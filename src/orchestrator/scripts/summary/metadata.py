from ..lib.basestep import BaseStep
from ..lib.inputcluster import InputCluster
from ..lib.processhelper import ProcessHelper
from ..lib.wfutils import ExecutionUtility, FileUtility
from .constants import (
    LOG_FOLDER,
    METADATA_STEP,
    S3_FOLDER_NAME,
    WORKER_NODE_METADATA_STEP,
)


class MetadataStep(BaseStep):

    def __init__(self):
        super().__init__(
            step_name=METADATA_STEP, log_prefix=LOG_FOLDER, s3_folder=S3_FOLDER_NAME
        )
        self.process_helper = ProcessHelper(calling_module=METADATA_STEP)

    def run(self, input_cluster: InputCluster = None):
        cluster = input_cluster.cluster

        # Invoke metadata script
        script_file = f"{self.bash_scripts_path()}/metadata.sh"
        metadata_json_report = self.json_report_file(
            cluster=cluster, report_name=METADATA_STEP
        )

        command_arguments: list[str] = [
            self.working_directory,
            cluster,
            metadata_json_report,
        ]

        resp = self.process_helper.run_shell(
            script_file=script_file, arguments=command_arguments
        )

        if resp == 0:

            self.logger.info(f"{script_file} successfully executed for {cluster}")

            # Create report directory and file for workerNodes
            worker_nodes_csv_report = self.csv_report_file(
                cluster=cluster, report_name=WORKER_NODE_METADATA_STEP
            )

            # Format the json file
            file_content = FileUtility.read_json_file(metadata_json_report)

            file_content["AddonDetails"] = self.get_addon_details(
                cluster, file_content["AddonDetails"]
            )
            nodes_list = self.get_worker_nodes(cluster, file_content["WorkerNodes"])
            del file_content["WorkerNodes"]

            if nodes_list is not None:
                # Attach Data key
                for d in nodes_list:
                    d["Data"] = "A"
                # Write back the contents to the csv
                FileUtility.write_csv(worker_nodes_csv_report, nodes_list)
            else:
                headers = ["Id", "Name", "KubeletVersion", "Data"]
                dummy_row = [1, None, None, "N/A"]
                FileUtility.write_csv_headers(
                    worker_nodes_csv_report, headers, dummy_row
                )

            # Write back the contents to the file
            FileUtility.write_flatten_json(metadata_json_report, file_content)

            self.logger.info(f"{metadata_json_report} generated for {cluster}")
            self.logger.info(f"{worker_nodes_csv_report} generated for {cluster}")

            # Upload reports to S3
            self.logger.info(f"Uploading {WORKER_NODE_METADATA_STEP} reports to S3")
            self.upload_reports(cluster=cluster, report_name=WORKER_NODE_METADATA_STEP)

        else:
            self.logger.error(f"Invoking {script_file} failed for {cluster}.")
            ExecutionUtility.stop()

    def get_worker_nodes(self, cluster: str, worker_nodes_str: str) -> []:
        if len(worker_nodes_str) == 0:
            self.logger.warning(f"Worker nodes string is empty {cluster}")
            return None

        worker_nodes_array = worker_nodes_str.split(";")

        if len(worker_nodes_array) == 0:
            self.logger.warning(f"No worker nodes present for {cluster}")
            return None

        worker_nodes = []

        for node in worker_nodes_array:

            if len(node) != 0:
                worker_node_array = node.split("|")

                worker_node = dict(
                    Name=worker_node_array[0], KubeletVersion=worker_node_array[1]
                )
                worker_nodes.append(worker_node)

        self.logger.debug(f"Worker node details for {cluster}: {worker_nodes}")
        return worker_nodes

    def get_addon_details(self, cluster: str, addon_details: dict) -> dict:
        formatted_addon_details = dict()

        core_dns_details = addon_details["CoreDns"]
        if len(core_dns_details) != 0:
            core_dns_array = core_dns_details.split("|")
            formatted_addon_details["CoreDns"] = dict(Details=core_dns_array[1])
        else:
            self.logger.warning(f"No CoreDns AddOn present for {cluster}")
            formatted_addon_details["CoreDns"] = dict(Details=None)

        kube_proxy_details = addon_details["KubeProxy"]
        if len(kube_proxy_details) != 0:
            kube_proxy_array = kube_proxy_details.split("|")
            formatted_addon_details["KubeProxy"] = dict(Details=kube_proxy_array[1])
        else:
            self.logger.warning(f"No KubeProxy AddOn present for {cluster}")
            formatted_addon_details["KubeProxy"] = dict(Details=None)

        aws_node_details = addon_details["AWSNode"]
        if len(aws_node_details) != 0:
            aws_node_array = aws_node_details.split("|")
            formatted_addon_details["AWSNode"] = dict(Details=aws_node_array[1])
        else:
            self.logger.warning(f"No AWSNode AddOn present for {cluster}")
            formatted_addon_details["AWSNode"] = dict(Details=None)

        self.logger.debug(f"Addon Details for {cluster}: {formatted_addon_details}")
        return formatted_addon_details


if __name__ == "__main__":
    metadata_step = MetadataStep()
    metadata_step.start(
        name=METADATA_STEP,
        report_name=METADATA_STEP,
        for_each_cluster=True,
        filter_input_clusters=True,
        input_clusters_required=False,
        check_cluster_status=False,
    )
