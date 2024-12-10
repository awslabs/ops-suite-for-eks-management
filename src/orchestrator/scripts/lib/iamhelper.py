import json
import logging

import boto3
from botocore.exceptions import ClientError

from .wfutils import ExecutionUtility


class IAMHelper:
    """
    Wrapper class for IAM boto3 client
    """

    iam_client = None

    def __init__(self, calling_module: str):
        log_name = f"{calling_module}.IAMHelper"
        self._logger = logging.getLogger(log_name)

        self.iam_client = boto3.client("iam")

    def create_role(self, role_name: str, trust_relationship_file: str) -> None:
        """
        Create IAM role which will be used by the Service Account attached to the velero plugin.

        Args:
            role_name: Name of the IAM Role that needs to be created.
            trust_relationship_file: Assume policy document

        Returns:
            None
        """

        if self.check_role_exists(role_name):
            self._logger.info("Role already exists. So skipping the creation..")
        else:
            with open(trust_relationship_file) as f:
                trust_policy = json.loads(f.read())

            try:
                role = self.iam_client.create_role(
                    RoleName=role_name,
                    AssumeRolePolicyDocument=json.dumps(trust_policy),
                )
                self._logger.info(f"Created role {role}")
            except ClientError as e:
                self._logger.error(f"Error while creating {role_name}: {e}")
                ExecutionUtility.stop()

    def put_role_policy(self, role_name: str, s3_bucket: str) -> None:
        """
        Put IAM role inline policy so that the velero plugin can access the S3 bucket.

        Args:
            role_name: Name of the IAM Role for which inline policy needs to be created.
            s3_bucket: S3 bucket used to back up the clusters in the target account.

        Returns:
            None
        """

        try:
            self._logger.info(
                f"Attaching inline policy EKSManagement-S3Permissions for {role_name}"
            )

            inline_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "ec2:DescribeVolumes",
                            "ec2:DescribeSnapshots",
                            "ec2:CreateTags",
                            "ec2:CreateVolume",
                            "ec2:CreateSnapshot",
                            "ec2:DeleteSnapshot",
                        ],
                        "Resource": "*",
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "s3:GetObject",
                            "s3:DeleteObject",
                            "s3:PutObject",
                            "s3:AbortMultipartUpload",
                            "s3:ListMultipartUploadParts",
                        ],
                    },
                    {"Effect": "Allow", "Action": ["s3:ListBucket"]},
                ],
            }

            # Python does not allow nesting expressions for now
            inline_policy["Statement"][1]["Resource"] = f"arn:aws:s3:::{s3_bucket}/*"
            inline_policy["Statement"][2]["Resource"] = f"arn:aws:s3:::{s3_bucket}"

            self.iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName="EKSManagement-S3Permissions",
                PolicyDocument=json.dumps(inline_policy),
            )

        except ClientError as e:
            self._logger.error(f"Error while putting custom policy to {role_name}: {e}")
            ExecutionUtility.stop()

    def check_role_exists(self, role_name: str) -> bool:
        """
        Check if IAM role exists.

        Args:
            role_name: IAM Role name

        Returns:
            bool: True if the role exists else False
        """

        try:
            response = self.iam_client.get_role(RoleName=role_name)
            self._logger.info(f"Existing Role response: {response}")
            return True
        except self.iam_client.exceptions.NoSuchEntityException as e:
            self._logger.error(f"Error while fetching {role_name} role details: {e}")
            return False

    def attach_policy(self, role_name: str, policy_arn: str) -> None:
        """
        Attach IAM policy to IAM role

        Args:
            role_name: IAM Role name
            policy_arn: IAM Policy ARN

        Returns:
            None
        """

        try:
            response = self.iam_client.attach_role_policy(
                RoleName=role_name, PolicyArn=policy_arn
            )
            self._logger.info(f"Attached policy response {response}.")
        except ClientError as e:
            self._logger.error(
                f"Error while attaching policy {policy_arn} for {role_name}: {e}"
            )
            ExecutionUtility.stop()
