import json
import os
from argparse import ArgumentParser

import boto3

from .inputcluster import InputCluster
from .logger import WorkflowLogger
from .wfutils import (
    CLUSTERS_FILE,
    REGION_FILE,
    ClusterUtility,
    ExecutionUtility,
    FileUtility,
)

# AWS SDK Clients
sts_client = boto3.client("sts")


class WorkflowArguments(object):
    """
    Handles parsing command line arguments and providing access to them as properties.
    """

    arg_parser = ArgumentParser()

    _working_directory: str = None
    _s3_bucket: str = None
    _script_base_path: str = None
    _report_base_path: str = None
    _eks_version = None
    _input_clusters: str = None
    _storage_bucket_prefix: str = None
    _update_tools: bool = None

    def __init__(self):
        """
        Parses command line arguments on initialization.
        """
        self.add_arguments()
        self.parse_arguments()

    def add_arguments(self):
        """
        Adds command line arguments to the argument parser.
        These arguments will be passed by the SSM Automation document to the python scripts.
        """
        self.arg_parser.add_argument(
            "-d", "--working-directory", help="Home directory for the code"
        )
        self.arg_parser.add_argument(
            "-s", "--script-base-path", help="Base path where scripts are present"
        )
        self.arg_parser.add_argument(
            "-r",
            "--report-base-path",
            help="Base path where reports need to be generated",
        )
        self.arg_parser.add_argument(
            "-b", "--s3-bucket", help="S3 Bucket to store the report"
        )
        self.arg_parser.add_argument(
            "-v",
            "--eks-version",
            help="eks version used while checking deprecated APIs",
        )
        self.arg_parser.add_argument("-i", "--input-clusters", help="Input clusters")
        self.arg_parser.add_argument(
            "-p", "--s3-storage-prefix", help="S3 bucket prefix used for backups"
        )
        self.arg_parser.add_argument(
            "-t",
            "--update-tools",
            help="Update tools like kubectl installed during preupgrade",
        )

    def parse_arguments(self):
        """
        Parses and sets the command line arguments to properties.
        """
        arguments = self.arg_parser.parse_args()
        self._s3_bucket = arguments.s3_bucket
        self._working_directory = arguments.working_directory
        self._script_base_path = arguments.script_base_path
        self._report_base_path = arguments.report_base_path
        self._eks_version = arguments.eks_version
        self._storage_bucket_prefix = arguments.s3_storage_prefix
        self._update_tools = arguments.update_tools
        self._input_clusters = (
            json.loads(arguments.input_clusters)
            if arguments.input_clusters is not None
            else []
        )

    @property
    def s3_bucket(self) -> str:
        return self._s3_bucket

    @property
    def working_directory(self) -> str:
        return self._working_directory

    @property
    def script_base_path(self) -> str:
        return self._script_base_path

    @property
    def report_base_path(self) -> str:
        return self._report_base_path

    @property
    def eks_version(self) -> str:
        return self._eks_version

    def storage_bucket_prefix(self) -> str:
        return self._storage_bucket_prefix

    @property
    def input_clusters(self) -> []:
        return self._input_clusters

    @property
    def update_tools(self) -> bool:
        return self._update_tools


class AutomationStep(WorkflowArguments):
    """
    Extends `WorkflowArguments` class and provides abstractions for the common functions used by the python scripts
    called by the SSM Automation.

    Child classes need to implement the below methods.
    * run
    """

    region: str = None
    account_id: str = None

    _workflow_logger = None

    def __init__(
        self,
        step_name: str,
        log_prefix: str,
        log_level: int,
        log_to_file: bool = True,
        need_region: bool = True,
    ):
        """
        Args:
            step_name: Generic name of the child class.
            log_prefix: Prefix that needs to be used while logging to a file.
            log_level: Log level.
            log_to_file: Specifies weather logs need to be streamed to a file. Defaults to True.
            need_region: Specifies weather AWS region value is needed. Defaults to True.
        """

        super().__init__()
        self._step_name = step_name

        self._workflow_logger = WorkflowLogger(
            log_name=step_name,
            working_dir=self.working_directory,
            log_prefix=log_prefix,
            log_to_file=log_to_file,
            log_level=log_level,
        )
        self.logger = self._workflow_logger.logger

        self.region_file_path = f"{self.working_directory}/{REGION_FILE}"
        self.cluster_file_path = f"{self.working_directory}/{CLUSTERS_FILE}"

        self.account_id = self.get_account_id()

        if need_region:
            self.region = self.get_region()

    def bash_scripts_path(self) -> str:
        """
        Get the bash scripts path. This needs to be overridden in the child classes.

        Returns:
            str: path of the bash scripts.
        """

        pass

    def start(
        self,
        name: str = None,
        report_name: str = None,
        for_each_cluster: bool = True,
        filter_input_clusters: bool = False,
        check_cluster_status: bool = False,
    ) -> None:
        """
        Start the core logic.

        Args:
            name: Name of the child class. Default to step name.
            report_name: Name of the report to be generated. Default to name.
            for_each_cluster: Specifies if the logic needs to run for each cluster.
            filter_input_clusters: Specifies if clusters need to be filtered.
            check_cluster_status: Specifies if cluster status needs to be checked.

        Returns:
            None
        """

        pass

    def run(self, input_cluster: InputCluster = None) -> None:
        """
        Function containing core logic.

        Args:
            input_cluster: Input cluster passed from SSM Automation. Defaults to None.

        Returns:
            None
        """

        pass

    @property
    def step_name(self) -> str:
        return self._step_name

    def get_account_id(self) -> str:
        """
        Get AWS Account ID

        Returns:
            str: AWS Account ID
        """

        try:
            return sts_client.get_caller_identity()["Account"]
        except Exception as e:
            self.logger.error(f"Error while fetching Account ID: {e}")
            ExecutionUtility.stop()

    def get_region(self) -> str:
        """
        Get AWS Region from config/region.txt file

        Returns:
            str: AWS Region value
        """

        self.validate_file(self.region_file_path)
        region = FileUtility.read_file(self.region_file_path)

        if region is None or region == "":
            self.logger.error(f"Region not found in the {self.region_file_path}")
            ExecutionUtility.stop()

        return region

    def get_eks_clusters(self) -> []:
        """
        Get EKS Clusters from config/clusters.json file.
        This file is populated using <b>aws eks list-clusters</b> API.

        Returns:
            []: Array of EKS Clusters
        """

        self.validate_file(self.cluster_file_path)

        json_file = FileUtility.read_json_file(self.cluster_file_path)
        clusters = json_file["clusters"]

        if clusters is None or len(clusters) == 0:
            self.logger.error(f"EKS clusters not found in the {self.cluster_file_path}")
            ExecutionUtility.stop()

        return clusters

    def get_relevant_clusters(
        self, filter_input_clusters: bool, input_clusters_required: bool
    ) -> [InputCluster]:
        """
        Get clusters that can be processed by the current Ec2 Instance

        Args:
            filter_input_clusters: Specifies weather clusters need to be filtered by cluster details provided
                in the input by SSM Automation.
            input_clusters_required: Specifies weather input clusters are required.

        Returns:
            [InputCluster]: Array of InputCluster that needs to be processed.
        """

        valid_account_clusters: [] = self.get_eks_clusters()

        if not input_clusters_required and len(self.input_clusters) == 0:
            self.logger.info(
                "Input clusters are empty and they are not required. "
                "So, defaulting to all teh clusters in the account region"
            )
            filter_input_clusters = False

        return ClusterUtility.get_relevant_clusters(
            filter_input_clusters=filter_input_clusters,
            valid_account_clusters=valid_account_clusters,
            input_clusters=self.input_clusters,
            account_id=self.account_id,
            region=self.region,
        )

    def get_reporting_directory(self, cluster: str, report_name: str = None) -> str:
        """
        Get the report directory path

        Args:
            cluster: EKS Cluster name
            report_name: Name of the report.

        Returns:
            str: Path of the report folder.
        """

        if report_name is None:
            report_name = self.step_name

        return (
            f"{self.working_directory}/{self.report_base_path}/{cluster}/{report_name}"
        )

    def create_report_directory(self, cluster: str, report_name: str) -> None:
        """
        Create report directory if it doesn't exist.

        Args:
            cluster: EKS Cluster name
            report_name: Name of the report.
        """

        report_dir = self.get_reporting_directory(cluster, report_name)

        if not os.path.exists(report_dir):
            self.logger.info(f"Creating reporting directory for {cluster}")
            os.mkdir(report_dir)

        self.logger.info(f"Reporting directory: {report_dir}")

    def json_report_file(self, cluster: str, report_name: str = None) -> str:
        """
        Create a JSON file to write report contents.

        Args:
            cluster: EKS Cluster name
            report_name: Name of the report.

        Returns:
            str: Path of the JSON file
        """

        if report_name is None:
            report_name = self.step_name

        self.create_report_directory(cluster, report_name)
        report_dir = self.get_reporting_directory(cluster, report_name)

        return f"{report_dir}/{report_name}.json"

    def csv_report_file(self, cluster: str, report_name: str = None) -> str:
        """
        Create a CSV file to write report contents.

        Args:
            cluster: EKS Cluster name
            report_name: Name of the report.

        Returns:
            str: Path of the CSV file
        """

        if report_name is None:
            report_name = self.step_name

        self.create_report_directory(cluster, report_name)
        report_dir = self.get_reporting_directory(cluster, report_name)

        return f"{report_dir}/{report_name}.csv"

    def validate_file(self, file: str) -> None:
        """
        Validate if a file is present. Used to validate if region.txt and clusters.json files are present.
        Exits if file is not present.
        """

        if not os.path.isfile(file):
            self.logger.error(f"{file} does not exist")
            ExecutionUtility.stop()

        self.logger.debug(f"{file} exists")
