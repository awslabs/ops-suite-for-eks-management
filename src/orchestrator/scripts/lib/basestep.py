import logging
import os.path
from datetime import datetime

from kubernetes import client, config

from .automationstep import AutomationStep
from .ekshelper import EKSHelper
from .inputcluster import InputCluster
from .s3helper import S3Helper
from .wfutils import ExecutionUtility, FileUtility

# Constants

"""
Folder name to find the kubernetes config files for the clusters.
"""
KUBE_CONFIG_FOLDER: str = "config"

"""
Folder to find the bash script files
"""
WORKFLOW_BASH_SCRIPTS_FOLDER: str = "bash"

"""
S3 bucket name prefix for velero.
"""
BACKUP_BUCKET_PREFIX: str = "eksmanagement-automation-velero-backup"


class BaseStep(AutomationStep):
    """
    Class which overrides the functions defined in AutomationStep class.
    """

    _all_account_clusters = []

    def __init__(
        self,
        step_name: str,
        s3_folder: str,
        log_prefix: str,
        log_level: int = logging.INFO,
        log_to_file: bool = True,
    ):
        """
        Args:
            step_name: Name of the SSM Automation step
            s3_folder: S3 folder to upload the reports
            log_prefix: Log sub-folder name
            log_level: Log level
            log_to_file: Weather to stream the logs to file
        """

        super().__init__(
            step_name=step_name,
            log_prefix=log_prefix,
            log_level=log_level,
            log_to_file=log_to_file,
            need_region=True,
        )

        self.eks_helper: EKSHelper = EKSHelper(
            region=self.region, calling_module=step_name
        )
        self.s3_helper: S3Helper = S3Helper(calling_module=step_name)

        self.s3_folder = s3_folder
        self._all_account_clusters = self.get_eks_clusters()

    @property
    def all_account_clusters(self) -> []:
        return self._all_account_clusters

    def bash_scripts_path(self) -> str:
        """
        Get the core bash scripts path

        Returns:
            str: Path to the core bash scripts
        """

        return f"{self.working_directory}/{self.script_base_path}/{WORKFLOW_BASH_SCRIPTS_FOLDER}"

    def kube_config_path(self, cluster: str):
        """
        Get a kubernetes config file path

        Args:
            cluster: Name of the EKS Cluster

        Returns:
            str: Path to the kubernetes config file
        """

        return f"{self.working_directory}/{KUBE_CONFIG_FOLDER}/{cluster}"

    def kube_config(self, cluster: str) -> None:
        """
        Configure `config` object of a kubernetes client

        Args:
            cluster: Name of the EKS Cluster

        Returns:
            None
        """

        config_path = self.kube_config_path(cluster)
        config.load_kube_config(config_path)

    def kube_api_client(self, cluster: str) -> client.ApiClient:
        """
        Create an ApiClient object of a kubernetes client.

        Args:
            cluster: Name of the EKS Cluster

        Returns:
            client.ApiClient
        """

        self.kube_config(cluster)
        return client.ApiClient()

    def kube_cert_api_client(self, cluster: str) -> client.CertificatesV1Api:
        """
        Create a CertificatesV1Api object of a kubernetes client.

        Args:
            cluster: Name of the EKS Cluster

        Returns:
            client.CertificatesV1Api
        """

        self.kube_config(cluster)
        return client.CertificatesV1Api()

    def kube_core_api_client(self, cluster: str) -> client.CoreV1Api:
        """
        Create a CoreV1Api object of a kubernetes client.

        Args:
            cluster: Name of the EKS Cluster

        Returns:
            client.CoreV1Api
        """

        self.kube_config(cluster)
        return client.CoreV1Api()

    def kube_apps_api_client(self, cluster: str) -> client.AppsV1Api:
        """
        Create an AppsV1Api object of a kubernetes client.

        Args:
            cluster: Name of the EKS Cluster

        Returns:
            client.AppsV1Api
        """

        return client.AppsV1Api(self.kube_api_client(cluster))

    def get_backup_bucket_name(self) -> str:
        """
        Get the name of the S3 backup bucket

        Returns:
            str: Backup S3 bucket name used by velero to store backup files.
        """
        prefix: str = (
            self.storage_bucket_prefix()
            if self.storage_bucket_prefix()
            else BACKUP_BUCKET_PREFIX
        )
        return f"{prefix}-{self.account_id}-{self.region}"

    @staticmethod
    def upload_to_s3(prefix_key: str, file_path: str) -> int:
        """
        Upload files recursively to the S3 bucket.

        Args:
            prefix_key: S3 prefix
            file_path: File path to copy.

        Returns:
            int: Status of the command
        """

        # return os.system(
        #    f'aws s3 cp {file_path} s3://{self.s3_bucket}/{prefix_key} --recursive'
        # )
        return 0

    def upload_reports(self, cluster: str, report_name: str = None) -> None:
        """
        Upload reports to the S3 bucket.
        Files uploaded will be partitioned based on report name, account id, region, cluster name and date in YYYY-MM-DD

        Args:
            cluster: Name of the cluster
            report_name: Name of the report to upload

        Returns:
            None
        """

        if report_name is None:
            report_name = self.step_name

        account_id = self.get_account_id()
        current_date = datetime.now().date()

        bucket_key = (
            f"{self.s3_folder}/{report_name}/accountId={account_id}/region={self.region}"
            f"/clusterName={cluster}/date={current_date}"
        )

        report_folder = self.get_reporting_directory(
            cluster=cluster, report_name=report_name
        )
        self.logger.info(f"Uploading {report_folder} to {bucket_key}")
        self.s3_helper.upload_folder(report_folder, self.s3_bucket, bucket_key)

    def cluster_status(self, cluster: str, report: str) -> None:
        """
        Check the status of the cluster. If the cluster is not in ACTIVE status, the SSM Automation step will exit.

        Args:
            cluster: Name of the cluster
            report: Name of the report

        Returns:
            None
        """

        self.logger.info(f"Checking cluster {cluster} status for {self.step_name}")

        cluster_details = self.eks_helper.get_eks_cluster_details(cluster_name=cluster)
        status = cluster_details.get("status")

        report = self.base_report(cluster=cluster, name=report)

        if os.path.isfile(report):
            report_content = FileUtility.read_json_file(report)
            report_content["ClusterStatus"] = status
        else:
            report_content = dict(ClusterStatus=status)

        FileUtility.write_json(report, report_content)

        if status != "ACTIVE":
            self.logger.error(
                f"{cluster} is {status}. So, no actions can be performed.."
            )
            self.upload_reports(cluster=cluster, report_name=report)
            ExecutionUtility.stop()

    def base_report(self, cluster: str, name: str) -> str:
        """
        Create a base report file.

        Args:
            cluster: Name of the cluster
            name: Name of the report

        Returns:
            str: Return report json file path
        """

        return self.json_report_file(cluster=cluster, report_name=name)

    def start(
        self,
        name: str = None,
        report_name: str = None,
        for_each_cluster: bool = True,
        filter_input_clusters: bool = False,
        input_clusters_required: bool = False,
        check_cluster_status: bool = False,
    ) -> None:
        """
        Start the core logic. Using the for_each_cluster flag, the run method call can be controlled
        to run the logic for every cluster for independent of the clusters.

        Args:
            name: Name of the child class. Default to step name.
            report_name: Name of the report to be generated. Default to name.
            for_each_cluster: Specifies if the logic needs to run for each cluster.
            filter_input_clusters: Specifies if clusters need to be filtered.
            input_clusters_required: Specifies is input clusters are required.
            check_cluster_status: Specifies if cluster status needs to be checked.

        Returns:
            None
        """

        if name is None:
            name = self.step_name

        if report_name is None:
            report_name = name

        self.logger.info(f"Begin {name}")

        if for_each_cluster:
            clusters: [InputCluster] = self.get_relevant_clusters(
                filter_input_clusters, input_clusters_required
            )

            self.logger.debug(
                f"List of input clusters that will be processed: {str(clusters)}"
            )
            self.logger.info(f"Starting {name} process for {len(clusters)} clusters")

            for input_cluster in clusters:
                cluster = input_cluster.cluster

                try:
                    if check_cluster_status:
                        # Checking for cluster status
                        self.cluster_status(cluster, report_name)

                    self.logger.info(f"Running step {name} for {cluster}")
                    self.run(input_cluster)
                finally:
                    self.logger.info(f"Uploading {name} reports for  {cluster}")
                    self.upload_reports(cluster=cluster, report_name=report_name)

        else:
            self.logger.info(f"Running step {name} independent of the clusters")
            self.run()

        self.logger.info(f"End {name}")

    def run(self, input_cluster: InputCluster = None) -> None:
        """
        Core logic

        Args:
            input_cluster: InputCluster object. Can be None

        Returns:
            None
        """

        pass

    @staticmethod
    def get_arguments(arguments: dict) -> list:
        """
        Convert dict to a list.
        Example: {"--include-namespace": "*"} will return ["--include-namespace", "*"]

        Args:
            arguments: key values that need to be passed to any CLI command.

        Returns:
            list: converted dict to a list:
        """

        converted = list()
        if arguments is not None:
            for key in arguments:
                converted.append(key)
                converted.append(arguments[key])

        return converted
