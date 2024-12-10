import logging
import os.path

import boto3
from botocore.exceptions import ClientError

from .wfutils import ExecutionUtility


class S3Helper:
    """
    Wrapper class for S3 boto3 client
    """

    def __init__(self, calling_module: str):
        log_name = f"{calling_module}.S3Helper"
        self._logger = logging.getLogger(log_name)

        self.s3_client = boto3.client("s3")

    def upload_file(
        self, file_name: str, file_path: str, bucket: str, key: str
    ) -> None:
        """
        Upload a file to S3 bucket

        Args:
            file_name: Name of the file to upload
            file_path: Full Path of the file to upload
            bucket: S3 bucket name
            key: The name of the key to upload to.

        Returns:
            None
        """

        try:
            s3_file_name = f"{key}/{file_name}"
            self.s3_client.upload_file(file_path, bucket, s3_file_name)
        except ClientError as e:
            self._logger.error(
                f"Error while uploading file {file_name} to {bucket}/{key}: {e}"
            )
            ExecutionUtility.stop()

    def upload_folder(self, folder: str, bucket: str, key: str) -> None:
        """
        Upload a folder all its sub-folders to S3 bucket

        Args:
            folder: Folder path which needs to be uploaded to S3
            bucket: S3 bucket name
            key: The name of the key to upload to.

        Returns:
            None
        """

        for root, dirs, files in os.walk(folder):
            for file in files:
                local_path = os.path.join(root, file)
                self.upload_file(file, local_path, bucket, key)

        self._logger.info(f"Uploaded {folder} to S3")
