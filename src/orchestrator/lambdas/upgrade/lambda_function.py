import json
import os

from aws_lambda_powertools import Logger
from ssmautomation import AutomationFunction

logger = Logger()

# Environment Variables
SSM_ASSUME_ROLE = os.getenv("SSM_ASSUME_ROLE", None)
S3_BUCKET = os.getenv("S3_BUCKET", None)
LATEST_EKS_VERSION = os.getenv("LATEST_EKS_VERSION")


class UpgradeLambdaFunction(AutomationFunction):
    def __init__(self):
        super().__init__(name="upgrade", input_clusters_required=True)

    def get_document_parameters(
        self, additional_parameters: dict, eks_clusters
    ) -> dict:
        # Option - defaulted to '/home/ec2-user/eks-management' in SSM Automation document
        # working_dir = additional_parameters.get('WorkingDirectory', '/home/ec2-user/eks-management')

        s3_output_logs_prefix = additional_parameters.get(
            "S3OutputLogsPrefix", self.get_script_log_prefix()
        )

        execution_timeout = additional_parameters.get("ExecutionTimeout", "18000")

        # Option - defaulted to latest EKS version in SSM Automation document
        # eks_version = additional_parameters.get('DesiredEKSVersion', '1.29')

        # Option - defaulted to 'upgrade' in SSM Automation document
        # download_path = additional_parameters.get('DownloadPath', 'eks-backup')

        # Option - defaulted to 'upgrade/scripts' in SSM Automation document
        # script_path = additional_parameters.get('ScriptBasePath', '{{DownloadPath}}/scripts')

        # Option - defaulted to 'upgrade/reports' in SSM Automation document
        # report_path = additional_parameters.get('ReportBasePath', '{{DownloadPath}}/reports')

        # Option - defaulted to SKIP
        update_software = additional_parameters.get("UpdateSoftware", "SKIP")

        return dict(
            AssumeRole=[SSM_ASSUME_ROLE],
            # WorkingDirectory=[working_dir],
            S3Bucket=[S3_BUCKET],
            S3OutputLogsPrefix=[s3_output_logs_prefix],
            ExecutionTimeout=[execution_timeout],
            # DesiredEKSVersion=[eks_version],
            # DownloadPath=[download_path],
            # ScriptBasePath=[script_path],
            # ReportBasePath=[report_path],
            UpdateSoftware=[update_software],
            EKSClusters=[json.dumps(eks_clusters)],
        )


def lambda_handler(event, context):
    logger.info("Lambda invocation started")
    logger.info(f"Event: {event}")
    logger.info(f"Context: {context}")

    default_options: dict = dict(DesiredEKSVersion=LATEST_EKS_VERSION)

    function = UpgradeLambdaFunction()
    return function.execution(
        event, accept_input_clusters=True, default_options=default_options
    )
