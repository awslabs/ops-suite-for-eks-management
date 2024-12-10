from kubernetes import client
from prettytable import PrettyTable

from ..lib.basestep import BaseStep
from ..lib.inputcluster import InputCluster
from ..lib.processhelper import ProcessHelper
from ..lib.wfutils import ExecutionUtility, FileUtility
from .constants import CSR_AUTO_APPROVE, CSR_STEP, LOG_FOLDER, S3_FOLDER_NAME


class CSRStep(BaseStep):

    def __init__(self):
        super().__init__(
            step_name=CSR_STEP, s3_folder=S3_FOLDER_NAME, log_prefix=LOG_FOLDER
        )
        self.process_helper = ProcessHelper(calling_module=CSR_STEP)

    def run(self, input_cluster: InputCluster = None):
        cluster = input_cluster.cluster
        csv_report = self.csv_report_file(cluster=cluster, report_name=CSR_STEP)

        table = PrettyTable()
        table.field_names = ["CSRName", "SignerName", "CurrentStatus", "Data"]

        try:

            cert_api: client.CertificatesV1Api = self.kube_cert_api_client(cluster)
            csr_list = cert_api.list_certificate_signing_request().items

            for csr in csr_list:
                csr_name = csr.metadata.name
                signer_name = csr.spec.signer_name

                if not csr.status.conditions:
                    self.logger.info(f"CSR: {csr_name}  Pending Approval..")

                    if CSR_AUTO_APPROVE:
                        script_file = f"{self.bash_scripts_path()}/csr_approval.sh"
                        kube_config_path = self.kube_config_path(cluster)

                        command_arguments: list[str] = [kube_config_path, csr_name]

                        resp = self.process_helper.run_shell(
                            script_file=script_file, arguments=command_arguments
                        )

                        if resp == 0:
                            self.logger.info(f"CSR: {csr_name}  Now Approved.")
                            table.add_row([csr_name, signer_name, "Approved Now", "A"])
                        else:
                            self.logger.error(f"CSR: {csr_name}  approval failed.")
                            ExecutionUtility.stop()
                    else:
                        table.add_row([csr_name, signer_name, "Pending Approval", "A"])
                elif csr.status.conditions[0].type == "Approved":
                    table.add_row([csr_name, signer_name, "Approved Already", "A"])

            self.logger.debug(table)

            table_content = FileUtility.to_dict(table)

            total_csr = len(table_content)
            if total_csr != 0:
                # Write back the contents to the files
                FileUtility.write_csv(csv_report, table_content)

            else:
                headers = ["Id", "CSRName", "SignerName", "CurrentStatus", "Data"]
                dummy_row = [1, None, None, None, "N/A"]
                # Write back just the headers to the file
                FileUtility.write_csv_headers(csv_report, headers, dummy_row)

        except Exception as e:
            self.logger.error(
                f"Error while fetching Certificate signing requests for {cluster}: {e}"
            )
            ExecutionUtility.stop()


if __name__ == "__main__":
    csr_step = CSRStep()
    csr_step.start(
        name=CSR_STEP,
        report_name=CSR_STEP,
        for_each_cluster=True,
        filter_input_clusters=True,
        input_clusters_required=False,
        check_cluster_status=False,
    )
