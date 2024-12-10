from kubernetes import client
from prettytable import PrettyTable

from ..lib.basestep import BaseStep
from ..lib.inputcluster import InputCluster
from ..lib.wfutils import ExecutionUtility, FileUtility
from .constants import LOG_FOLDER, S3_FOLDER_NAME, UNHEALTHY_PODS_STEP


class UnhealthyPodsStep(BaseStep):

    def __init__(self):
        super().__init__(
            step_name=UNHEALTHY_PODS_STEP,
            s3_folder=S3_FOLDER_NAME,
            log_prefix=LOG_FOLDER,
        )

    def run(self, input_cluster: InputCluster = None):
        cluster = input_cluster.cluster

        csv_report = self.csv_report_file(
            cluster=cluster, report_name=UNHEALTHY_PODS_STEP
        )

        table = PrettyTable()
        table.field_names = ["Namespace", "PodName", "PodStatus", "ErrorReason", "Data"]

        try:
            core_api: client.CoreV1Api = self.kube_core_api_client(cluster)
            namespaces = core_api.list_namespace()

            num_unhealthy_pods = 0
            for namespace in namespaces.items:
                get_name_space = namespace.metadata.name
                pod_list = core_api.list_namespaced_pod(get_name_space).items
                for pod in pod_list:
                    pod_name = pod.metadata.name
                    pod_status = pod.status.phase
                    if pod_status not in ["Running", "Succeeded"]:
                        num_unhealthy_pods += 1
                        try:
                            pod_status_error = pod.status.container_statuses[
                                0
                            ].state.waiting.reason
                        except Exception as e:
                            self.logger.error(
                                f"Exception while fetching pods with waiting status for {cluster}: {e}"
                            )
                            try:
                                pod_status_error = pod.status.container_statuses[
                                    0
                                ].state.terminated.reason
                            except Exception as e:
                                self.logger.error(
                                    f"Exception while fetching pods with terminated status for {cluster}: {e}"
                                )
                                pod_status_error = "unknown"
                        table.add_row(
                            [
                                get_name_space,
                                pod_name,
                                pod_status,
                                pod_status_error,
                                "A",
                            ]
                        )

            self.logger.debug(table)

            table_content = FileUtility.to_dict(table)

            if num_unhealthy_pods != 0:
                # Write back the contents to the file
                FileUtility.write_csv(csv_report, table_content)

            else:
                headers = [
                    "Id",
                    "Namespace",
                    "PodName",
                    "PodStatus",
                    "ErrorReason",
                    "Data",
                ]
                dummy_row = [1, None, None, None, None, "N/A"]
                FileUtility.write_csv_headers(csv_report, headers, dummy_row)

        except Exception as e:
            self.logger.error(f"Error while fetching unhealthy pods for {cluster}: {e}")
            ExecutionUtility.stop()


if __name__ == "__main__":
    unhealthy_pods_step = UnhealthyPodsStep()
    unhealthy_pods_step.start(
        name=UNHEALTHY_PODS_STEP,
        report_name=UNHEALTHY_PODS_STEP,
        for_each_cluster=True,
        filter_input_clusters=True,
        input_clusters_required=False,
        check_cluster_status=False,
    )
