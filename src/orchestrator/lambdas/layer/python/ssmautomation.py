import os
from datetime import datetime

import boto3
from aws_lambda_powertools import Logger
from cluster import Cluster
from factory import get_input_clusters, get_target_locations

# Environment Variables
DOCUMENT_NAME = os.getenv("DOCUMENT_NAME", None)
TARGET_TAG_KEY = os.getenv("TARGET_TAG_KEY", "EKSManagementNode")
TARGET_TAG_VALUE = os.getenv("TARGET_TAG_VALUE", "EKSManagementBastionHost")

# Constants
"""
Target identifier
"""
TARGET_PARAMETER_NAME = "InstanceId"

"""
Default SSM Automation concurrency.
"""
DEFAULT_MAX_CONCURRENCY = 10

"""
Default SSM Automation errors. 0 specifies, if at-least one execution fails, then stop all the automation executions.
"""
DEFAULT_MAX_ERRORS = 0

ssm = boto3.client("ssm")
logger = Logger()


class SSMAutomation:
    """
    Class with functionality to start SSM Automation
    """

    def __init__(self):
        self.validate_env_vars()

    def start_automation(
        self,
        parameters: dict,
        target_locations: [],
        max_concurrency: str,
        max_errors: str,
    ) -> str:
        """
        Start SSM Automation

        Args:
            parameters: Parameters to pass to SSM Automation document
            target_locations: Target locations to run the SSm Automation
            max_concurrency: Maximum concurrency while running the automation on different targets
            max_errors: Maximum number of errors to ignore while running the automation

        Returns:
            str: Automation Execution Id
        """

        try:
            logger.info(f"Staring automation for {DOCUMENT_NAME}")
            response = ssm.start_automation_execution(
                DocumentName=DOCUMENT_NAME,
                TargetParameterName=TARGET_PARAMETER_NAME,
                Parameters=parameters,
                Targets=self.get_targets(),
                MaxConcurrency=max_concurrency,
                MaxErrors=max_errors,
                TargetLocations=target_locations,
            )
            logger.info(f"Automation started for {DOCUMENT_NAME}: {response}")
            return response.get("AutomationExecutionId")
        except Exception as e:
            logger.error(
                f"An error occurred while starting automation for {DOCUMENT_NAME}"
            )
            raise Exception(str(e))

    @staticmethod
    def validate_env_vars() -> None:
        """
        Validate if environment variables are present.

        Returns:
            None

        Raises:
            Exception
        """

        if TARGET_TAG_KEY is None or TARGET_TAG_VALUE is None:
            raise Exception(
                "TARGET_TAG_KEY and TARGET_TAG_VALUE environment variables are required"
            )

        if DOCUMENT_NAME is None or DOCUMENT_NAME == "":
            raise Exception("DOCUMENT_NAME environment variable is required")

    @staticmethod
    def get_targets() -> []:
        """
        List of targets to run the SSm Automation.
        Here tag key value pairs are used to identify the bastion host instances.

        Returns:
            []: List of targets
        """
        return [{"Key": f"tag:{TARGET_TAG_KEY}", "Values": [TARGET_TAG_VALUE]}]


class AutomationFunction:
    """
    Lambda function base class.
    Child classes should implement the following methods:
    * get_document_parameters
    """

    def __init__(self, name: str, input_clusters_required: bool):
        self.name = name
        self._date = datetime.now()
        self.input_clusters_required = input_clusters_required

    def execution(
        self, event: dict, accept_input_clusters: bool = False, default_options=None
    ) -> dict:
        """
        * Get the target locations
        * Get the clusters from event, if need_input_clusters is true
        * Start the SSM Automation

        Args:
            event: Lambda event
            accept_input_clusters: Weather input clusters are needed
            default_options: Default options for SSM Automation

        Returns:
            dict: (StatusCode, Response)
        """

        try:
            if accept_input_clusters:
                logger.info(f"Fetching input clusters for {self.name}...")
                eks_clusters: [Cluster] = get_input_clusters(
                    self.name, event, default_options
                )
                logger.info(f"Cluster mappings: {eks_clusters}")

                if len(eks_clusters) == 0 and self.input_clusters_required:
                    return {
                        "StatusCode": 404,
                        "Response": {"Error": {"Message": "No clusters provided"}},
                    }
            else:
                logger.info(f"No need to fetch input clusters for {self.name}...")
                eks_clusters = []

            try:
                target_locations = get_target_locations(
                    event=event, eks_clusters=eks_clusters
                )
                logger.debug(f"Target locations: {target_locations}")

                if len(target_locations) == 0:
                    return {
                        "StatusCode": 404,
                        "Response": {
                            "Error": {
                                "Message": "Account details not found. "
                                "Run /tenants/onboard API to onboard the tenants to DynamoDB"
                            }
                        },
                    }

            except Exception as e:
                logger.error(
                    f"Exception while fetching targets for {self.name}: {str(e)}"
                )
                return {
                    "StatusCode": 500,
                    "Response": {"Error": {"Message": f"Error while fetching targets"}},
                }

        except Exception as e:
            logger.error(
                f"Exception while fetching input clusters for {self.name}: {str(e)}"
            )
            return {"StatusCode": 500, "Response": {"Error": {"Message": f"{str(e)}"}}}

        try:
            additional_parameters = event.get("Parameters", {})
            document_parameters = self.get_document_parameters(
                additional_parameters, eks_clusters
            )
            max_concurrency = event.get("MaxConcurrency", DEFAULT_MAX_CONCURRENCY)
            max_errors = event.get("MaxErrors", DEFAULT_MAX_ERRORS)

            ssm_automation = SSMAutomation()
            execution_id = ssm_automation.start_automation(
                parameters=document_parameters,
                max_concurrency=str(max_concurrency),
                max_errors=str(max_errors),
                target_locations=target_locations,
            )

            return {
                "StatusCode": 200,
                "Request": {
                    "TargetLocations": target_locations,
                    "Parameters": document_parameters,
                    "MaxConcurrency": max_concurrency,
                    "MaxErrors": max_errors,
                },
                "Response": {"AutomationExecutionId": execution_id},
            }
        except Exception as e:
            logger.error(f"Exception while starting automation: {str(e)}")
            return {
                "StatusCode": 500,
                "Response": {
                    "Error": {"Message": f"Error while starting automation: {str(e)}"}
                },
            }

    def get_document_parameters(
        self, additional_parameters: dict, eks_clusters
    ) -> dict:
        """
        Get the parameters for the SSM Automation

        Args:
            additional_parameters: Additional parameters that are passed in the lambda event.
            eks_clusters: Input EKS Clusters

        Returns:
            dict: Parameters that will be passed to the SSM Automation document.
        """

        pass

    def get_script_log_prefix(self) -> str:
        """
        Get the log prefix for the SSM Automation

        Returns:
            str: Prefix for the SSM logs in S3
        """

        return f"logs/ssm/{self.name}/{self._date.date()}"
