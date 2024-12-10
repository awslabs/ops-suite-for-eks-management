import os.path
import shutil
import sys

import boto3
from botocore.utils import *

from .automationstep import AutomationStep
from .ekshelper import EKSHelper
from .inputcluster import InputCluster
from .processhelper import ProcessHelper
from .wfutils import CLUSTERS_FILE, REGION_FILE, ExecutionUtility, FileUtility

# Constants
"""
Default log name
"""
DEFAULT_LOG_NAME = "config"

"""
Config folder
"""
CONFIG_FOLDER: str = "config"

"""
Folder path where config bash scripts are located.
"""
CONFIG_BASH_SCRIPTS_FOLDER: str = "bash"

# AWS SDK Clients
sts_client = boto3.client("sts")


class BaseConfig(AutomationStep):
    """
    Class that extends AutomationStep and has implementation for the start method. Also has common methods that are used
    by the config automation steps.
    """

    def __init__(
        self,
        config_name: str,
        log_prefix: str,
        log_name: str = DEFAULT_LOG_NAME,
        log_level: int = logging.INFO,
        need_region: bool = True,
        log_to_file: bool = True,
    ):
        """
        Args:
            config_name: Name of the config step.
            log_prefix: Log sub-folder name
            log_name: Name of the logger
            log_level: Log level
            need_region: Whether a region needs to be fetched from the file.
            log_to_file: Weather to stream the logs to file
        """

        super().__init__(
            step_name=log_name,
            log_prefix=log_prefix,
            log_level=log_level,
            log_to_file=log_to_file,
            need_region=need_region,
        )

        self.process_helper = ProcessHelper(DEFAULT_LOG_NAME)

        self.config_name = config_name
        self.region_file_path = f"{self.working_directory}/{REGION_FILE}"
        self.cluster_file_path = f"{self.working_directory}/{CLUSTERS_FILE}"
        self.config_path = f"{self.working_directory}/{CONFIG_FOLDER}"

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

        Returns:

        """

        if name is None:
            name = self.config_name

        self.logger.info(f"Begin {name}")

        if for_each_cluster:
            clusters: [InputCluster] = self.get_relevant_clusters(
                filter_input_clusters, input_clusters_required
            )

            self.logger.debug(
                f"List of input clusters that will be processed: {str(clusters)}"
            )
            self.logger.info(f"Starting {name} process for {len(clusters)} clusters")

            for cluster in clusters:
                self.run(cluster)

        else:
            self.logger.info(f"Starting {name} process")
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

    def bash_scripts_path(self) -> str:
        """
        Get the config bash scripts path

        Returns:
            str: Path to the config bash scripts
        """

        return f"{self.working_directory}/{self.script_base_path}/{CONFIG_BASH_SCRIPTS_FOLDER}"

    def write_config_yaml(self, yaml_content, yaml_file_name) -> None:
        """
        Write YAML content into a config file. After the file is created, the permissions are changed to 744.

        Args:
            yaml_content: Content
            yaml_file_name: File path

        Returns:
            None
        """

        yaml_file_path = (
            f"{self.working_directory}/{CONFIG_FOLDER}/{yaml_file_name}.yaml"
        )
        FileUtility.write_yaml(yaml_file_path, yaml_content)

        self.logger.info(f"Created {yaml_file_path}")
        # os.chmod(path=yaml_file_path, mode=744)


class BaseClustersConfig(BaseConfig):
    """
    Get all the clusters and store it in a file
    """

    eks_helper: EKSHelper = None

    def __init__(
        self,
        config_name: str,
        log_prefix: str,
        log_name: str = DEFAULT_LOG_NAME,
        log_level: int = logging.INFO,
        need_region: bool = True,
        log_to_file: bool = True,
    ):
        """
        Args:
            config_name: Name of the config step.
            log_prefix: Log sub-folder name
            log_name: Name of the logger
            log_level: Log level
            need_region: Whether a region needs to be fetched from the file.
            log_to_file: Weather to stream the logs to file
        """

        super().__init__(
            config_name=config_name,
            log_name=log_name,
            log_prefix=log_prefix,
            log_level=log_level,
            log_to_file=log_to_file,
            need_region=need_region,
        )

        self.eks_helper = EKSHelper(region=self.region, calling_module=DEFAULT_LOG_NAME)

    def run(self, input_cluster: InputCluster = None) -> None:
        """
        Write clusters with access to a file.

        Args:
            input_cluster: InputCluster object

        Returns:
            None
        """

        clusters = self.get_clusters_with_access()

        with open(self.cluster_file_path, "w") as f:
            f.write(json.dumps(clusters))

    def get_clusters_with_access(self):
        all_clusters = self.eks_helper.list_clusters()
        clusters_with_access = set()
        for cluster in all_clusters:
            if self.eks_helper.can_describe_cluster(cluster):
                self.logger.info(f"Instance has access to : {cluster}")
                clusters_with_access.add(cluster)

        return {"clusters": list(clusters_with_access)}


class BaseRegionConfig(BaseConfig):
    """
    Get the region of the bastion host
    """

    def __init__(
        self,
        config_name: str,
        log_prefix: str,
        log_name: str = DEFAULT_LOG_NAME,
        log_level: int = logging.INFO,
        need_region: bool = True,
        log_to_file: bool = True,
    ):
        """
        Args:
            config_name: Name of the config step.
            log_prefix: Log sub-folder name
            log_name: Name of the logger
            log_level: Log level
            need_region: Whether a region needs to be fetched from the file.
            log_to_file: Weather to stream the logs to file
        """

        super().__init__(
            config_name=config_name,
            log_name=log_name,
            log_prefix=log_prefix,
            log_level=log_level,
            log_to_file=log_to_file,
            need_region=need_region,
        )

    def run(self, input_cluster: InputCluster = None) -> None:
        """
        Write region value to a file.

        Args:
            input_cluster: InputCluster object

        Returns:
            None
        """

        region = self.get_region_from_boto()

        if region is None:
            print("Region not found. Please provide a default region")
            sys.exit(1)

        with open(self.region_file_path, "w") as f:
            f.write(region)

    def get_region_from_boto(self):
        try:
            region_fetcher = InstanceMetadataRegionFetcher(timeout=60, num_attempts=3)

            return region_fetcher.retrieve_region()
        except Exception as e:
            self.logger.error(
                f"Error while fetching region from InstanceMetadataRegionFetcher: {e}"
            )
            sys.exit(1)


class BaseReportConfig(BaseConfig):
    """
    Cleanup the existing reports and create new report folders for each cluster.
    BaseConfig implementation for run method.
    """

    def __init__(
        self,
        config_name: str,
        log_prefix: str,
        log_name: str = DEFAULT_LOG_NAME,
        log_level: int = logging.INFO,
        need_region: bool = True,
        log_to_file: bool = True,
    ):
        """
        Args:
            config_name: Name of the config step.
            log_prefix: Log sub-folder name
            log_name: Name of the logger
            log_level: Log level
            need_region: Whether a region needs to be fetched from the file.
            log_to_file: Weather to stream the logs to file
        """

        super().__init__(
            config_name=config_name,
            log_name=log_name,
            log_prefix=log_prefix,
            log_level=log_level,
            log_to_file=log_to_file,
            need_region=need_region,
        )

    def run(self, input_cluster: InputCluster = None) -> None:
        """
        Delete an existing report directory and create a new one for each cluster.

        Args:
            input_cluster: InputCluster object

        Returns:
            None
        """

        cluster: str = input_cluster.cluster

        self.logger.info(f"Cleaning up existing reports for {cluster}")

        directory = f"{self.working_directory}/{self.report_base_path}/{cluster}"

        if os.path.isdir(directory):
            self.logger.info(f"{directory} exists. Deleting...")
            shutil.rmtree(directory)

        os.mkdir(directory)
        self.logger.info(f"Created new directory: {directory}")


class BaseKubeConfig(BaseConfig):
    """
    Create a new kubernetes config file for each cluster.
    BaseConfig implementation for run method.
    """

    def __init__(
        self,
        config_name: str,
        log_prefix: str,
        log_name: str = DEFAULT_LOG_NAME,
        log_level: int = logging.INFO,
        need_region: bool = True,
        log_to_file: bool = True,
    ):
        """
        Args:
            config_name: Name of the config step.
            log_prefix: Log sub-folder name
            log_name: Name of the logger
            log_level: Log level
            need_region: Whether a region needs to be fetched from the file.
            log_to_file: Weather to stream the logs to file
        """

        super().__init__(
            config_name=config_name,
            log_name=log_name,
            log_prefix=log_prefix,
            log_level=log_level,
            log_to_file=log_to_file,
            need_region=need_region,
        )

    def run(self, input_cluster: InputCluster = None) -> None:
        """
        Create a new kubernetes config file for each cluster if it doesn't exist.
        If access is denied, then exit from the SSM Automation.

        Args:
            input_cluster: InputCluster object

        Returns:
            None
        """

        cluster: str = input_cluster.cluster

        kube_config_path = f"{self.config_path}/{cluster}"

        if not os.path.isfile(kube_config_path):
            self.logger.info(f"{kube_config_path} file does not exist.")

            self.logger.info(
                f"Updating kubeconfig for {kube_config_path} and region {self.region}"
            )
            aws_arguments: list[str] = [
                "eks",
                "update-kubeconfig",
                "--kubeconfig",
                kube_config_path,
                "--region",
                self.region,
                "--name",
                cluster,
                "--alias",
                cluster,
            ]

            resp = self.process_helper.run("aws", aws_arguments)

            if resp.returncode == 0:
                self.logger.info(f"Config file updated for {cluster}")
                chmod_arguments: list[str] = ["744", kube_config_path]
                resp = self.process_helper.run("chmod", chmod_arguments)
                if resp.returncode != 0:
                    self.logger.error(f"Not able to chmod {kube_config_path}")
                    ExecutionUtility.stop()
            else:
                self.logger.error(f"Config file not created for {cluster}")
                ExecutionUtility.stop()

            self.check_access(cluster, kube_config_path)

        else:
            self.check_access(cluster, kube_config_path)

    def check_access(self, cluster: str, kube_config_path: str) -> None:
        """
        Check if the clusters are accessible using kubectl.
        Exit from SSM Automation, if no access is possible.

        Args:
            cluster: Name of the cluster
            kube_config_path: Path of the kubernetes config file path

        Returns:
            None
        """

        self.logger.info("Getting the EKS Control Plane version")

        kubectl_arguments: list[str] = [
            f"--kubeconfig={kube_config_path}",
            "version",
            "-o",
            "json",
        ]

        kubectl_resp = self.process_helper.run("kubectl", kubectl_arguments)

        if kubectl_resp.returncode == 0:
            jq_arguments: list[str] = ["-rj", '.serverVersion|.major,".",.minor']

            jq_resp = self.process_helper.run("jq", jq_arguments)
            self.logger.info(
                f"Able to access {cluster}. Cluster version is {jq_resp.stdout}"
            )
        else:
            self.logger.error(
                f"Not able to access {cluster}. Please check the RBAC for the cluster."
            )
            ExecutionUtility.stop()


class FilterClustersConfig(BaseConfig):
    """
    Check if the input clusters can be processed by the current AWS account, region and Bastion host.
    BaseConfig implementation for run method.
    """

    def __init__(
        self,
        config_name: str,
        log_prefix: str,
        log_name: str = DEFAULT_LOG_NAME,
        log_level: int = logging.INFO,
        need_region: bool = True,
        log_to_file: bool = False,
    ):
        """
        Args:
            config_name: Name of the config step.
            log_prefix: Log sub-folder name
            log_name: Name of the logger
            log_level: Log level
            need_region: Whether a region needs to be fetched from the file.
            log_to_file: Weather to stream the logs to file
        """

        super().__init__(
            config_name=config_name,
            log_name=log_name,
            log_prefix=log_prefix,
            log_level=log_level,
            log_to_file=log_to_file,
            need_region=need_region,
        )

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
        This class is used in the SSM Automation branching step.

        Args:
            name: Name of the child class. Default to step name.
            report_name: Name of the report to be generated.
            Default to name.
            for_each_cluster: Specifies if the logic needs to run for each cluster.
            filter_input_clusters: Specifies if clusters need to be filtered.
            input_clusters_required: Specifies weather the clusters are required.
            check_cluster_status: Specifies if cluster status needs to be checked.

        Returns:

        """

        self.check_for_clusters(input_clusters_required)

    def check_for_clusters(self, input_clusters_required: bool) -> None:
        """
        Check if the relevant clusters are present.

        Args:
            input_clusters_required: Specifies weather the clusters are required.

        Returns:
            None
        """
        relevant_input_clusters = self.get_relevant_clusters(
            filter_input_clusters=True, input_clusters_required=input_clusters_required
        )
        count = len(relevant_input_clusters)
        if count == 0:
            output = dict(AccountClustersInInput="Not Present")
        else:
            output = dict(AccountClustersInInput=f"{count} EKS Clusters Found")

        print(json.dumps(output))
