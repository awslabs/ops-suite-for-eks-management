import logging
import os
import sys
from datetime import datetime

# Constants
LOG_DIR = "logs"
LOG_FORMATTER = "%(name)s: %(asctime)s | %(levelname)s | %(filename)s:%(lineno)s | %(process)d >>> %(message)s"


class WorkflowLogger:
    """
    Common logger class
    """

    def __init__(
        self,
        log_name: str,
        working_dir: str,
        log_prefix: str,
        log_level: int,
        log_to_file: bool = True,
    ):
        """
        Args:
            log_name: Name of the logger. The same will be used for log file name also.
            working_dir: Directory where log related folders and files need to be created or saved.
            log_prefix: Sub-folder name under `logs` folder.
            log_level: Log level
            log_to_file: Weather the logs need to be streamed to a file.
        """

        self.log_name = log_name
        self.log_prefix = log_prefix
        self.log_level = log_level
        self.working_dir = working_dir

        self._logger = logging.getLogger(name=log_name)
        self._logger.setLevel(log_level)

        fmt = logging.Formatter(LOG_FORMATTER)

        self.stdout_handler(fmt)

        if log_to_file:
            self._logger.debug("Logging to file")
            self.file_handler(fmt)

    def stdout_handler(self, formatter: any):
        stdout_handler = logging.StreamHandler(stream=sys.stdout)
        stdout_handler.setLevel(self.log_level)
        stdout_handler.setFormatter(formatter)
        self._logger.addHandler(stdout_handler)

    def file_handler(self, formatter: any):
        file_name = self.get_log_path()
        self._logger.debug(f"Logging file is {file_name}")

        file_handler = logging.FileHandler(file_name)
        file_handler.setLevel(self.log_level)
        file_handler.setFormatter(formatter)
        self._logger.addHandler(file_handler)

    def get_log_path(self):
        """
        Creates the necessary log directories and subdirectories and returns the log file name.
        Example:
            * Create /home/ec2-user/eks-management/logs folder if not already present.
            * Create /home/ec2-user/eks-management/logs/YYYY-MM-DD folder if not already present
            * Create /home/ec2-user/eks-management/logs/YYYY-MM-DD/{log_prefix} folder if not already present.

        Returns:
            str: Log file path
        """

        logs_dir = f"{self.working_dir}/{LOG_DIR}"
        if not os.path.isdir(logs_dir):
            os.mkdir(logs_dir)

        current_date = datetime.now().date()
        dated_dir = f"{logs_dir}/{current_date}"

        if not os.path.isdir(dated_dir):
            os.mkdir(dated_dir)

        upgrade_logs_folder = f"{dated_dir}/{self.log_prefix}"

        if not os.path.isdir(upgrade_logs_folder):
            os.mkdir(upgrade_logs_folder)

        return f"{upgrade_logs_folder}/{self.log_name}.log"

    @property
    def logger(self):
        return self._logger
