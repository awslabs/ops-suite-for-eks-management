import logging

# nosec B404
from subprocess import CalledProcessError, CompletedProcess, run
from typing import Union

from .wfutils import ExecutionUtility


class ProcessHelper:
    """
    Wrapper class for subprocess.
    """

    def __init__(self, calling_module: str):
        log_name = f"{calling_module}.ProcessHelper"
        self._logger = logging.getLogger(log_name)

    def run(
        self, command: str, arguments: list[str]
    ) -> Union[CompletedProcess, CalledProcessError]:
        """
        Execute the command in a subprocess.
        Note: Added union instead of | (bitwise OR) for the return types to support python version 3.9 or above.
        Args:
            command: Command to execute
            arguments: List of arguments to be passed to the command

        Returns:
            CompletedProcess | CalledProcessError
        """

        self._logger.info(f"Running command: {command}")
        self._logger.debug(f"Running command: {command} with arguments: {arguments}")

        args = [command]
        args.extend(arguments)

        try:
            # nosec B404
            output: CompletedProcess = run(
                args, capture_output=True, check=True, encoding="UTF-8", shell=False
            )

            self._logger.info(f"{output.stdout}")
            self._logger.info(
                f"Command {command} completed with status: {output.returncode}"
            )

            return output

        except CalledProcessError as e:
            self._logger.info(f"{e.stdout}")
            self._logger.error(
                f"{command} failed with status {e.returncode}: {e.stderr}"
            )

            return e

    def run_shell(self, script_file: str, arguments: list[str]) -> int:
        """
        Execute the script file in a subprocess.

        Args:
            script_file: The full path of the shell script
            arguments: List of arguments to be passed to the shell script

        Returns:
            int: Status of the script execution
        """

        self.shell_executable(script_file)

        return self.run(script_file, arguments).returncode

    def shell_executable(self, script_file: str) -> None:
        """
        Make the script file executable

        Args:
            script_file: The script file which needs to be made executable

        Returns:
            None
        """

        args: list[str] = ["chmod", "u+x", script_file]
        try:
            # nosec B404
            output: CompletedProcess = run(
                args, capture_output=True, check=True, encoding="UTF-8", shell=False
            )

            self._logger.debug(f"{script_file} made executable")

        except CalledProcessError as e:
            self._logger.info(f"{e.stdout}")
            self._logger.error(f"failed to make {script_file} executable: {e.stderr}")
            ExecutionUtility.stop()
